from datetime import datetime

import logging
import requests
import time

logger = logging.getLogger(__name__)


def cppk_suggester(text):
    url = 'https://api.mobile-kassa.ru/v1.7/train-schedule/search-station?query={}&limit=100'
    return requests.get(url.format(text)).json()


def cppk_suggester_brute_force(text, min_len=3, return_code=False):
    text = text.upper()
    for i in range(len(text), min_len, -1):
        q = '*{}*'.format(text[:i])
        print(q)
        result = cppk_suggester(q)
        if result:
            if return_code:
                return result[0]['id']
            return result


def cppk_prices(from_code, to_code, date):
    """ Codes are extracted by cppk_suggester, and date is given as yyyy-mm-dd
    returns something like [{
        'cost': 48.0,
         'tariffId': 3267818,
         'trainNumber': '7573',
         'startTime': '2020-11-27T23:38:00',
         'startStationId': 2000006,
         'startStationName': 'МОСКВА (Белорусский вокзал)',
         'startStationLatinName': 'MOSKVA (Belorusskiy vokzal)',
         'finishTime': '2020-11-28T00:16:00',
         'finishStationId': 2000055,
         'finishStationName': 'ОДИНЦОВО',
         'finishStationLatinName': 'ODINTSOVO',
         'departureStationId': 2001060,
         'departureStationName': 'БЕГОВАЯ',
         'departureStationLatinName': 'BEGOVAYA',
         'departureStationHasWicket': True,
         'arrivalStationId': 2001101,
         'arrivalStationName': 'СКОЛКОВО',
         'arrivalStationLatinName': 'SKOLKOVO',
         'arrivalStationHasWicket': True,
         'defaultDirection': True,
         'departureTime': '2020-11-27T23:43:30',
         'arrivalTime': '2020-11-28T00:10:00',
         'scheduleId': 1957291,
         'motionMode': 'Ежедневно',
         'trainCategoryId': 11,
         'mcd': 1,
         'rzdTrainCategoryId': 1,
         'sevenThousandth': False
    }]
    """
    url = 'https://api.mobile-kassa.ru/v1.7/train-schedule/date-travel'
    params = {
        'date': date,
        'fromStationId': from_code,
        'toStationId': to_code,
    }
    result = requests.get(url, params=params)
    return result.json()


def get_cppk_cost(from_text, to_text, date=None, return_price=False):
    t = time.time()
    date = date or datetime.now().strftime('%Y-%m-%d')
    to_code = cppk_suggester_brute_force(to_text, return_code=True)
    if not to_code:
        return
    from_code = cppk_suggester_brute_force(from_text, return_code=True)
    if not from_code:
        return
    prices = cppk_prices(from_code=from_code, to_code=to_code, date=date)
    logger.debug(f'Got CPPK price in {time.time() - t} seconds')
    if return_price and prices:
        return prices[0].get('cost')
    return prices
