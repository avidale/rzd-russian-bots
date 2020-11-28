from collections import defaultdict

from tgalice.dialog import Response
from tgalice.nlg.controls import BigImage

from api.cppk import get_cppk_cost
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

        cost = get_cppk_cost(from_text=ft, to_text=tt, date=None, return_price=True)

        turn.response_text = phrase_results(
            name_from=from_norm,
            name_to=to_norm,
            results=result,
            only_next=True,
            from_meta=turn.world.get(fn),
        )
        if cost and segments:
            turn.response_text += f' Стоимость {cost} рублей. Желаете купить билет?'
            turn.stage = 'confirm_sell_suburb'
            turn.suggests.append('Да')

            turn.user_object['suburb_transaction'] = {
                'from_text': from_norm,
                'to_text': to_norm,
                'price': cost or 100,
            }
        return
    elif not fn:
        turn.response_text = 'Не поняла, откуда вы хотите поехать. Можете назвать ещё раз?'
    elif not tn:
        turn.response_text = 'Не поняла, куда вы хотите поехать. Можете назвать ещё раз?'
    else:
        turn.response_text = 'Это какая-то невозможная ветка диалога'


@csc.add_handler(priority=100, intents=['yes', 'confirm_purchase'], stages=['confirm_sell_suburb'])
def suburb_confirm_purchase(turn: RzdTurn):
    # todo: fill
    tran = turn.user_object['suburb_transaction']
    p = int(tran["price"])
    url = f'https://rzd-skill.herokuapp.com/qr/?f={tran["from_text"]}&t={tran["to_text"]}'
    text = f'Отлично! Продаю вам билет на электричку. С вашей карты будет списано {p} рублей.'
    turn.response = Response(
        image=BigImage(
            image_id='213044/4e2dacacedfb7029f89e',
            button_text='Скачать билет',
            button_url=url,
            description=text,
        ),
        text='',  # voice='*',
        rich_text=text,
    )
