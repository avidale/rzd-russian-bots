import http

import requests
import time
import re

from collections import Counter


def suggest_stations(text, threshold=0.5, min_n=3, max_n=10, s_coef=1e-3, l_coef=1e-3, len_coef=-1e-5):
    """ Получение списка станций по префиксу названия.
    Ответ - список станций в формате [({'n': name, 'c': code, ...}, score), ...],
    где name - название станции, code - её код, score - скор точности совпадения.
    """
    text2 = text.upper()
    response = requests.get(
        'https://m.rzd.ru/suggester',
        params=dict(
            stationNamePart=text2,
            lang='ru',
            compactMode='y',
            lat=1,
        ),
    )
    if response.headers.get('content-type').startswith('application/json'):
        suggests = response.json()
    else:
        return None
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


def suggest_first_station(text):
    """Функция, которая выбирает первую станцию из предложенных."""
    # TODO временный костыль c предлогами
    lower_text = text.lower()
    for prep in ["от", "из", "с", "до", "в", "на", "к"]:
        if lower_text.startswith(f"{prep} "):
            lower_text = lower_text.split(" ", maxsplit=1)[1]
            break
    # TODO временный костыль c питером
    if lower_text == 'питер':
        lower_text = 'Санкт-Петербург'
    stations = suggest_stations(lower_text)
    if stations:
        return stations[0][0]['c']

    return None


TIME_MAPPING = {
    "night": "ночь",
    "morning": "утро",
    "afternoon": "день",
    "evening": "вечер"
}


def get_time_of_day(time_str):
    """Узнаем какой тег времени дня у этого билета.
    Args:
        time_str (str): время дня в формате HH:MM

    Returns:
        str|None: Тег времени дня или None, если не подходит формат
    """
    if not re.match(r"^\d{1,2}:\d{2}$", "01:30"):
        return None
    hours = int(time_str.split(":")[0])
    if hours in range(0, 6):
        return "night"
    elif hours in range(6, 12):
        return "morning"
    elif hours in range(12, 18):
        return "afternoon"
    else:
        return "evening"


def filter_trains_by_time_tags(trains, time_tags):
    """Фильтруем все билеты по наличию в них тегов времени дня из заданного входного списка тегов."""
    filtered_trains = []
    for train in trains:
        train_tag = train.get('time_tag', None)
        if train_tag and train_tag in time_tags:
            filtered_trains.append(train)
    return filtered_trains


def time_tag_attribution(trains):
    """Проставляем тег времени дня ко всем билетам."""
    time_tags = []
    for idx, train in enumerate(trains):
        datetime_parts = train["time_start"].split()
        if len(datetime_parts) != 2:
            continue
        train_time_str = datetime_parts[1]
        train_tag = get_time_of_day(train_time_str)
        time_tags.append(train_tag)
        # Заполняем тег для билета
        trains[idx]["time_tag"] = train_tag
    return trains, set(time_tags)


def init_find_route(from_code, to_code, date_to, date_back=None):
    """Инициализация запроса на получение списка маршрутов из А в Б на определённую дату.
    from_code и to_code - коды станций отправления и назначения (берутся из suggest_stations).
    date_to и date_back - даты в формате DD.MM.YYYY
    Формат ответа - кортеж из словаря параметров запроса и cookie
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
    params['rid'] = prev_result.json().get('rid', None)
    cookies = prev_result.cookies
    return params, cookies.get_dict()


def request_find_route_result(params, cookies, timeout=0.01, max_attempts=10, timeout_inc=0.01, format_result=False):
    """Получение ранее запрошенного списка маршрутов."""
    result = None

    for i in range(max_attempts):
        result = requests.get('https://pass.rzd.ru/timetable/public/ru', params=params, cookies=cookies).json()
        code = result.get('result', None)
        if code == 'OK':
            break
        time.sleep(timeout + timeout_inc * i)

    if format_result:
        return format_route_list(result)
    return result


def find_route(from_code, to_code, date_to, date_back=None, timeout=0.01, max_attempts=10, timeout_inc=0.01,
               format_result=False):
    """ Получение списка маршрутов из А в Б на определённую дату.
    from_code и to_code - коды станций отправления и назначения (берутся из suggest_stations).
    date_to и date_back - даты в формате DD.MM.YYYY
    Формат ответа я пока до конца не разобрал
    """
    params, cookies = init_find_route(from_code, to_code, date_to, date_back)
    return request_find_route_result(params, cookies, timeout, max_attempts, timeout_inc, format_result)


def format_route_list(routes_dict):
    """ Преобрзование словаря маршрутов в обговоренный формат списка поездов."""
    if not routes_dict or routes_dict.get('result', None) != 'OK':
        return []
    result_trains = []

    train_groups = routes_dict['tp']
    for train_group in train_groups:
        from_location = train_group['from']
        to_location = train_group['where']

        request_trains = routes_dict['tp'][0]['list']
        for train in request_trains:
            number = train['number']
            brand = train.get('brand', '').lower() # сапсан, красная стрела, эксресс

            local_start_date = train.get('localDate0', train.get('date0', None))
            local_start_time = train.get('localTime0', train.get('time0', None))

            local_end_date = train.get('localDate1', train.get('date1', None))
            local_end_time = train.get('localTime1', train.get('time1', None))

            from_time_zone = train.get('timeDeltaString0', None) or 'МСК+0'
            to_time_zone = train.get('timeDeltaString1', None) or 'МСК+0'

            duration = train['timeInWay']

            from_station = train['station0']
            to_station = train['station1']

            cars = train['cars']
            for car in cars:
                free_seats_count = int(car['freeSeats'])
                cost = car['tariff']
                car_type = car['typeLoc']
                if free_seats_count > 0 and car_type in ['Купе', 'Плацкартный', 'Сидячий', 'СВ', 'Люкс']:
                    result_trains.append({
                        "seat_type": car_type,
                        "from": from_location,
                        "to": to_location,
                        "from_station": from_station,
                        "to_station": to_station,
                        "number": number,
                        "brand": brand,
                        "time_start": f"{local_start_date} {local_start_time}",
                        "time_end": f"{local_end_date} {local_end_time}",
                        "from_tz": from_time_zone,
                        "to_tz": to_time_zone,
                        "duration": duration,
                        "cost": int(cost)
                    })

        return result_trains


if __name__ == "__main__":
    moscow = suggest_first_station("Москва")
    piter = suggest_first_station("Санкт-Петербург")
    date_to = "01.12.2020"
    print(moscow, piter)
    print(find_route(moscow, piter, date_to, format_result=True))

    vlad = suggest_first_station("Владивасток")
    irkutsk = suggest_first_station("Иркутск")
    print(suggest_first_station("Владивасток"))
    print(suggest_first_station("Иркутск"))
    date_to = "01.12.2020"
    print(vlad, irkutsk)
    print(find_route(vlad, piter, irkutsk, format_result=True))

    orenburg = suggest_first_station("Оренбург")
    irkutsk = suggest_first_station("Иркутск")
    date_to = "01.12.2020"
    print(orenburg, moscow)
    print(find_route(orenburg, moscow, date_to, format_result=True))




