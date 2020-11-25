import tgalice
from tgalice.cascade import Cascade
from tgalice.dialog import Context
from tgalice.dialog_manager import BaseDialogManager
from tgalice.interfaces.yandex import extract_yandex_forms
from tgalice.nlu.basic_nlu import fast_normalize

from bot.turn import RzdTurn, csc
import bot.handlers  # noqa: the handlers are registered there


class RzdDialogManager(BaseDialogManager):
    def __init__(self, cascade: Cascade = None, **kwargs):
        super(RzdDialogManager, self).__init__(**kwargs)
        self.cascade = cascade or csc

    def respond(self, ctx: Context):
        forms = {}  # todo: extract our own forms with regexes
        if ctx.yandex:
            forms = extract_yandex_forms(ctx.yandex)
        intents = {intent_name: 1 for intent_name in forms}
        if tgalice.nlu.basic_nlu.like_help(ctx.message_text):
            intents['help'] = 1
        turn = RzdTurn(
            ctx=ctx,
            text=fast_normalize(ctx.message_text),
            intents=intents,
            forms=forms,
        )
        handler_name = self.cascade(turn)
        self.cascade.postprocess(turn)
        return turn.make_response()
