"""Read-only reports over recorded loans."""


def active_loans(loans):
    """Loans that have not been returned, in recorded order."""
    return [loan for loan in loans if loan.returned is None]


def returned_late(loans):
    """Item ids returned after their due date, in recorded order."""
    return [loan.item_id for loan in loans if loan.returned is not None and loan.returned > loan.due]
