from api.rzd_basic import suggest_first_station, init_find_route, request_find_route_result, \
    car_type_to_rzd_type, create_suggestions_for_car_types, extract_min_max_prices_for_car_types, \
    extracted_prices_to_information_str
from api.rzd_basic import time_tag_attribution, TIME_MAPPING, filter_trains_by_time_tags, filter_trains_by_rzd_car_type
from bot.turn import RzdTurn, csc
from utils.date_convertor import convert_date_to_abs, date2ru
from utils.human_converters import get_human_readable_existing_car_types, car_type_to_human_str, seat_type_to_human_str
from utils.morph import convert_geo_to_normalized_city

from tgalice.dialog import Response
from tgalice.nlg.controls import BigImage


def check_slots_and_chose_state(turn: RzdTurn):
    """Проверяем что заполнены все слоты. Если что-то не заполнено то выбираем какой заполнить."""
    # Достаем все возможные слоты из объекта
    from_text = turn.user_object.get("from_text", None)
    to_text = turn.user_object.get("to_text", None)
    when_text = turn.user_object.get("when_text", None)

    if from_text and to_text and when_text:
        turn.response_text = f'Ищу билеты по маршруту {from_text} - {to_text} {when_text}. Все правильно?'
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
        turn.response_text = f'Когда поедем по маршруту {from_text} - {to_text}?'
        next_stage = 'expect_departure_time'
        turn.suggests.extend(['Завтра', 'Сегодня'])

    elif from_text and when_text:
        turn.response_text = f'Куда поедем'
        next_stage = 'expect_destination_place'
        turn.suggests.extend(['Петербург', 'Казань'])

    elif to_text and when_text:
        turn.response_text = f'Откуда поедем?'
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

    print(f"when_text: {when_text}")

    if from_text:
        from_text = convert_geo_to_normalized_city(from_text)
        turn.user_object['from_text'] = from_text
        turn.user_object['from_id'] = suggest_first_station(from_text)
    if to_text:
        to_text = convert_geo_to_normalized_city(to_text)
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
        # Получили недостающий слот с местом назначения. Заполняем данные
        to_text = convert_geo_to_normalized_city(to_text)
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
        # Получили недостающий слот с местом отправления. Заполняем данные
        from_text = convert_geo_to_normalized_city(from_text)
        turn.user_object['from_text'] = from_text
        turn.user_object['from_id'] = suggest_first_station(from_text)
        turn = check_slots_and_chose_state(turn)
        print(f"turn.response_text: {turn.response_text}")


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
            turn.user_object["selected_train"] = selected_train

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
                             f'Выберем другой тип вагона?\n\n{prices_information_str}'
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


@csc.add_handler(priority=30, stages=['expect_after_selecting_train_slots_filled'], intents=['yes', 'no'])
def expect_after_selecting_train_slots_filled(turn: RzdTurn):
    print("expect_after_selecting_train_slots_filled handler")
    print(f"intents: {turn.intents}")

    # TODO разобраться и поправить с учетом адреса картинки
    if 'yes' in turn.intents:
        selected_train = turn.user_object["selected_train"]
        cost = selected_train["cost"]
        from_location = selected_train["from"]
        to_location = selected_train["to"]
        url = f'https://rzd-skill.herokuapp.com/qr/?f={from_location}&t={to_location}'
        text = f'Отлично! Вы купили билет на поезд. С вашей карты будет списано {cost} руб.'
        turn.response = Response(
            image=BigImage(
                image_id='213044/4e2dacacedfb7029f89e',
                button_text='Скачать билет',
                button_url=url,
                description=text,
            ),
            text='',  # voice='*',
            rich_text=text,
        )
    else:
        turn.response_text = f'К сожалению, я ничего не нашла. Давайте попробуем заново'

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

