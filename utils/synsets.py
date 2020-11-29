from collections import defaultdict
from typing import Dict, List

import attr
import yaml
from tgalice.utils.serialization import Serializeable


@attr.s
class Synset(Serializeable):
    id: str = attr.ib()
    canonical: str = attr.ib(converter=lambda x: x.lower().strip())
    synonyms: List[str] = attr.ib(factory=list, converter=lambda x: [t.lower().strip() for t in x])

    @property
    def all(self) -> List[str]:
        return [self.canonical] + self.synonyms


class Synsets:
    def __init__(self, data):
        if isinstance(data, str):
            with open(data, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        self.id2set: Dict[str, Synset] = {k: Synset(id=k, **v) for k, v in data.items()}
        self.can2id: Dict[str, str] = {}
        self.text2ids: Dict[str, List[str]] = defaultdict(list)
        self.text2can: Dict[str, List[str]] = defaultdict(list)
        for ss in self.id2set.values():
            self.can2id[ss.canonical] = ss.id
            for text in ss.all:
                self.text2ids[text].append(ss.id)
                self.text2can[text].append(ss.canonical)

    def synonyms(self, text):
        text = text.lower().strip()
        results = set()
        for idx in self.text2ids.get(text, []):
            ss = self.id2set[idx]
            results.add(ss.canonical)
            results.update(ss.synonyms)
        return sorted(results.difference({text}))


CITY_SYNONYMS = Synsets('config/synonyms.yaml')
