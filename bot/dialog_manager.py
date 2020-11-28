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

from api.rasp import RaspSearcher
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
        self.intents = {}
        # self.intents = load_intents_with_replacement(
        #     intents_fn='config/intents.yaml',
        #     expressions_fn='config/expressions.yaml',
        # )
        
        if os.getenv('PRECOMPILE_REGEX'):
            compile_intents_re(self.intents)
        logger.debug('loading world..')
        self.rasp_api = rasp_api or RaspSearcher()
        self.world = self.rasp_api.get_world()
        self.code2obj = {}
        for t, d in self.world.items():
            for o in d:
                self.code2obj[o['yandex_code']] = o
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
            world=self.code2obj,
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
        if tgalice.nlu.basic_nlu.like_yes(ctx.message_text):
            intents['yes'] = 1
        if tgalice.nlu.basic_nlu.like_no(ctx.message_text):
            intents['no'] = 1

        print(f"Intents: {intents}")
        print(f"Forms: {forms}")
        return text, forms, intents
