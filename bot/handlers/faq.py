import tgalice

from bot.turn import RzdTurn, csc, TRANSIENT_SLOTS


def is_first_session(turn: RzdTurn) -> bool:
    if turn.ctx.session_is_new():
        return True
    if turn.ctx.source == tgalice.SOURCES.TEXT and not turn.ctx.message_text:
        return True
    if turn.ctx.message_text == '/start':
        return True
    return False


@csc.add_handler(priority=1000, checker=is_first_session)
def greeting_handler(turn: RzdTurn):
    turn.response_text = 'Привет! Это навык РЖД. Здесь вы можете найти и заказать билеты на поезд.' \
                         'Чтобы выйти из навыка, скажите "Хватит".'
    turn.suggests.append('Помощь')

    for slot in TRANSIENT_SLOTS:
        if slot in turn.user_object:
            del turn.user_object[slot]


@csc.add_handler(priority=1, intents=['help', 'YANDEX.HELP'])
def help_handler(turn: RzdTurn):
    # todo: make help dependent on turn.text and maybe some context
    turn.response_text = 'Это навык РЖД. Здесь вы можете найти и заказать билеты на поиск.' \
                         'Чтобы выйти из навыка, скажите "Хватит".'
    turn.suggests.append('Хватит')


@csc.add_handler(priority=0)
def fallback(turn: RzdTurn):
    turn.response_text = 'Простите, я вас не понимаю.'
    turn.suggests.append('Помощь')
