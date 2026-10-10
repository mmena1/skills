# Cash ledger

Append-only cash ledger for a small shop, stored as one text file per till.

Durability contract: a batch of entries is appended while holding an exclusive lock on the ledger file for the whole batch. The file is flushed and fsynced before the lock is released, and the file is closed and unlocked even when formatting or writing fails part way. Formatting is pure and testable without files.

Python 3.11 standard library, POSIX only. Run `python -m unittest discover -s tests`.
