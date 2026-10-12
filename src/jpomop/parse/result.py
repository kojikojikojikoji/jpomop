from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pyarrow as pa

from jpomop.parse.fields import Violation

VIOLATION_SCHEMA = pa.schema(
    [
        ("file", pa.string()),
        ("line", pa.int64()),
        ("field", pa.string()),
        ("value", pa.string()),
        ("rule", pa.string()),
        ("message", pa.string()),
    ]
)


def violations_table(violations: list[Violation]) -> pa.Table:
    return pa.Table.from_pylist([asdict(v) for v in violations], schema=VIOLATION_SCHEMA)


@dataclass
class ParseResult:
    """Rows that passed the checks, plus every problem found.

    Rows with a missing required value or a malformed value are left out of
    `table`. Unknown codes are reported but the row is kept.
    """

    table: pa.Table
    violations: list[Violation] = field(default_factory=list)

    def violations_table(self) -> pa.Table:
        return violations_table(self.violations)
