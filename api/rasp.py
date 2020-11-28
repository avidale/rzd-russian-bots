import editdistance
import logging
import os
import requests
import statistics
import time
from collections import defaultdict, Counter
from datetime import datetime

from tgalice.nlu.basic_nlu import fast_normalize

logger = logging.getLogger(__name__)


def median(x):
    return statistics.median(x) if x else None


class RaspSearcher:
    def __init__(self, token=None):
        self._token = token or os.getenv('RASP_TOKEN')
        self._cache = {}

    def suburban_trains_between(self, code_from, code_to, date=None, limit=1000):
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
        t = time.time()
        rasp = requests.get('https://api.rasp.yandex.net/v3.0/search/', params=params)
        # todo: work with pagination
        result = rasp.json()
        logger.debug(f'requested yandex.rasp in {time.time() - t} seconds')
        self._cache[key] = result
        # keys are: 'interval_segments', 'pagination', 'segments', 'search'
        return result

    def get_world(self, countries=None):
        raw = requests.get(f'https://api.rasp.yandex.net/v3.0/stations_list/?apikey={self._token}').json()
        return prepare_the_world(raw, countries=countries)


def extract_all_objects(regions_list):
    settlements = []
    stations = []
    regions = []
    for region_id, region in enumerate(regions_list):
        region_code = region['codes'].get('yandex_code')
        regions.append({
            'title': region['title'],
            'yandex_code': region_code,
            'region_id': region_id,
            'country': region['country']
        })
        for settlement_id, settlement in enumerate(region['settlements']):
            settlement_code = settlement['codes'].get('yandex_code')
            latitude = median([s['latitude'] for s in settlement['stations'] if s['latitude']]) or None
            longitude = median([s['longitude'] for s in settlement['stations'] if s['longitude']]) or None
            settlements.append({
                'title': settlement['title'],
                'yandex_code': settlement_code,
                'region_id': region_id,
                'settlement_id': settlement_id,
                'latitude': latitude,
                'longitude': longitude,
            })
            for station_id, station in enumerate(settlement['stations']):
                if station['station_type'] in {'bus_stop'}:
                    # there are too many of bus stops, and they are generally useless for our purposes
                    continue
                station['region_id'] = region_id
                station['settlement_id'] = settlement_id
                station['yandex_code'] = station.get('codes', {}).get('yandex_code')
                stations.append(station)

    return regions, settlements, stations


def prepare_the_world(stations_json, countries=None):
    target_countries = countries or ['Россия', 'Беларусь', 'Украина']
    regions_list = []
    for c in stations_json['countries']:
        if c['title'] in target_countries:
            for r in c['regions']:
                r['country'] = c['title']
            regions_list.extend(c['regions'])
    regions, settlements, stations = extract_all_objects(regions_list)
    world = {
        'regions': regions,
        'settlements': settlements,
        'stations': stations
    }
    return world


class StationMatcher:
    def __init__(self, world, prefix_size=3):
        self.world = world
        self.code2obj = {}
        for t, d in self.world.items():
            for o in d:
                self.code2obj[o['yandex_code']] = o
        self.prefixes = defaultdict(list)
        self.prefix_size = prefix_size
        for s in self.code2obj.values():
            self.prefixes[s['title'][:prefix_size].lower()].append(s['yandex_code'])

    def match(self, text, stations=0, regions=None, cities=0.9, lemmatize=True):
        scores = Counter()
        queries = {text.lower(), text.lower()[:-1], text.lower()[-2]}
        if lemmatize:
            queries.add(fast_normalize(text, lemmatize=True))
        codes = {'r': regions, 'c': cities, 's': stations}
        for d in self.prefixes[text.lower()[:self.prefix_size]]:
            if codes.get(d[0]) is None:
                continue
            scores[d] = codes[d[0]] \
                        - sum(editdistance.eval(q, self.code2obj[d]['title']) for q in queries) / len(queries)
        return [k for k, v in scores.most_common(10)]
