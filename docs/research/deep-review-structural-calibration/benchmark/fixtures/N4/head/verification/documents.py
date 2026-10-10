from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Document:
    holder_name: str
    expires: date
