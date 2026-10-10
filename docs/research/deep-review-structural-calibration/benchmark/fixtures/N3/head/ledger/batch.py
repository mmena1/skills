from ledger.entries import format_entry
from ledger.writer import LedgerWriter


def record_batch(path, entries) -> int:
    lines = [format_entry(entry) for entry in entries]
    with LedgerWriter(path) as writer:
        for line in lines:
            writer.append(line)
    return len(lines)
