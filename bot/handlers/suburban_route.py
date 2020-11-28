from collections import defaultdict

from bot.nlg.suburban import phrase_results
from bot.turn import csc, RzdTurn


def extract_slot_with_code(slot, form, inverse, prefix='s'):
    value = None, None
    text = form.get(slot)
    if not text:
        return text, value
    for v in inverse[text]:
        if v.startswith(prefix) and v[1].isnumeric():
            value = v
            break
    return text, value


@csc.add_handler(priority=10, intents=['suburb_route'])
def suburb_route(turn: RzdTurn, force=False):
    form = turn.forms.get('suburb_route')
    # найди электрички от сколково до беговой turns to
    # {'suburb': 'электрички', 'from': 'беговой', 's9602218': 'сколково', 's9601666': 'беговой', 'to': 'сколково'}}
    if not form:
        return
    if not form.get('suburb') and 'intercity_route' in turn.forms and not force:
        # we give higher priority to intercity_route
        return
    text2slots = defaultdict(set)
    for k, v in form.items():
        text2slots[v].add(k)
    ft, fn = extract_slot_with_code('from', form, text2slots)
    tt, tn = extract_slot_with_code('to', form, text2slots)

    if fn and tn:
        result = turn.rasp_api.suburban_trains_between(code_from=fn, code_to=tn)
        segments = result['segments']
        search = result['search']
        from_norm = search['from']['title']
        to_norm = search['to']['title']
        # todo: pass timezone
        print(segments[0])
        turn.response_text = phrase_results(
            name_from=from_norm,
            name_to=to_norm,
            results=result,
            only_next=True,
        )
        return

    turn.response_text = f'Вы хотите поехать на электричке от {ft} до {tt}, верно?'.format()
    turn.suggests.append('да')
