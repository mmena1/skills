from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Entry:
    till: str
    amount: Decimal
    memo: str
