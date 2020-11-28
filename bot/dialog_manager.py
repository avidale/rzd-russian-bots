import regex
import tgalice
from tgalice.cascade import Cascade
from tgalice.dialog import Context
from tgalice.dialog_manager import BaseDialogManager
from tgalice.interfaces.yandex import extract_yandex_forms
from tgalice.nlu.basic_nlu import fast_normalize
from tgalice.nlu.regex_expander import load_intents_with_replacement

from bot.turn import RzdTurn, csc
import bot.handlers.route  # noqa: the handlers are registered there


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
        forms = self.match_forms(text)

        if ctx.yandex:
            ya_forms = extract_yandex_forms(ctx.yandex)
            forms.update(ya_forms)
        intents = {intent_name: 1 for intent_name in forms}

        if tgalice.nlu.basic_nlu.like_help(ctx.message_text):
            intents['help'] = 1
        if tgalice.nlu.basic_nlu.like_yes(ctx.message_text):
            intents['yes'] = 1
        if tgalice.nlu.basic_nlu.like_no(ctx.message_text):
            intents['no'] = 1

        print(f"Intents: {intents}")
        print(f"Forms: {forms}")
        return text, forms, intents

    def match_forms(self, text):
        forms = {}
        for intent_name, intent_value in self.intents.items():
            if 'regexp' in intent_value:
                exps = intent_value['regexp']
                if isinstance(exps, str):
                    exps = [exps]
                for exp in exps:
                    match = regex.match(exp, text)
                    if match:
                        forms[intent_name] = match.groupdict()
                        break
        return forms
