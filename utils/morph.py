from tgalice.nlu.basic_nlu import PYMORPHY
from typing import Optional


def with_number(noun, number):
    text = agree_with_number(noun=noun, number=number)
    return f'{number} {text}'


def agree_with_number(noun, number):
    last = abs(number) % 10
    tens = abs(number) % 100 // 10
    if PYMORPHY:
        parses = PYMORPHY.parse(noun)
        if parses:
            return parses[0].make_agree_with_number(abs(number)).word
    # detect conjugation based on the word ending
    if last == 1:
        return noun
    elif noun.endswith('ка'):
        if last in {2, 3, 4}:
            return noun[:-1] + 'и'
        else:
            return noun[:-1] + 'ек'
    elif noun.endswith('а'):
        if last in {2, 3, 4}:
            return noun[:-1] + 'ы'
        else:
            return noun[:-1]
    else:
        if last in {2, 3, 4}:
            return noun + 'а'
        else:
            return noun + 'ов'


def convert_geo_to_normalized_city(geo_entity) -> Optional[str]:
    """Конвертируем гео сущность Яндекса в текстовое нормализованное имя города."""
    if isinstance(geo_entity, dict):
        return geo_entity.get('city', None)

    elif isinstance(geo_entity, str):
        # Если есть предлог  то удаляем его
        parts = geo_entity.split()
        preps = ["в", "от", "из", "с", "до", "на", "к"]
        if len(parts) > 1 and parts[0] in preps:
            parts = parts[1:]
        return ' '.join(parts)
