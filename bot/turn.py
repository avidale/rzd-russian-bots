from typing import Dict

import attr
from tgalice.cascade import DialogTurn, Cascade

from api.rasp import RaspSearcher, StationMatcher
from utils.synsets import Synsets


@attr.s
class RzdTurn(DialogTurn):
    rasp_api: RaspSearcher = attr.ib(factory=RaspSearcher)
    world: StationMatcher = attr.ib(factory=StationMatcher)

    @property
    def last_yandex_code(self):
        # todo: return the code of the last used suburb station
        pass

    @property
    def bank_card(self):
        return 'VISA <voice>на</voice><text>****</text>0378'


csc = Cascade()


class SLOTS:
    FROM_TEXT = 'from_text'
    TO_TEXT = 'to_text'
    WHEN_TEXT = 'when_text'


TRANSIENT_SLOTS = {
    SLOTS.FROM_TEXT,
    SLOTS.TO_TEXT,
    SLOTS.WHEN_TEXT,
}
