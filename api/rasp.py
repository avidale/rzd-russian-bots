import os
import requests
import statistics

from datetime import datetime


def median(x):
    return statistics.median(x) if x else None


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
