"""One structural PNCP identifier parser; originals remain in source storage."""
from dataclasses import dataclass
import re

_ID = re.compile(r'([A-Z0-9]{12}[0-9]{2})-1-([0-9]{1,10})/([0-9]{4,10})',re.ASCII)


@dataclass(frozen=True)
class PNCPIdentifier:
    cnpj: str
    sequence: str
    year: str

    @property
    def canonical(self):
        return f'{self.cnpj}-1-{self.sequence}/{self.year}'


def parse_pncp_id(value):
    if not isinstance(value,str) or len(value)>40:
        raise ValueError('Invalid PNCP identifier')
    match=_ID.fullmatch(value.upper())
    if not match:
        raise ValueError('Invalid PNCP identifier')
    cnpj,sequence,year=match.groups()
    return PNCPIdentifier(cnpj,sequence,year)
