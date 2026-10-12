"""Read and validate Form 1 (様式1).

Form 1 is stored long: one record per item code, with up to nine payloads.
`read_yoshiki1` checks the record layout. `pivot_yoshiki1` turns the
records into one row per form plus long tables for diagnoses and surgeries,
checking each payload against the item definitions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa

from jpomop.parse.encoding import REPLACEMENT, iter_records, normalize_text
from jpomop.parse.fields import Violation, check_value, parse_date8, partial_date
from jpomop.parse.result import ParseResult, violations_table
from jpomop.spec import Spec, load_codes, load_spec

KEY = ("facility_code", "data_id", "admission_date", "stay_no", "summary_no")
PAYLOADS = [f"payload{i}" for i in range(1, 10)]


def read_yoshiki1(path: Path, spec: Spec | None = None) -> ParseResult:
    spec = spec or load_spec("dpc_yoshiki1")
    columns: dict[str, list[Any]] = {"_file": [], "_line": []} | {f.name: [] for f in spec.fields}
    violations: list[Violation] = []

    for lineno, raw in iter_records(path, spec.encoding, spec.delimiter):
        if len(raw) != spec.n_fields:
            violations.append(
                Violation(
                    path.name,
                    lineno,
                    "*",
                    str(len(raw)),
                    "n_fields",
                    f"expected {spec.n_fields} fields",
                )
            )
            continue
        row_ok = True
        for f in spec.fields:
            value = raw[f.col - 1]
            if REPLACEMENT in value:
                violations.append(
                    Violation(
                        path.name,
                        lineno,
                        f.name,
                        value,
                        "encoding",
                        "contains bytes that are not CP932",
                    )
                )
            if value == "":
                if f.required == "always":
                    violations.append(
                        Violation(
                            path.name, lineno, f.name, value, "required", "required field is empty"
                        )
                    )
                    row_ok = False
                continue
            problem = check_value(
                value, type_=f.type, length=f.length, zero_pad=f.zero_pad, codes=None
            )
            if problem:
                violations.append(Violation(path.name, lineno, f.name, value, *problem))
                row_ok = False
        if not row_ok:
            continue
        columns["_file"].append(path.name)
        columns["_line"].append(lineno)
        for f in spec.fields:
            value = raw[f.col - 1]
            columns[f.name].append(None if value == "" else value)

    columns["admission_date"] = [parse_date8(v) for v in columns["admission_date"]]
    columns["seq"] = [int(v) for v in columns["seq"]]
    schema = pa.schema(
        [("_file", pa.string()), ("_line", pa.int64())]
        + [
            (
                f.name,
                pa.date32()
                if f.name == "admission_date"
                else pa.int64()
                if f.name == "seq"
                else pa.string(),
            )
            for f in spec.fields
        ]
    )
    return ParseResult(pa.table(columns, schema=schema), violations)


@dataclass
class Yoshiki1Tables:
    forms: pa.Table
    diagnoses: pa.Table
    surgeries: pa.Table
    violations: list[Violation] = field(default_factory=list)

    def violations_table(self) -> pa.Table:
        return violations_table(self.violations)


def _item_defs(spec: Spec, code: str) -> dict[int, dict[str, Any]]:
    payload = spec.payloads[code]
    items = payload.get("items") or spec.item_sets[payload["item_set"]]
    return {int(k): v for k, v in items.items()}


def _check_items(
    rec: dict[str, Any], defs: dict[int, dict[str, Any]], code: str
) -> tuple[dict[str, str | None], list[Violation]]:
    out: dict[str, str | None] = {}
    problems: list[Violation] = []
    for no, d in defs.items():
        if d["name"] == "unused" or d.get("drop"):
            continue
        value = rec[f"payload{no}"]
        out[d["name"]] = value
        where = f"{code}.{no}:{d['name']}"
        if value is None:
            if d.get("required"):
                problems.append(
                    Violation(
                        rec["_file"],
                        rec["_line"],
                        where,
                        "",
                        "required",
                        "required payload is empty",
                    )
                )
            continue
        problem = check_value(
            value,
            type_=d.get("type", "string"),
            length=d.get("length"),
            zero_pad=False,
            codes=load_codes(d["codes"]) if "codes" in d else None,
        )
        if problem:
            problems.append(Violation(rec["_file"], rec["_line"], where, value, *problem))
    return out, problems


FORM_COLUMNS = {
    "birth_date": pa.date32(),
    "sex": pa.string(),
    "admission_route": pa.string(),
    "admission_type": pa.string(),
    "ambulance": pa.string(),
    "discharge_date": pa.date32(),
    "discharge_to": pa.string(),
    "discharge_outcome": pa.string(),
    "death_within_24h": pa.string(),
    "period_start": pa.date32(),
    "period_end": pa.date32(),
}
KEY_SCHEMA = [
    ("facility_code", pa.string()),
    ("data_id", pa.string()),
    ("admission_date", pa.date32()),
    ("stay_no", pa.string()),
    ("summary_no", pa.string()),
]


def pivot_yoshiki1(long: pa.Table, spec: Spec | None = None) -> Yoshiki1Tables:
    spec = spec or load_spec("dpc_yoshiki1")
    suspected = str(spec.extra.get("suspected_modifier", "8002"))
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for rec in long.to_pylist():
        groups[tuple(rec[k] for k in KEY)].append(rec)

    forms: list[dict[str, Any]] = []
    diagnoses: list[dict[str, Any]] = []
    surgeries: list[dict[str, Any]] = []
    violations: list[Violation] = []

    for key, recs in groups.items():
        keyd = dict(zip(KEY, key, strict=True))
        form: dict[str, Any] = dict(keyd)
        seen: set[tuple[str, int]] = set()
        for rec in recs:
            code = rec["code"]
            if code not in spec.payloads:
                continue
            payload = spec.payloads[code]
            ident = (code, rec["seq"])
            if ident in seen or (not payload.get("repeat") and rec["seq"] not in (0, 1)):
                violations.append(
                    Violation(
                        rec["_file"],
                        rec["_line"],
                        code,
                        str(rec["seq"]),
                        "duplicate_key",
                        "record repeated within one form",
                    )
                )
                continue
            seen.add(ident)
            values, problems = _check_items(rec, _item_defs(spec, code), code)
            violations += problems
            if payload.get("item_set") == "diagnosis":
                mods = [values.get(f"modifier{i}") for i in range(1, 5)]
                mods_present = [m for m in mods if m]
                name = values.get("disease_name")
                diagnoses.append(
                    keyd
                    | {
                        "role": payload["name"],
                        "seq": rec["seq"],
                        "icd10": values.get("icd10"),
                        "disease_code": values.get("disease_code"),
                        "modifiers": " ".join(mods_present) or None,
                        "suspected": suspected in mods_present,
                        "disease_name": normalize_text(name) if name else None,
                    }
                )
            elif payload["name"] == "surgery":
                surgeries.append(
                    keyd
                    | {
                        "seq": rec["seq"],
                        "surgery_date": parse_date8(values.get("surgery_date") or ""),
                        "surgery_code": values.get("surgery_code"),
                        "surgery_name": values.get("surgery_name"),
                    }
                )
            else:
                for name, value in values.items():
                    if name not in FORM_COLUMNS:
                        continue
                    if name == "birth_date":
                        form[name] = partial_date(value or "")
                    elif FORM_COLUMNS[name] == pa.date32():
                        form[name] = parse_date8(value or "")
                    else:
                        form[name] = value
        for required_code in ("A000010", "A000030"):
            if (required_code, 0) not in seen and (required_code, 1) not in seen:
                first = recs[0]
                violations.append(
                    Violation(
                        first["_file"],
                        first["_line"],
                        required_code,
                        "",
                        "missing_record",
                        "required record is missing",
                    )
                )
        forms.append(form)

    dx_schema = pa.schema(
        [
            *KEY_SCHEMA,
            ("role", pa.string()),
            ("seq", pa.int64()),
            ("icd10", pa.string()),
            ("disease_code", pa.string()),
            ("modifiers", pa.string()),
            ("suspected", pa.bool_()),
            ("disease_name", pa.string()),
        ]
    )
    op_schema = pa.schema(
        [
            *KEY_SCHEMA,
            ("seq", pa.int64()),
            ("surgery_date", pa.date32()),
            ("surgery_code", pa.string()),
            ("surgery_name", pa.string()),
        ]
    )
    form_schema = pa.schema(KEY_SCHEMA + list(FORM_COLUMNS.items()))
    return Yoshiki1Tables(
        forms=pa.Table.from_pylist(forms, schema=form_schema),
        diagnoses=pa.Table.from_pylist(diagnoses, schema=dx_schema),
        surgeries=pa.Table.from_pylist(surgeries, schema=op_schema),
        violations=violations,
    )
