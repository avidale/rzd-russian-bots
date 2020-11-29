
def get_human_readable_existing_car_types(trains: list):
    """Получение списка человеко-читаемых типов вагонов."""
    existing_car_types = set(train['seat_type'] for train in trains)
    return [car_type.capitalize() for car_type in existing_car_types]


def car_type_to_human_str(car_type: str, form=0):
    """Перевод типа вагона в человеко-читаемый вид с учетом склонения."""
    plural_mapping = {
        "seating": "сидячие",
        "first_class": "СВ",
        "econom": "плацкартные",
        "sleeping": "купейные",
        "luxury": "люксовый"
    }
    plural_mapping2 = {
        "seating": "сидячими",
        "first_class": "СВ",
        "econom": "плацкартными",
        "sleeping": "купейными",
        "luxury": "люксовыми"
    }
    plural_mapping3 = {
        "seating": "сидячих",
        "first_class": "СВ",
        "econom": "плацкартных",
        "sleeping": "купейных",
        "luxury": "люксовых"
    }

    singular_mapping = {
        "seating": "сидячий",
        "first_class": "СВ",
        "econom": "плацкартный",
        "sleeping": "купейный",
        "luxury": "люкс"
    }
    singular_mapping2 = {
        "seating": "сидячем",
        "first_class": "СВ",
        "econom": "плацкартном",
        "sleeping": "купейном",
        "luxury": "люксовом"
    }

    if form == 1:
        return plural_mapping[car_type]
    elif form == 2:
        return plural_mapping2[car_type]
    elif form == 3:
        return singular_mapping2[car_type]
    elif form == 4:
        return plural_mapping3[car_type]
    return singular_mapping[car_type]


def seat_type_to_human_str(seat_type: str, form=0):
    """Перевод типа места в человеко-читаемый вид с учетом склонения."""
    plural_mapping = {
        "upper": "верхние",
        "bottom": "нижние"
    }
    singular_mapping = {
        "upper": "верхний",
        "bottom": "нижний"
    }
    singular_mapping2 = {
        "upper": "верхнее",
        "bottom": "нижнее"
    }
    if form == 2:
        return plural_mapping[seat_type]
    elif form == 1:
        return singular_mapping2[seat_type]
    return singular_mapping[seat_type]