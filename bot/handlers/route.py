import tgalice

from bot.turn import RzdTurn, csc


def check_slots_and_chose_state(turn: RzdTurn):
    """Проверяем что заполнены все слоты. Если что-то не заполнено то выбираем какой заполнить."""
    print(turn.ctx.user_object)
    # Достаем все возможные слоты из объекта
    from_text = turn.ctx.user_object.get("from_text", None)
    to_text = turn.ctx.user_object.get("to_text", None)
    when_text = turn.ctx.user_object.get("when_text", None)

    if from_text and to_text and when_text:
        turn.response_text = f'Ищу билеты {from_text} {to_text} {when_text}. Все правильно?'
        turn.stage = 'expect_after_slots_filled'
        # На данном этапе полностью получены все слоты

    elif from_text and to_text:
        turn.response_text = f'Когда поедем {from_text} {to_text}?'
        turn.stage = 'expect_departure_time'
        turn.suggests.extend(['Завтра', 'Сегодня'])

    elif from_text and when_text:
        turn.response_text = f'Куда поедем {from_text} {when_text}?'
        turn.stage = 'expect_destination_place'
        turn.suggests.extend(['Петербург', 'Казань'])

    elif to_text and when_text:
        turn.response_text = f'Откуда поедем {to_text} {when_text}?'
        turn.stage = 'expect_departure_place'
        turn.suggests.extend(['Москва', 'Петербург'])

    else:
        turn.response_text = f'Давайте попробуем заново. Откуда и куда вы хотите билет?'
        turn.stage = 'expect_departure_place'
        turn.suggests.extend(['Москва', 'Петербург'])

    print(f"next stage is: {turn.stage}")

    return turn


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
        turn.ctx.user_object['from_text'] = from_text
    if to_text:
        turn.ctx.user_object['to_text'] = to_text
    if when_text:
        turn.ctx.user_object['when_text'] = when_text

    turn.ctx.user_object["from_text"] = "from_text"
    print(f"intercity_route turn: {turn.ctx.user_object['from_text']}")
    turn = check_slots_and_chose_state(turn)
    print(f"turn.response_text: {turn.response_text}")


@csc.add_handler(priority=9, stages=['expect_departure_time'], intents=['slots_filling'])
def expect_departure_time(turn: RzdTurn):
    print("expect_departure_time handler")

    # Должен быть заполнен интент slots_filing и слот when
    forms = turn.forms['slots_filing']
    when_text = forms.get('when', None)

    if not when_text:
        # Во время дозаполнения слота времени мы не получили данный слот. Переспрашиваем ещё раз
        turn.response_text = 'Назовите дату, на которую хотите посмотреть билет'
        # Оставляем тот же стейт
        turn.stage = 'expect_departure_time'
        turn.suggests.extend(['Завтра', 'Сегодня'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.ctx.user_object['when_text'] = when_text


@csc.add_handler(priority=8, stages=['expect_destination_place'], intents=['slots_filling'])
def expect_destination_place(turn: RzdTurn):
    # Уточняем место назначения
    print("expect_destination_place handler")

    # Должен быть заполнен интент slots_filing и слот to
    forms = turn.forms['slots_filing']
    to_text = forms.get('to', None)

    if not to_text:
        # Во время дозаполнения слота места назначения мы не получили данный слот. Переспрашиваем ещё раз
        turn.response_text = 'Назовите конечный пункт куда вы держите путь'
        # Оставляем тот же стейт
        turn.stage = 'expect_destination_place'
        turn.suggests.extend(['Москва', 'Петербург'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.ctx.user_object['to_text'] = to_text


@csc.add_handler(priority=7, stages=['expect_departure_place'], intents=['slots_filling'])
def expect_departure_place(turn: RzdTurn):
    # Уточняем место отправления
    print("expect_departure_place handler")

    # Должен быть заполнен интент slots_filing и слот from
    forms = turn.forms['slots_filing']
    from_text = forms.get('from', None)

    if not from_text:
        # Во время дозаполнения слота места отправления мы не получили данный слот. Переспрашиваем ещё раз
        turn.response_text = 'Назовите, откуда вы собираетесь выезжать'
        # Оставляем тот же стейт
        turn.stage = 'expect_departure_place'
        turn.suggests.extend(['Москва', 'Петербург'])
    else:
        # Получили недостающий слот со временем. Заполняем данные
        turn.ctx.user_object['from_text'] = from_text
