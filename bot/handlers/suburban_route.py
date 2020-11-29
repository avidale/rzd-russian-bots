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
    from_norm: str = attr.ib(default=None)
    from_code: str = attr.ib(default=None)
    to_text: str = attr.ib(default=None)
    to_norm: str = attr.ib(default=None)
    to_code: str = attr.ib(default=None)
    date_txt: str = attr.ib(default=None)
    time_txt: str = attr.ib(default=None)
    cost: int = attr.ib(default=None)
    bidirectional: bool = attr.ib(default=False)


@csc.add_handler(priority=5, intents=['suburb_route', 'suburb_route_rx'])
@csc.add_handler(priority=20, intents=['suburb_route', 'suburb_route_rx', 'suburb_ellipsis'],
                 stages=['suburb_no_price'])
@csc.add_handler(priority=30, intents=['suburb_route', 'suburb_route_rx', 'suburb_ellipsis'],
                 stages=['suburb_get_from', 'suburb_get_to', 'suburb_confirm_sell', 'suburb_confirm_sell_final'])
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
            and ('intercity_route' in turn.forms
                 or (turn.stage or '').startswith('expect') and 'slots_filling' in turn.forms) \
            and not force:
        # we give higher priority to intercity_route if we are out of suburb-specific context
        return

    text2slots = defaultdict(set)
    for k, v in form.items():
        if not isinstance(v, dict):  # skip yandex intents
            text2slots[v].add(k)
    if 'suburb_route_rx' in turn.forms and 'suburb_route' not in turn.forms and 'suburb_ellipsis' not in turn.forms:
        ft, fn = extract_slot_with_code('from', form, text2slots)
        tt, tn = extract_slot_with_code('to', form, text2slots)
    else:
        # yandex fills these slots in a really weird way
        ft, fn = form.get('from'), None
        tt, tn = form.get('to'), None

    if ft or tt:  # on new search, we don't want to keep bidirectionality
        sub.bidirectional = False

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
            turn.response_text = f'Не удалось получить маршрут электричек от {sub.from_text} до {sub.to_text}.' \
                                 f' Поискать междугородные поезда? '
            turn.suggests.append('да')
            turn.stage = 'suggest_intercity_route_from_suburban'
            turn.user_object['suburb'] = sub.to_dict()
            return
        segments = result['segments']
        search = result['search']
        sub.from_norm = search['from']['title']
        sub.to_norm = search['to']['title']

        if segments:
            cost = get_cppk_cost(from_text=sub.from_text, to_text=sub.to_text, date=None, return_price=True)
        else:
            cost = None

        turn.response_text = phrase_results(
            name_from=sub.from_norm,
            name_to=sub.to_norm,
            results=result,
            only_next=(date == now),
            from_meta=turn.world.code2obj.get(sub.from_code),
            date=date,
            now=now,
        )
        if cost and segments:
            sub.cost = cost
            turn.response_text += f' Стоимость {cost} рублей в одну сторону. Желаете купить билет?'
            turn.stage = 'suburb_confirm_sell'
            turn.suggests.append('Да')
            turn.suggests.append('Туда и обратно')
        elif not segments:
            turn.response_text += ' Поискать междугородные поезда?'
            turn.suggests.append('да')
            turn.stage = 'suggest_intercity_route_from_suburban'
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


@csc.add_handler(priority=40, stages=['suggest_intercity_route_from_suburban'], intents=['yes'])
def switch_to_intercity(turn: RzdTurn):
    sub = SuburbContext.from_dict(turn.user_object.get('suburb') or {})
    form = {
        'from': sub.from_norm or sub.from_text,
        'to': sub.to_norm or sub.to_text,
        'when': datetime.fromisoformat(sub.date_txt) if sub.date_txt else None,
    }
    from bot.handlers.route import intercity_route
    intercity_route(turn=turn, form=form)


@csc.add_handler(priority=100, intents=['yes', 'confirm_purchase'], stages=['suburb_confirm_sell'])
@csc.add_handler(priority=100, intents=['both_sides', 'one_side'],
                 stages=['suburb_confirm_sell', 'suburb_confirm_sell_final'])
def suburb_purchase_details(turn: RzdTurn):
    sub = SuburbContext.from_dict(turn.user_object.get('suburb') or {})
    if turn.intents.get('both_sides'):
        sub.bidirectional = True
    if turn.intents.get('one_side'):
        sub.bidirectional = False
    turn.response_text = f'Покупаю билет от станции {sub.from_norm} до станции {sub.to_norm}, '
    if sub.bidirectional:
        turn.response_text += 'в обе стороны, '
    turn.response_text += f' с вашей карты {turn.bank_card} спишется {sub.cost * (sub.bidirectional + 1)} рублей. '
    turn.response_text += 'Вы подтверждаете покупку?'
    turn.suggests.append('Да')
    turn.suggests.append('В одну сторону' if sub.bidirectional else 'В обе стороны')
    turn.stage = 'suburb_confirm_sell_final'
    turn.user_object['suburb'] = sub.to_dict()


@csc.add_handler(priority=100, intents=['yes', 'confirm_purchase'], stages=['suburb_confirm_sell_final'])
def suburb_confirm_purchase(turn: RzdTurn):
    # todo: fill
    sub = SuburbContext.from_dict(turn.user_object.get('suburb') or {})
    p = int(sub.cost) * (1 + sub.bidirectional)
    url = f'https://rzd-skill.herokuapp.com/qr/?f={sub.from_norm}&t={sub.to_norm}'
    text = f'Отлично! Я оформила вам билет на электричку. ' \
           f'Вы можете распечатать его или приложить QR-код прямо к турникету.'
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
    # todo: add post-sell suggests
