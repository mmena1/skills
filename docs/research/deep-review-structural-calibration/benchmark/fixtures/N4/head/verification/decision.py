from dataclasses import dataclass

from verification.evidence import EvidenceCheck, EvidenceStatus


@dataclass(frozen=True)
class NextStep:
    action: str
    applicant_messages: tuple[str, ...] = ()


def next_step(check: EvidenceCheck) -> NextStep:
    if check.status is EvidenceStatus.MISSING:
        return NextStep("request_upload", ("Please upload an identity document.",))
    if check.status is EvidenceStatus.INVALID:
        return NextStep("reject", check.failures)
    return NextStep("approve")
