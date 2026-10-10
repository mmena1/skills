from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal


@dataclass(frozen=True)
class Entry:
    till: str
    amount: Decimal
    memo: str


def normalize_amount(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def format_entry(entry: Entry) -> str:
    memo = entry.memo.replace("\t", " ").replace("\n", " ").strip()
    return f"{entry.till}\t{normalize_amount(entry.amount)}\t{memo}"
