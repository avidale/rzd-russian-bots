from datetime import datetime
from pytz import timezone

import attr
import logging

from collections import defaultdict

from tgalice.dialog import Response
from tgalice.nlg.controls import BigImage
from tgalice.utils.serialization import Serializeable

from api.cppk import get_cppk_cost
from bot.nlg.suburban import phrase_results
from bot.turn import csc, RzdTurn
from utils.date_convertor import convert_date_to_abs, local_now

logger = logging.getLogger(__name__)


def extract_slot_with_code(slot, form, inverse, prefix='s'):
    value = None
    text = form.get(slot)
    if not text:
        return text, value
    for v in inverse[text]:
        if v.startswith(prefix) and v[1].isnumeric():
            value = v
            break
    return text, value


@attr.s
class SuburbContext(Serializeable):
    from_text: str = attr.ib(default=None)
    from_code: str = attr.ib(default=None)
    to_text: str = attr.ib(default=None)
    to_code: str = attr.ib(default=None)
    date_txt: str = attr.ib(default=None)
    time_txt: str = attr.ib(default=None)
    cost: int = attr.ib(default=None)


@csc.add_handler(priority=5, intents=['suburb_route'])
@csc.add_handler(priority=20, intents=['suburb_route', 'suburb_ellipsis'], stages=['suburb_no_price'])
@csc.add_handler(priority=30, intents=['suburb_route', 'suburb_ellipsis'],
                 stages=['suburb_get_from', 'suburb_get_to', 'suburb_confirm_sell'])
def suburb_route(turn: RzdTurn, force=False):
    form = turn.forms.get('suburb_route') or turn.forms.get('suburb_ellipsis')
    # найди электрички от сколково до беговой turns to
    # {'suburb': 'электрички', 'from': 'беговой', 's9602218': 'сколково', 's9601666': 'беговой', 'to': 'сколково'}}
    sub = SuburbContext.from_dict(turn.user_object.get('suburb') or {})
    suburb_stage = (turn.stage or '').startswith('suburb')
    if not form:
        if suburb_stage:
            turn.response_text = 'Я не поняла вас. Пожалуйста, попробуйте переформулировать.'
        return
    if not suburb_stage \
            and not form.get('suburb') \
            and 'intercity_route' in turn.forms and not force:
        # we give higher priority to intercity_route if we are out of suburb-specific context
        return

    text2slots = defaultdict(set)
    for k, v in form.items():
        if not isinstance(v, dict):  # skip yandex intents
            text2slots[v].add(k)
    ft, fn = extract_slot_with_code('from', form, text2slots)
    tt, tn = extract_slot_with_code('to', form, text2slots)

    center = None
    center_code = sub.from_code or sub.to_code or turn.last_yandex_code or 'c213'
    if center_code:
        c = turn.world.code2obj.get(center_code)
        if c and c.get('latitude'):
            center = c['latitude'], c['longitude']

    # matching stations or cities from Yandex queries
    if ft and not fn:
        fn = (turn.world.match(ft, center=center) or [None])[0]
        logger.debug('matched {} to {} '.format(ft, fn and turn.world.code2obj[fn]['title']))
    if tt and not tn:
        tn = (turn.world.match(tt, center=center) or [None])[0]
        logger.debug('matched {} to {} '.format(tt, tn and turn.world.code2obj[tn]['title']))

    logger.debug(f'{ft}  ({fn}) -> {tt} ({tn})')

    if fn:
        sub.from_text = ft
        sub.from_code = fn
    if tn:
        sub.to_text = tt
        sub.to_code = tn

    anchor = None
    if sub.from_code:
        anchor = turn.world.code2obj[sub.from_code]
    elif sub.to_code:
        anchor = turn.world.code2obj[sub.to_code]
    if anchor:
        now = local_now(lat=anchor['latitude'], lon=anchor['longitude'])
    else:
        now = datetime.now(tz=timezone('Europe/Moscow'))

    date = None
    if form.get('when'):
        date = convert_date_to_abs(form['when'])
    if not date and sub.date_txt:
        date = datetime.fromisoformat(sub.date_txt)
    if not date:
        date = now
    sub.date_txt = date.isoformat()
    logger.debug('now is {}, search date is {}'.format(now, date))

    if sub.from_code and sub.to_code:
        if form.get('back'):
            logger.debug('turning the route backwards!')
            sub.from_code, sub.to_code = sub.to_code, sub.from_code
            sub.from_text, sub.to_text = sub.to_text, sub.from_text

        result = turn.rasp_api.suburban_trains_between(
            code_from=sub.from_code,
            code_to=sub.to_code,
            date=str(date)[:10],
        )
        if not result:
            turn.response_text = f'Не удалось получить маршрут электричек от {sub.from_text} до {sub.to_text}'
            turn.user_object['suburb'] = sub.to_dict()
            return
        segments = result['segments']
        search = result['search']
        from_norm = search['from']['title']
        to_norm = search['to']['title']

        cost = get_cppk_cost(from_text=sub.from_text, to_text=sub.to_text, date=None, return_price=True)

        turn.response_text = phrase_results(
            name_from=sub.from_text,
            name_to=sub.to_text,
            results=result,
            only_next=(date == now),
            from_meta=turn.world.code2obj.get(sub.from_code),
            date=date,
            now=now,
        )
        if cost and segments:
            sub.cost = cost
            turn.response_text += f' Стоимость {cost} рублей. Желаете купить билет?'
            turn.stage = 'suburb_confirm_sell'
            turn.suggests.append('Да')
            turn.suggests.append('Туда и обратно')

            turn.user_object['suburb_transaction'] = {
                'from_text': from_norm,
                'to_text': to_norm,
                'price': cost or 100,
            }
        else:
            turn.stage = 'suburb_no_price'
    elif not tn:
        turn.response_text = 'Куда вы хотите поехать' + (f' от станции {ft}' if ft else '') + '?'
        turn.stage = 'suburb_get_to'
    elif not fn:
        turn.response_text = 'Откуда вы хотите поехать' + (f' до станции {tt}' if tt else '') + '?'
        turn.stage = 'suburb_get_from'
    else:
        turn.response_text = 'Это какая-то невозможная ветка диалога'

    turn.user_object['suburb'] = sub.to_dict()


@csc.add_handler(priority=100, intents=['yes', 'confirm_purchase'], stages=['suburb_confirm_sell'])
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
    turn.stage = 'suburb_after_selling'
