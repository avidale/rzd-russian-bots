import tgalice

from bot.turn import RzdTurn, csc
from utils.date_convertor import convert_date_to_abs, date2ru
from utils.morph import with_number


def check_slots_and_chose_state(turn: RzdTurn):
    """Проверяем что заполнены все слоты. Если что-то не заполнено то выбираем какой заполнить."""
    # Достаем все возможные слоты из объекта
    from_text = turn.user_object.get("from_text", None)
    to_text = turn.user_object.get("to_text", None)
    when_text = turn.user_object.get("when_text", None)

    if from_text and to_text and when_text:
        turn.response_text = f'Ищу билеты {from_text} {to_text} {when_text}. Все правильно?'
        next_stage = 'expect_after_slots_filled'
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


def get_trains():
    """Формирование результата, полученного через API."""
    api_response = [
            {
                "seat_type": "Плацкарт",
                "from": "",
                "to": "",
                "from_station": "",
                "to_station": "",
                "number": "",
                "time_start": "2020-12-01 16:30",
                "time_end": "2020-12-04 19:30",
                "duration": "30:80",
                "cost": "3500"
            },
            {
                "seat_type": "Купе",
                "time_start": "2020-12-01 16:30",
                "time_end": "2020-12-04 19:30",
                "duration": "10800",
                "cost": "5000"
            }
    ]
    return api_response


@csc.add_handler(priority=30, stages=['expect_after_slots_filled'], intents=['yes', 'no'])
def expect_after_slots_filled(turn: RzdTurn):
    if 'yes' in turn.intents:
        # Дождались положительного ответа от пользователя после формирования полного запроса
        # Достаем результат
        api_response = get_trains()
        turn.user_object['trains'] = api_response

        for train in api_response["trains"]:
            print(train)

        print(f"intents: {turn.intents}")
        turn.response_text = 'Найдено несколько поездов. Какого тип вагона и места вы хотите?'
        turn.stage = 'expect_all_train_data'
        turn.suggests.extend(['Один билет в плацкартный вагон', 'Два билета в купе'])

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
    if to_text:
        turn.user_object['to_text'] = to_text
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
        turn = check_slots_and_chose_state(turn)
        print(f"turn.response_text: {turn.response_text}")






def expect_slots_and_choose_state_for_selecting_train(turn: RzdTurn):
    """Второй этап. Заполнение слотов для выбора поезда."""
    print(turn.user_object)
    # Достаем все возможные слоты из объекта
    car_type = turn.user_object.get("car_type", None)
    seat_type = turn.user_object.get("seat_type", None)
    quantity = turn.user_object.get("quantity", None)
    print(f"car_type: {car_type}")
    print(f"seat_type: {seat_type}")
    print(f"quantity: {quantity}")

    if car_type and seat_type and quantity:
        turn.response_text = f'Покупаем {with_number("билет", quantity)} в {car_type} вагон, {seat_type} мест. ' \
                             f'Все правильно?'
        turn.stage = 'expect_after_selecting_train_slots_filled'
        turn.suggests.extend(['Да', 'Нет'])
    if not car_type:
        turn.response_text = f'Какой хотите тип вагона?'
        turn.stage = 'expect_car_type'
        turn.suggests.extend(['Плацкартный', 'Купейный', 'СВ', 'Сидячий'])
    elif car_type != 'св' and car_type != 'сидячий' and not seat_type:
        # Для плацкартного и купейного вагона уточняем тип места
        turn.response_text = 'Хотите верхнее место?'
        turn.stage = 'expect_seat_type'
        turn.suggests.extend(['Верхнее', 'Нижнее'])
    elif not quantity:
        # Уточняем количество билетов
        turn.response_text = 'Сколько билетов вы хотите купить?'
        turn.stage = 'expect_quantity'
        turn.suggests.extend(['Один', 'Два', 'Три'])

    print(f"next stage is: {turn.stage}")

    return turn

@csc.add_handler(priority=6, stages=['expect_all_train_data'])
def expect_all_train_data(turn: RzdTurn):
    forms = turn.forms['selecting_train']

    car_type = forms.get('car_type', None)
    seat_type = forms.get('seat_type', None)
    quantity = forms.get('quantity', None)

    if car_type:
        turn.user_object['car_type'] = car_type
    if seat_type:
        turn.user_object['seat_type'] = seat_type
    if quantity:
        turn.user_object['quantity'] = quantity

    turn = expect_slots_and_choose_state_for_selecting_train(turn)
    print(f"expect_all_train_data response_text: {turn.response_text}")
    print(f"expect_all_train_data stage: {turn.stage}")


@csc.add_handler(priority=6, stages=['expect_car_type'], intents=['car_type_slot_filling'])
def expect_car_type(turn: RzdTurn):
    # Уточняем тип вагоне
    print("expect_car_type handler")

    # Должен быть заполнен интент selecting_train и слот car_type
    forms = turn.forms.get('selecting_train', None) or turn.forms.get('car_type_slot_filling', None)
    car_type = forms.get('car_type', None)

    if not car_type:
        # Переспрашиваем тип вагона
        turn.response_text = 'Какой хотите тип вагона?'
        # Оставляем тот же стейт
        turn.stage = 'expect_car_type'
        turn.suggests.extend(['Плацкартный', 'Купейный', 'СВ', 'Сидячий'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['car_type'] = car_type
        turn = expect_slots_and_choose_state_for_selecting_train(turn)


@csc.add_handler(priority=6, stages=['expect_seat_type'], intents=['seat_type_slot_filling'])
def expect_seat_type(turn: RzdTurn):
    # Уточняем тип места
    print("expect_seat_type handler")

    # Должен быть заполнен интент selecting_train и слот car_type
    # turn.text, forms.get() or forms.get()
    forms = turn.forms.get('selecting_train', None) or turn.forms.get('seat_type_slot_filling', None)
    seat_type = forms.get('seat_type', None)
    car_type = turn.user_object.get('car_type', None)

    if car_type == 'св' or car_type == 'сидячий':
        turn.user_object['seat_type'] = 'нет'
    elif not seat_type:
        # Для плацкартного и купейного вагона уточняем тип места
        turn.response_text = 'Хотите верхнее место?'
        # Оставляем тот же стейт
        turn.stage = 'expect_seat_type'
        turn.suggests.extend(['Верхнее', 'Нижнее'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['seat_type'] = seat_type
        turn = expect_slots_and_choose_state_for_selecting_train(turn)


@csc.add_handler(priority=6, stages=['expect_quantity'], intents=['tickets_quantity_slot_filling'])
def expect_quantity(turn: RzdTurn):
    # Уточняем количество билетов
    print("expect_quantity handler")
    # Должен быть заполнен интент selecting_train и слот car_type

    forms = turn.forms.get('selecting_train', None) or turn.forms.get('tickets_quantity_slot_filling', None)
    quantity = forms.get('quantity', None)

    if quantity is None:
        # Уточняем количество билетов
        turn.response_text = 'Хотите купить один билет?'
        # Оставляем тот же стейт
        turn.stage = 'expect_quantity'
        turn.suggests.extend(['Да', 'Один', 'Два'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.user_object['seat_type'] = quantity
        turn = expect_slots_and_choose_state_for_selecting_train(turn)
