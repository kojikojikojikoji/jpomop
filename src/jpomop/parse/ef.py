"""Read and validate the inpatient EF integrated file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa

from jpomop.parse.encoding import REPLACEMENT, iter_records, normalize_text
from jpomop.parse.fields import Violation, check_value, parse_date8
from jpomop.parse.result import ParseResult
from jpomop.spec import Spec, load_codes, load_spec

_ARROW_TYPES = {
    "integer": pa.int64(),
    "decimal": pa.float64(),
    "date8": pa.date32(),
    "date8_or_zero": pa.date32(),
}


def _convert(value: str, type_: str) -> Any:
    if value == "":
        return None
    if type_ == "integer":
        return int(value)
    if type_ == "decimal":
        return float(value)
    if type_ in ("date8", "date8_or_zero"):
        return parse_date8(value)  # 00000000 (still in hospital) becomes null
    return value


def read_ef(path: Path, spec: Spec | None = None) -> ParseResult:
    spec = spec or load_spec("dpc_ef")
    fields = [f for f in spec.fields if not f.drop]
    codes = {f.name: load_codes(f.codes) for f in fields if f.codes}
    columns: dict[str, list[Any]] = {"_line": []} | {f.name: [] for f in fields}
    violations: list[Violation] = []

    def bad(line: int, field: str, value: str, rule: str, message: str) -> None:
        violations.append(Violation(path.name, line, field, value, rule, message))

    for lineno, raw in iter_records(path, spec.encoding, spec.delimiter):
        if len(raw) != spec.n_fields:
            bad(lineno, "*", str(len(raw)), "n_fields", f"expected {spec.n_fields} fields")
            continue
        row_ok = True
        values: dict[str, Any] = {}
        for f in fields:
            value = raw[f.col - 1]
            if REPLACEMENT in value:
                bad(lineno, f.name, value, "encoding", "contains bytes that are not CP932")
            if value == "":
                if f.required == "always":
                    bad(lineno, f.name, value, "required", "required field is empty")
                    row_ok = False
                values[f.name] = None
                continue
            problem = check_value(
                value, type_=f.type, length=f.length, zero_pad=f.zero_pad, codes=codes.get(f.name)
            )
            if problem:
                bad(lineno, f.name, value, *problem)
                if problem[0] != "code_not_in_table":
                    row_ok = False
            if f.name == "item_name":
                value = normalize_text(value)
            values[f.name] = _convert(value, f.type) if row_ok else None
        if not row_ok:
            continue
        columns["_line"].append(lineno)
        for f in fields:
            columns[f.name].append(values[f.name])

    schema = pa.schema(
        [pa.field("_line", pa.int64())]
        + [pa.field(f.name, _ARROW_TYPES.get(f.type, pa.string())) for f in fields]
    )
    return ParseResult(pa.table(columns, schema=schema), violations)
