"""Reading DPC text files.

The survey files are Shift_JIS (CP932) tab-separated text. The manual says
gaiji must not be included (p189), but hospital systems do not always
comply, so undecodable bytes are replaced and reported rather than fatal.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from pathlib import Path

REPLACEMENT = "�"


def iter_records(path: Path, encoding: str, delimiter: str) -> Iterator[tuple[int, list[str]]]:
    """Yield (line number, fields) for each non-empty line. Line numbers start at 1."""
    text = path.read_bytes().decode(encoding, errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line == "":
            continue
        yield lineno, line.split(delimiter)


def normalize_text(s: str) -> str:
    """NFKC-normalise a free-text field (names). Codes are never normalised."""
    return unicodedata.normalize("NFKC", s)
