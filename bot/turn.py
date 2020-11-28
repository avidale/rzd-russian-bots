from typing import Dict

import attr
from tgalice.cascade import DialogTurn, Cascade

from api.rasp import RaspSearcher


@attr.s
class RzdTurn(DialogTurn):
    rasp_api: RaspSearcher = attr.ib(factory=RaspSearcher)
    world: Dict[str, Dict] = attr.ib(factory=dict)


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
