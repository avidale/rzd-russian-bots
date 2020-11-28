import regex
import tgalice
from tgalice.cascade import Cascade
from tgalice.dialog import Context
from tgalice.dialog_manager import BaseDialogManager
from tgalice.interfaces.yandex import extract_yandex_forms
from tgalice.nlu.basic_nlu import fast_normalize
from tgalice.nlu.regex_expander import load_intents_with_replacement

from bot.turn import RzdTurn, csc
import bot.handlers  # noqa
import bot.handlers.route  # noqa: the handlers are registered there
from utils.re_utils import match_forms


class RzdDialogManager(BaseDialogManager):
    def __init__(self, cascade: Cascade = None, **kwargs):
        super(RzdDialogManager, self).__init__(**kwargs)
        self.cascade = cascade or csc

        self.intents = load_intents_with_replacement(
            intents_fn='config/intents.yaml',
            expressions_fn='config/expressions.yaml',
        )

    def respond(self, ctx: Context):
        text, forms, intents = self.nlu(ctx)
        turn = RzdTurn(
            ctx=ctx,
            text=text,
            intents=intents,
            forms=forms,
            user_object=ctx.user_object,
        )
        handler_name = self.cascade(turn)
        print(f"Handler name: {handler_name}")
        self.cascade.postprocess(turn)
        print()
        return turn.make_response()

    def nlu(self, ctx):
        text = fast_normalize(ctx.message_text or '')
        forms = match_forms(text=text, intents=self.intents)
        if ctx.yandex:
            ya_forms = extract_yandex_forms(ctx.yandex)
            forms.update(ya_forms)
        intents = {intent_name: 1 for intent_name in forms}
        if tgalice.nlu.basic_nlu.like_help(ctx.message_text):
            intents['help'] = 1

        print(f"Intents: {intents}")
        print(f"Forms: {forms}")
        return text, forms, intents
