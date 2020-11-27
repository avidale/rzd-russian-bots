import tgalice

from bot.turn import RzdTurn, csc


@csc.add_handler(priority=10, intents=['route_to'])
def route_to(turn: RzdTurn):
    # from_text = turn.ctx.yandex.request.nlu.intents['route_from_to'].slots['from']
    to_text = turn.forms['route_to']['to']
    turn.ctx.user_object['to_text'] = to_text
    # todo: make help dependent on turn.text and maybe some context
    from_text = turn.ctx.user_object.get('from_text')
    if from_text:
        turn.response_text = f'Когда поедем из {from_text} в {to_text}?'
        turn.stage = 'expect_departure_time'
        turn.suggests.extend(['Сегодня', 'Завтра'])
    else:
        turn.response_text = f'Откуда вы хотите поехать в {to_text}?'
        turn.stage = 'expect_departure_point'
        turn.suggests.append('Из Москвы')


@csc.add_handler(priority=10, stages=['expect_departure_point'])
def expect_departure_point(turn: RzdTurn):
    pass
