"""Field-level checks shared by the EF and Form 1 readers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_DECIMAL = re.compile(r"-?\d+(\.\d+)?")


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    field: str
    value: str
    rule: str
    message: str


def parse_date8(s: str) -> date | None:
    """Parse YYYYMMDD. Return None if it is not a real calendar date."""
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None


def check_value(
    value: str,
    *,
    type_: str,
    length: int | None,
    zero_pad: bool,
    codes: dict[str, str] | None,
) -> tuple[str, str] | None:
    """Return (rule, message) if `value` breaks the field definition, else None.

    Empty values are not checked here; whether they are allowed is a
    separate `required` rule.
    """
    if length is not None:
        if zero_pad and len(value) != length:
            return "length", f"must be exactly {length} characters (zero-padded)"
        if len(value) > length:
            return "length", f"longer than {length} characters"
    if type_ == "digits" and not value.isdigit():
        return "type", "must contain digits only"
    if type_ == "integer" and not value.lstrip("-").isdigit():
        return "type", "must be an integer"
    if type_ == "decimal" and not _DECIMAL.fullmatch(value):
        return "type", "must be a number"
    if type_ == "date8" and parse_date8(value) is None:
        return "date_invalid", "not a valid YYYYMMDD date"
    if type_ == "date8_or_zero" and value != "00000000" and parse_date8(value) is None:
        return "date_invalid", "not a valid YYYYMMDD date or 00000000"
    if type_ == "date8_partial" and not (len(value) == 8 and value.isdigit()):
        return "date_invalid", "must be 8 digits (unknown parts as 0)"
    if type_ == "date8_partial" and value[:4] != "0000" and partial_date(value) is None:
        return "date_invalid", "not a calendar date"
    if codes is not None and value not in codes:
        return "code_not_in_table", "not in the code table"
    return None


def partial_date(s: str) -> date | None:
    """Birth dates may have unknown parts recorded as 0 (p44). Fill them with 1."""
    if len(s) != 8 or not s.isdigit() or s[:4] == "0000":
        return None
    month = int(s[4:6]) or 1
    day = int(s[6:]) or 1
    try:
        return date(int(s[:4]), month, day)
    except ValueError:
        return None
