"""Owns the open ledger file and its exclusive lock for one batch of appends."""

import fcntl
import os


class LedgerWriter:
    def __init__(self, path):
        self._path = path
        self._file = None

    def __enter__(self):
        handle = open(self._path, "a", encoding="utf-8")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
        except BaseException:
            handle.close()
            raise
        self._file = handle
        return self

    def append(self, line: str) -> None:
        if self._file is None:
            raise RuntimeError("ledger writer is not open")
        self._file.write(line + "\n")

    def __exit__(self, exc_type, exc, traceback):
        handle, self._file = self._file, None
        try:
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        return False
