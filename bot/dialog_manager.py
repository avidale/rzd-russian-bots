import logging
import os
import regex
import tgalice
from tgalice.cascade import Cascade
from tgalice.dialog import Context
from tgalice.dialog_manager import BaseDialogManager
from tgalice.interfaces.yandex import extract_yandex_forms
from tgalice.nlu.basic_nlu import fast_normalize
from tgalice.nlu.regex_expander import load_intents_with_replacement

from api.rasp import RaspSearcher, StationMatcher
from bot.turn import RzdTurn, csc
import bot.handlers  # noqa
import bot.handlers.route  # noqa: the handlers are registered there
from utils.re_utils import match_forms, compile_intents_re


logger = logging.getLogger(__name__)


class RzdDialogManager(BaseDialogManager):
    def __init__(self, cascade: Cascade = None, rasp_api=None, **kwargs):
        super(RzdDialogManager, self).__init__(**kwargs)
        self.cascade = cascade or csc

        logger.debug('loading intents..')

        self.intents = load_intents_with_replacement(
            intents_fn='config/intents.yaml',
            expressions_fn='config/expressions.yaml',
        )
        compile_intents_re(self.intents)
        logger.debug('loading world..')
        self.rasp_api = rasp_api or RaspSearcher()
        self.world: StationMatcher = StationMatcher(self.rasp_api.get_world())
        logger.debug('the world loaded.')

    def respond(self, ctx: Context):
        text, forms, intents = self.nlu(ctx)
        turn = RzdTurn(
            ctx=ctx,
            text=text,
            intents=intents,
            forms=forms,
            user_object=ctx.user_object,
            rasp_api=self.rasp_api,
            world=self.world,
        )
        logger.debug(f'current stage is: {turn.stage}')
        handler_name = self.cascade(turn)
        print(f"Handler name: {handler_name}")
        self.cascade.postprocess(turn)
        print()
        return turn.make_response()

    def update_forms(self, forms, text):
        """В зависимости от предлога, найденного в тексте, исправляем сущности яндекса для слотов to и from."""
        from_preps = ["от", "из", "с"]
        to_preps = ["в", "до", "на", "к"]
        try:
            updated_forms = forms
            geo_intents = ["intercity_route", "slots_filling"]
            for intent in forms:
                if intent in geo_intents:
                    # Если только одно гео определилось в интенте
                    if ('to' in forms[intent] and 'from' not in forms[intent]) or \
                            ('to' not in forms[intent] and 'from' in forms[intent]):
                        par = 'to' if 'to' in forms[intent] else 'from'
                        content = forms[intent][par]
                        if any([p in to_preps for p in text.split()]):
                            forms[intent]["to"] = content
                            if "from" in forms[intent]:
                                del forms[intent]["from"]
                        elif any([p in from_preps for p in text.split()]):
                            forms[intent]["from"] = content
                            if "to" in forms[intent]:
                                del forms[intent]["to"]
        except Exception:
            return forms
        else:
            return updated_forms

    def nlu(self, ctx):
        text = fast_normalize(ctx.message_text or '')
        forms = match_forms(text=text, intents=self.intents)
        if ctx.yandex:
            ya_forms = extract_yandex_forms(ctx.yandex)
            forms.update(ya_forms)

        print(f"Extracted forms: {forms}")
        forms = self.update_forms(forms, ctx.message_text)
        print(f"Updated forms: {forms}")

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
