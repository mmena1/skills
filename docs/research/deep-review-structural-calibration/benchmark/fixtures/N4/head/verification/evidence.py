from dataclasses import dataclass
from datetime import date
from enum import Enum

from verification.documents import Document


class EvidenceStatus(Enum):
    MISSING = "missing"
    INVALID = "invalid"
    VALID = "valid"


@dataclass(frozen=True)
class EvidenceCheck:
    status: EvidenceStatus
    failures: tuple[str, ...] = ()


def check_evidence(document: Document | None, applicant_name: str, today: date) -> EvidenceCheck:
    if document is None:
        return EvidenceCheck(EvidenceStatus.MISSING)
    failures = []
    if document.expires < today:
        failures.append("document has expired")
    if document.holder_name.casefold() != applicant_name.casefold():
        failures.append("name on document does not match the application")
    if failures:
        return EvidenceCheck(EvidenceStatus.INVALID, tuple(failures))
    return EvidenceCheck(EvidenceStatus.VALID)
