from datetime import datetime
from pytz import timezone

from utils.date_convertor import local_now, date2ru


def human_readable_time(time_string):
    ts = datetime.fromisoformat(time_string[:19])  # the last 6 symbols are timezone; we ignore them for now
    return '{}:{:02d}'.format(ts.hour, ts.minute)


def simplify_station(text):
    text = text.split('(')[0]
    if text.isupper():
        text = ' '.join(w.capitalize() for w in text.split())
    return text.strip()


def phrase_results(results, name_from, name_to, only_next=True, from_meta=None, date=None, now=None):
    if not now:
        if from_meta:
            now = local_now(lat=from_meta['latitude'], lon=from_meta['longitude'])
        else:
            now = datetime.now(tz=timezone('Europe/Moscow'))
        name_to, name_from = simplify_station(name_to), simplify_station(name_from)
    dnow = str(now)[:10]
    tnow = str(now)[11:20]
    print('now is {}'.format(tnow))
    if not date:
        date_txt = 'сегодня'
    elif str(date)[:10] == str(now)[:10]:
        date_txt = 'сегодня'
    else:
        date_txt = date2ru(date)
    if only_next:
        valid = []
        for v in results['segments']:
            try:
                d = datetime.fromisoformat(v['departure'])
                if d > now:
                    valid.append(v)
            except ValueError:
                if v['departure'] > tnow:
                    valid.append(v)
    else:
        valid = results['segments']
    if len(valid) <= 0:
        pre = 'Сегодня все электрички от {} до {} ушли. Но вот какие были: в'.format(name_from, name_to)
        results_to_read = results['segments']
    else:
        pre = 'Вот какие электрички от {} до {} есть {}: в'.format(name_from, name_to, date_txt)
        results_to_read = valid
    times = [human_readable_time(r['departure']) for r in results_to_read]
    if len(times) == 0:
        return f'Никаких электричек от {name_from} до {name_to} не нашлось.'
    if len(times) == 1:
        pre = pre + ' {}'.format(times[0])
    else:
        n_first = -1
        if len(times) > 6:
            n_first = 3
        pre = pre + ','.join([' {}'.format(t) for t in times[:n_first]])
        if n_first > 0:
            pre += ' и ещё {}, последняя в {}'.format(len(times) - n_first, times[-1])
        else:
            pre += ' и в {}'.format(times[-1])
    pre = pre + '.'
    return pre
