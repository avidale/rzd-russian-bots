import os
import requests

from datetime import datetime


class RaspSearcher:
    def __init__(self, token=None):
        self._token = token or os.getenv('RASP_TOKEN')
        self._cache = {}

    def suburban_trains_between(self, code_from, code_to, date=None, limit=100):
        # see https://yandex.ru/dev/rasp/doc/reference/schedule-point-point-docpage/
        if date is None:
            date = str(datetime.now())[:10]  # todo: calculate 'now' in requesters timezone
        params = {
            'from': code_from,
            'to': code_to,
            'date': date,
            'transport_types': 'suburban',
            'limit': limit,
        }
        key = str(sorted(params.items()))
        if key in self._cache:
            return self._cache[key]
        params['apikey'] = self._token
        rasp = requests.get('https://api.rasp.yandex.net/v3.0/search/', params=params)
        # todo: work with pagination
        result = rasp.json()
        self._cache[key] = result
        # keys are: 'interval_segments', 'pagination', 'segments', 'search'
        return result
