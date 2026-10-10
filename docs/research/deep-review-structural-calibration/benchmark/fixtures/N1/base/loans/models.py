from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Loan:
    item_id: str
    member_id: str
    due: date
    returned: date | None = None
