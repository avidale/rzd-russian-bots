import tgalice

from api.rzd_basic import suggest_first_station, find_route, init_find_route, request_find_route_result
from api.rzd_basic import time_tag_attribution, TIME_MAPPING, filter_trains_by_time_tags
from bot.turn import RzdTurn, csc
from utils.date_convertor import convert_date_to_abs, date2ru
from utils.morph import with_number


def filter_trains_by_rzd_car_type(trains: list, rzd_car_type: str):
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
    print(f"intents: {turn.intents}")

    if 'yes' in turn.intents:
        # Дождались положительного ответа от пользователя после формирования полного запроса
        # Достаем результат
        trains = get_trains(turn)
        turn.user_object['trains'] = trains

        print("Trains received after API request")
        for train in trains:
            print(train)

        # Атрибуцируем тег времени для
        trains, time_tags = time_tag_attribution(trains)
        print(f"Trains with time tags:\n{trains}")
        print(trains)

        # Проверяем, что тегов больше одного. Уточняем время дня
        if len(time_tags) > 1:
            tag_names = [TIME_MAPPING[tag] for tag in time_tags]
            time_tags_str = ", ".join(tag_names)
            turn.response_text = f'Есть поезда на {time_tags_str}. Когда желаете отправиться?'
            turn.stage = 'expect_departure_time_tag'
            turn.suggests.extend(tag_names)
        else:
            # Не даем выбрать время, потому что выбора нет
            extracted_prices = extract_min_max_prices_for_car_types(trains)
            prices_information_str = extracted_prices_to_information_str(extracted_prices)
            turn.response_text = f'Найдено несколько поездов. Какое место хотите?\n\n{prices_information_str}'
            turn.stage = 'expect_all_train_data'
            turn.suggests.extend(['Верхнее место в плацкартном вагоне', 'Нижнее место в купе'])
    else:
        turn.response_text = f'К сожалению, я ничего не нашла. Давайте попробуем заново'


@csc.add_handler(priority=30, stages=['expect_after_slots_filled', 'expect_departure_time_tag'], intents=['time_tags'])
def expect_departure_time_tag(turn: RzdTurn):
    print("expect_departure_time_tag handler")
    print(f"intents: {turn.intents}")

    forms = turn.forms['time_tags']
    time_tags = forms.keys()

    source_trains = turn.user_object['trains']
    filtered_trains = filter_trains_by_time_tags(source_trains, time_tags)

    print(f"Filtered trains by time tags: {filtered_trains}")

    if len(filtered_trains) == 0:
        extracted_prices = extract_min_max_prices_for_car_types(source_trains)
        prices_information_str = extracted_prices_to_information_str(extracted_prices)

        # Если на нужное время дня нет билетов то говорим об этом и предлагаем соазу выбирать тип вагона и места
        turn.response_text = f'К сожалению, на выбранное время дня нет билетов. ' \
                             f'Давайте выберем место в найденных билетах?\n\n{prices_information_str}'
        turn.stage = 'expect_all_train_data'

        rzd_car_types = get_human_readable_existing_car_types(source_trains)
        if rzd_car_types:
            turn.suggests.extend(create_suggestions_for_car_types(rzd_car_types))
        else:
            turn.suggests.extend(['Верхнее место в плацкарте', 'Нижнее место в купе'])
    else:
        extracted_prices = extract_min_max_prices_for_car_types(filtered_trains)
        prices_information_str = extracted_prices_to_information_str(extracted_prices)

        # Теперь в юзерстейте лежат отфильтрованные по времени билеты
        turn.user_object['trains'] = filtered_trains
        # Переходим к выбору типа вагона и мест
        turn.response_text = f'{prices_information_str}\nКакое место хотите?'
        turn.stage = 'expect_all_train_data'

        rzd_car_types = get_human_readable_existing_car_types(filtered_trains)
        if rzd_car_types:
            turn.suggests.extend(create_suggestions_for_car_types(rzd_car_types))
        else:
            turn.suggests.extend(['Верхнее место в плацкарте', 'Нижнее место в купе'])


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
    """Получение списка человеко-читаемых типов вагонов."""
    existing_car_types = set(train['seat_type'] for train in trains)
    return [car_type.capitalize() for car_type in existing_car_types]


def car_type_to_rzd_type(car_type):
    """Перевод типа вагона из грамматики в тип вагона в RZD API."""
    mapping = {
        "seating": "Сидячий",
        "first_class": "СВ",
        "econom": "Плацкартный",
        "sleeping": "Купе",
        "luxury": "Люкс"
    }
    return mapping[car_type]


def create_suggestions_for_car_types(rzd_car_types):
    """Формирования списка предложения по списку типов доступных поездов."""
    suggestions = []
    if "Купе" in rzd_car_types:
        suggestions.append("Нижнее место в купе")
    if "Плацкартный" in rzd_car_types:
        suggestions.append("Верхнее место в плацкарте")
    if "Сидячий" in rzd_car_types:
        suggestions.append("Сидячее место")
    if "СВ" in rzd_car_types:
        suggestions.append("Св")
    if "Люкс" in rzd_car_types:
        suggestions.append("Люкс")
    return suggestions


def extract_min_max_prices_for_car_types(trains):
    """Формирование словаря с минимальными ценами в зависимости от типа вагона.
    Ключ - тип вагона, значение - вложенный словарь с ключами min и max, значения - соответственно
    минимальная и максимальная цены на места данного типа."""
    result = {}
    for train in trains:
        car_type = train["seat_type"]
        cost = train["cost"]
        if car_type in result:
            if result[car_type]["min"] > cost:
                result[car_type]["min"] = cost
            elif result[car_type]["max"] < cost:
                result[car_type]["max"] = cost
        else:
            result[car_type] = {"min": train["cost"], "max": train["cost"]}

    print(f"Extracted min and max prices: {result}")
    return result


def extracted_prices_to_information_str(extracted_prices_dict):
    """Формирование информационной строки с минимальными и максимальными ценами по каждому типу ввагонов
    на основе словаря."""
    result = ""
    for rzd_car_type, costs in extracted_prices_dict.items():
        result += f"{rzd_car_type}:   {costs['min']} - {costs['max']} руб.\n"
    return result


def car_type_to_human_str(car_type: str, form=0):
    """Перевод типа вагона в человеко-читаемый вид с учетом склонения."""
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
    plural_mapping3 = {
        "seating": "сидячих",
        "first_class": "СВ",
        "econom": "плацкартных",
        "sleeping": "купейных",
        "luxury": "люксовых"
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
    elif form == 4:
        return plural_mapping2[car_type]
    return singular_mapping[car_type]


def seat_type_to_human_str(seat_type: str, form=0):
    """Перевод типа места в человеко-читаемый вид с учетом склонения."""
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

    if car_type and (seat_type or car_type not in ['econom', 'sleeping']):
        filtered_trains = filter_trains_by_rzd_car_type(trains, car_type_to_rzd_type(car_type))
        if not filtered_trains:
            turn.response_text = f'К сожалению нет поездов с {car_type_to_human_str(car_type, form=2)} вагонами ' \
                                 f'на указанное время.\n' \
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
                                f'{car_type_to_human_str(car_type, form=3)} вагоне. '
            else:
                response_str += f'{car_type_to_human_str(car_type)} вагон. '
            response_str += f'\nЦена {selected_train["cost"]} руб.\nВсе правильно?'

            turn.response_text = response_str
            turn.stage = 'expect_after_selecting_train_slots_filled'
            turn.suggests.extend(['Да', 'Нет'])
            # Заполнили вторую часть

    if not car_type:
        extracted_prices = extract_min_max_prices_for_car_types(trains)
        prices_information_str = extracted_prices_to_information_str(extracted_prices)
        turn.response_text = f'{prices_information_str}\nКакой хотите тип вагона?'
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

    prices_information_str = ""
    if trains:
        extracted_prices = extract_min_max_prices_for_car_types(trains)
        prices_information_str = extracted_prices_to_information_str(extracted_prices)

    if not car_type:
        # Переспрашиваем тип вагона

        turn.response_text = f'{prices_information_str}Какой хотите тип вагона?'
        # Оставляем тот же стейт
        turn.stage = 'expect_car_type'
        if trains:
            turn.suggests.extend(get_human_readable_existing_car_types(trains))
        else:
            turn.suggests.extend(['Плацкартный', 'Купейный', 'СВ', 'Сидячий'])
    elif trains and not car_type_to_human_str(car_type).capitalize() in get_human_readable_existing_car_types(trains):
        # Гооворим, что вагона заданного типа нет
        turn.response_text = f'К сожалению нет поездов с {car_type_to_human_str(car_type, form=2)} вагонами ' \
                             f'на указанное время! ' \
                             f'Выберем другой тип вагона? \n{prices_information_str}'
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

