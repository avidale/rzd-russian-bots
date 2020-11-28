from typing import Dict

import regex


def drop_none(d):
    return {k: v for k, v in d.items() if v is not None}


def compile_intents_re(intents):
    for intent_value in intents.values():
        if 'regexp' in intent_value:
            exps = intent_value['regexp']
            if isinstance(exps, str):
                exps = [exps]
            intent_value['regexp'] = [regex.compile(v) for v in exps]


def match_forms(text: str, intents: dict) -> Dict[str, Dict]:
    forms = {}
    for intent_name, intent_value in intents.items():
        if 'regexp' in intent_value:
            exps = intent_value['regexp']
            if isinstance(exps, str):
                exps = [exps]
            for exp in exps:
                match = regex.match(exp, text)
                if match:
                    forms[intent_name] = drop_none(match.groupdict())
                    break
    return forms
