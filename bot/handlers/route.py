import tgalice

from api.rzd_basic import suggest_first_station, find_route, init_find_route, request_find_route_result
from bot.turn import RzdTurn, csc
from utils.date_convertor import convert_date_to_abs, date2ru
from utils.morph import with_number


def filter_trains(trains: list, rzd_car_type: str):
    """Фильтруем список предложений поездов по типу вагона."""
    return [train for train in trains if train['seat_type'] == rzd_car_type]


def check_slots_and_chose_state(turn: RzdTurn):
    """Проверяем что заполнены все слоты. Если что-то не заполнено то выбираем какой заполнить."""
    # Достаем все возможные слоты из объекта
    from_text = turn.user_object.get("from_text", None)
    to_text = turn.user_object.get("to_text", None)
    when_text = turn.user_object.get("when_text", None)

    if from_text and to_text and when_text:
        turn.response_text = f'Ищу билеты {from_text} {to_text} {when_text}. Все правильно?'
        next_stage = 'expect_after_slots_filled'

        from_id = turn.user_object.get('from_id', None)
        to_id = turn.user_object.get('to_id', None)
        date_to = turn.user_object.get('when_text', None)
        params, cookies = init_find_route(from_id, to_id, date_to)
        turn.user_object['find_route_params'] = params
        turn.user_object['find_route_cookies'] = cookies

        # На данном этапе полностью получены все слоты
        turn.suggests.extend(['Да', 'Нет'])

    elif from_text and to_text:
        turn.response_text = f'Когда поедем {from_text} {to_text}?'
        next_stage = 'expect_departure_time'
        turn.suggests.extend(['Завтра', 'Сегодня'])

    elif from_text and when_text:
        turn.response_text = f'Куда поедем {from_text} {when_text}?'
        next_stage = 'expect_destination_place'
        turn.suggests.extend(['Петербург', 'Казань'])

    elif to_text and when_text:
        turn.response_text = f'Откуда поедем {to_text} {when_text}?'
        next_stage = 'expect_departure_place'
        turn.suggests.extend(['Москва', 'Петербург'])

    else:
        turn.response_text = f'Давайте попробуем заново. Откуда и куда вы хотите билет?'
        next_stage = None
        turn.suggests.extend(['Москва', 'Петербург'])

    if next_stage:
        print(f"Next stage: {next_stage}")
        turn.stage = next_stage

    return turn


def get_trains(turn: RzdTurn):
    """Формирование результата, полученного через API."""
    params = turn.user_object.get('find_route_params', None)
    cookies = turn.user_object.get('find_route_cookies', None)

    return request_find_route_result(params, cookies, format_result=True)


@csc.add_handler(priority=30, stages=['expect_after_slots_filled'], intents=['yes', 'no'])
def expect_after_slots_filled(turn: RzdTurn):
    print("expect_after_slots_filled handler")
    if 'yes' in turn.intents:
        # Дождались положительного ответа от пользователя после формирования полного запроса
        # Достаем результат
        trains_list = get_trains(turn)
        turn.user_object['trains'] = trains_list

        print("Trains")
        for train in trains_list:
            print(train)

        print(f"intents: {turn.intents}")
        turn.response_text = 'Найдено несколько поездов. Какое место хотите?'
        turn.stage = 'expect_all_train_data'
        turn.suggests.extend(['Верхнее место в плацкартном вагоне', 'Нижнее место в купе'])

        # turn.response_text = f'Я нашла вам несколько вариантов.'
        # turn.stage = 'expect_ticket_decision'
    else:
        turn.response_text = f'К сожалению, я ничего не нашла. Давайте попробуем заново'


@csc.add_handler(priority=10, intents=['intercity_route'])
def intercity_route(turn: RzdTurn):
    print(f"intercity_route handler intents: {turn.intents}")
    print(f"intercity_route handler forms: {turn.forms['intercity_route']}")
    forms = turn.forms['intercity_route']
    # from_text = turn.ctx.yandex.request.nlu.intents['route_from_to'].slots['from']

    # Может быть заполнено от 1 до 3х форм: from, to, when
    from_text = forms.get('from', None)
    to_text = forms.get('to', None)
    when_text = forms.get('when', None)

    if from_text:
        turn.user_object['from_text'] = from_text
        turn.user_object['from_id'] = suggest_first_station(from_text)
    if to_text:
        turn.user_object['to_text'] = to_text
        turn.user_object['to_id'] = suggest_first_station(to_text)
    if when_text:
        turn.user_object['when_text'] = date2ru(convert_date_to_abs(when_text))

    print(f"intercity_route turn: {turn.user_object['from_text']}")
    turn = check_slots_and_chose_state(turn)
    print(f"turn.response_text: {turn.response_text}")


@csc.add_handler(priority=20, stages=['expect_departure_time'], intents=['slots_filling'])
def expect_departure_time(turn: RzdTurn):
    print("expect_departure_time handler")

    # Должен быть заполнен интент slots_filing и слот when
    forms = turn.forms['slots_filling']
    when_text = forms.get('when', None)

    if not when_text:
        # Во время дозаполнения слота времени мы не получили данный слот. Переспрашиваем ещё раз
        turn.response_text = 'Назовите дату, на которую хотите посмотреть билет'
        # Оставляем тот же стейт
        turn.stage = 'expect_departure_time'
        turn.suggests.extend(['Завтра', 'Сегодня'])
    else:
        # Получили недостающий слот со временем. Заполняем данные=
        turn.user_object['when_text'] = date2ru(convert_date_to_abs(when_text))
        turn = check_slots_and_chose_state(turn)
        print(f"turn.response_text: {turn.response_text}")


@csc.add_handler(priority=20, stages=['expect_destination_place'], intents=['slots_filling'])
def expect_destination_place(turn: RzdTurn):
    # Уточняем место назначения
    print("expect_destination_place handler")

    # Должен быть заполнен интент slots_filing и слот to
    forms = turn.forms['slots_filling']
    to_text = forms.get('to', None) or forms.get('place', None)

    if not to_text:
        # Во время дозаполнения слота места назначения мы не получили данный слот. Переспрашиваем ещё раз
        turn.response_text = 'Назовите конечный пункт куда вы держите путь'
        # Оставляем тот же стейт
        turn.stage = 'expect_destination_place'
        turn.suggests.extend(['Москва', 'Петербург'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['to_text'] = to_text
        turn.user_object['to_id'] = suggest_first_station(to_text)
        turn = check_slots_and_chose_state(turn)
        print(f"turn.response_text: {turn.response_text}")


@csc.add_handler(priority=20, stages=['expect_departure_place'], intents=['slots_filling'])
def expect_departure_place(turn: RzdTurn):
    # Уточняем место отправления
    print("expect_departure_place handler")

    # Должен быть заполнен интент slots_filing и слот from
    forms = turn.forms['slots_filling']
    from_text = forms.get('from', None) or forms.get('place', None)

    if not from_text:
        # Во время дозаполнения слота места отправления мы не получили данный слот. Переспрашиваем ещё раз
        turn.response_text = 'Назовите, откуда вы собираетесь выезжать'
        # Оставляем тот же стейт
        turn.stage = 'expect_departure_place'
        turn.suggests.extend(['Москва', 'Петербург'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['from_text'] = from_text
        turn.user_object['from_id'] = suggest_first_station(from_text)
        turn = check_slots_and_chose_state(turn)
        print(f"turn.response_text: {turn.response_text}")


def get_human_readable_existing_car_types(trains: list):
    existing_car_types = set(train['seat_type'] for train in trains)
    return [car_type.capitalize() for car_type in existing_car_types]


def car_type_to_rzd_type(car_type):
    mapping = {
        "seating": "Сидячий",
        "first_class": "СВ",
        "econom": "Плацкартный",
        "sleeping": "Купе",
        "luxury": "Люкс"
    }
    return mapping[car_type]


def car_type_to_human_str(car_type: str, form=0):
    plural_mapping = {
        "seating": "сидячие",
        "first_class": "СВ",
        "econom": "плацкартные",
        "sleeping": "купейные",
        "luxury": "люксовый"
    }
    plural_mapping2 = {
        "seating": "сидячими",
        "first_class": "СВ",
        "econom": "плацкартными",
        "sleeping": "купейными",
        "luxury": "люксовыми"
    }

    singular_mapping = {
        "seating": "сидячий",
        "first_class": "СВ",
        "econom": "плацкартный",
        "sleeping": "купейный",
        "luxury": "люкс"
    }
    singular_mapping2 = {
        "seating": "сидячем",
        "first_class": "СВ",
        "econom": "плацкартном",
        "sleeping": "купейном",
        "luxury": "люксовом"
    }

    if form == 1:
        return plural_mapping[car_type]
    elif form == 2:
        return plural_mapping2[car_type]
    elif form == 3:
        return singular_mapping2[car_type]
    return singular_mapping[car_type]


def seat_type_to_human_str(seat_type: str, form=0):
    plural_mapping = {
        "upper": "верхние",
        "bottom": "нижние"
    }
    singular_mapping = {
        "upper": "верхний",
        "bottom": "нижний"
    }
    singular_mapping2 = {
        "upper": "верхнее",
        "bottom": "нижнее"
    }
    if form == 2:
        return plural_mapping[seat_type]
    elif form == 1:
        return singular_mapping2[seat_type]
    return singular_mapping[seat_type]


def expect_slots_and_choose_state_for_selecting_train(turn: RzdTurn):
    """Второй этап. Заполнение слотов для выбора поезда."""
    print(f"usr_object: {turn.user_object}")

    # Достаем все возможные слоты из объекта
    trains = turn.user_object.get("trains", None)
    car_type = turn.user_object.get("car_type", None)
    seat_type = turn.user_object.get("seat_type", None)

    print(f"car_type: {car_type}")
    print(f"seat_type: {seat_type}")

    if car_type and seat_type:
        filtered_trains = filter_trains(trains, car_type_to_rzd_type(car_type))
        if not filtered_trains:
            turn.response_text = f'К сожалению нет {car_type_to_human_str(car_type, form=2)} вагонов. ' \
                                 f'Давайте выберем вагон другого типа?'
            turn.suggests.extend(get_human_readable_existing_car_types(trains))
            turn.user_object["car_type"] = None
            turn.stage = "expect_car_type"
        else:
            selected_train = filtered_trains[0]

            response_str = f'Покупаем билет на поезд {selected_train["number"]} ' \
                           f'{selected_train["from"]} {selected_train["to"]} на {selected_train["time_start"]} ' \
                           f'местного времени, '
            if car_type in ['econom', 'sleeping']:
                response_str += f'{seat_type_to_human_str(seat_type, form=1)} место в ' \
                                f'{car_type_to_human_str(car_type, form=3)} вагоне. ' \
                                f'Все правильно?'
            else:
                response_str += f'{car_type_to_human_str(car_type)} вагон. ' \
                                f'Все правильно?'
            turn.response_text = response_str
            turn.stage = 'expect_after_selecting_train_slots_filled'
            turn.suggests.extend(['Да', 'Нет'])
            # Заполнили вторую часть

    if not car_type:
        turn.response_text = f'Какой хотите тип вагона?'
        turn.stage = 'expect_car_type'
        turn.suggests.extend(get_human_readable_existing_car_types(trains))
    elif car_type in ['econom', 'sleeping'] and not seat_type:
        # Для плацкартного и купейного вагона уточняем тип места
        turn.response_text = 'Верхнее или нижнее место?'
        turn.stage = 'expect_seat_type'
        turn.suggests.extend(['Верхнее', 'Нижнее'])

    print(f"next stage is: {turn.stage}")

    return turn


@csc.add_handler(priority=6, stages=['expect_all_train_data'], intents=['selecting_train'])
def expect_all_train_data(turn: RzdTurn):
    print("expect_all_train_data handler")

    forms = turn.forms['selecting_train']

    car_type = forms.get('car_type', None)
    seat_type = forms.get('seat_type', None)

    if car_type:
        turn.user_object['car_type'] = car_type
    if seat_type:
        turn.user_object['seat_type'] = seat_type

    turn = expect_slots_and_choose_state_for_selecting_train(turn)
    print(f"expect_all_train_data response_text: {turn.response_text}")
    print(f"expect_all_train_data stage: {turn.stage}")


@csc.add_handler(priority=6, stages=['expect_all_train_data', 'expect_car_type'], intents=['car_type_slot_filling'])
def expect_car_type(turn: RzdTurn):
    # Уточняем тип вагона
    print("expect_car_type handler")

    # Должен быть заполнен интент selecting_train и слот car_type
    forms = turn.forms.get('selecting_train', None) or turn.forms.get('car_type_slot_filling', None)
    car_type = forms.get('car_type', None)
    trains = turn.user_object.get("trains", None)

    if not car_type:
        # Переспрашиваем тип вагона
        turn.response_text = 'Какой хотите тип вагона?'
        # Оставляем тот же стейт
        turn.stage = 'expect_car_type'
        if trains:
            turn.suggests.extend(get_human_readable_existing_car_types(trains))
        else:
            turn.suggests.extend(['Плацкартный', 'Купейный', 'СВ', 'Сидячий'])
    elif trains and not car_type_to_human_str(car_type).capitalize() in get_human_readable_existing_car_types(trains):
        # Гооворим, что вагона заданного типа нет
        turn.response_text = f'К сожалению нет поездов с {car_type_to_human_str(car_type, form=2)} вагонами!' \
                             f'Выберем другой тип вагона?'
        # Оставляем тот же стейт
        turn.stage = 'expect_car_type'
        turn.suggests.extend(get_human_readable_existing_car_types(trains))
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['car_type'] = car_type
        turn = expect_slots_and_choose_state_for_selecting_train(turn)
        print(f"turn.response_text: {turn.response_text}")


@csc.add_handler(priority=6, stages=['expect_seat_type'], intents=['seat_type_slot_filling'])
def expect_seat_type(turn: RzdTurn):
    # Уточняем тип места
    print("expect_seat_type handler")

    # Должен быть заполнен интент selecting_train и слот car_type
    # turn.text, forms.get() or forms.get()
    forms = turn.forms.get('selecting_train', None) or turn.forms.get('seat_type_slot_filling', None)
    seat_type = forms.get('seat_type', None)
    car_type = turn.user_object.get('car_type', None)

    if car_type == 'first_class' or car_type == 'seating':
        turn.user_object['seat_type'] = 'нет'
    elif not seat_type:
        # Для плацкартного и купейного вагона уточняем тип места
        turn.response_text = 'Верхнее или нижнее место?'
        turn.stage = 'expect_seat_type'
        turn.suggests.extend(['Верхнее', 'Нижнее'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['seat_type'] = seat_type
        turn = expect_slots_and_choose_state_for_selecting_train(turn)
        print(f"turn.response_text: {turn.response_text}")


# @csc.add_handler(priority=6, stages=['expect_quantity'], intents=['tickets_quantity_slot_filling'])
# def expect_quantity(turn: RzdTurn):
#     # Уточняем количество билетов
#     print("expect_quantity handler")
#     # Должен быть заполнен интент selecting_train и слот car_type
#
#     forms = turn.forms.get('selecting_train', None) or turn.forms.get('tickets_quantity_slot_filling', None)
#     quantity = forms.get('quantity', None)
#
#     if quantity is None:
#         # Уточняем количество билетов
#         turn.response_text = 'Хотите купить один билет?'
#         # Оставляем тот же стейт
#         turn.stage = 'expect_quantity'
#         turn.suggests.extend(['Да', 'Один', 'Два'])
#     else:
#         # Получили недостающий слот со временем. Заполняем данные
#         turn.user_object['seat_type'] = quantity
#         turn = expect_slots_and_choose_state_for_selecting_train(turn)
#         print(f"turn.response_text: {turn.response_text}")