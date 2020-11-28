import requests
import time

from collections import Counter


def suggest_stations(text, threshold=0.5, min_n=3, max_n=10, s_coef=1e-3, l_coef=1e-3, len_coef=-1e-5):
    """ Получение списка станций по префиксу названия.
    Ответ - список станций в формате [({'n': name, 'c': code, ...}, score), ...],
    где name - название станции, code - её код, score - скор точности совпадения.
    """
    text2 = text.upper()
    suggests = requests.get(
        'https://m.rzd.ru/suggester',
        params=dict(
            stationNamePart=text2,
            lang='ru',
            compactMode='y',
            lat=1,
        ),
    ).json()
    top = Counter()
    id2station = {}
    query = set(text2.split())
    for s in suggests:
        r = set(s['n'].split())
        score = s.get('S', 0) * s_coef + s.get('L', 0) * l_coef - len(s['n']) * len_coef
        for w in query:
            for i in range(len(w), 1, -1):
                if any(w[:i] in rw for rw in r):
                    score += (i / len(w)) / len(query)
                    break
        top[s['c']] = score
        id2station[s['c']] = s
    final = [
        (id2station[k], v)
        for i, (k, v) in enumerate(top.most_common(max_n))
        if v > threshold or i < min_n
    ]
    return final


def find_route(from_code, to_code, date_to, date_back=None, timeout=0.01, max_attempts=10, timeout_inc=0.01):
    """ Получение списка маршрутов из А в Б на определённую дату.
    from_code и to_code - коды станций отправления и назначения (берутся из suggest_stations).
    date_to и date_back - даты в формате DD.MM.YYYY
    Формат ответа я пока до конца не разобрал
    """
    params = dict(
        STRUCTURE_ID=735,
        layer_id=5371,
        dir=0,
        tfl=3,
        checkSeats=1,
        code0=from_code,
        dt0=date_to,
        code1=to_code,
    )
    if date_back:
        params['dt1'] = date_back
    prev_result = requests.get('https://pass.rzd.ru/timetable/public/ru', params=params)
    params['rid'] = prev_result.json()['rid']
    cookies = prev_result.cookies
    for i in range(max_attempts):
        result = requests.get('https://pass.rzd.ru/timetable/public/ru', params=params, cookies=cookies).json()
        code = result['result']
        if code == 'OK':
            return result
        time.sleep(timeout + timeout_inc * i)
