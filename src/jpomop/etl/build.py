"""Build CDM tables from parsed DPC tables.

Keys:
- patient: (facility_code, data_id)
- stay:    (facility_code, data_id, admission_date)

Only whole-stay forms (統括診療情報番号 0) become visits. Ward-group
forms, short readmissions (A, B) and the day-90 interim form (Z) are
counted by `run_etl` but not converted yet; see docs/adr.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from typing import Any

import pyarrow as pa

from jpomop.etl import concepts as C
from jpomop.etl import schema as S
from jpomop.spec import load_code_table

Patient = tuple[str, str]
Stay = tuple[str, str, date]


def source_value(facility_code: str, data_id: str) -> str:
    """Hash of the patient key, so the hospital's data ID never leaves the ETL."""
    return hashlib.sha256(f"{facility_code}:{data_id}".encode()).hexdigest()[:16]


def whole_stay_forms(forms: pa.Table) -> list[dict[str, Any]]:
    rows = [f for f in forms.to_pylist() if f["summary_no"] == "0"]
    return sorted(rows, key=lambda f: (f["facility_code"], f["data_id"], f["admission_date"]))


def person_ids(forms: list[dict[str, Any]]) -> dict[Patient, int]:
    keys = sorted({(f["facility_code"], f["data_id"]) for f in forms})
    return {k: i for i, k in enumerate(keys, start=1)}


def visit_ids(forms: list[dict[str, Any]]) -> dict[Stay, int]:
    keys = sorted({(f["facility_code"], f["data_id"], f["admission_date"]) for f in forms})
    return {k: i for i, k in enumerate(keys, start=1)}


def build_person(forms: list[dict[str, Any]], pids: dict[Patient, int]) -> pa.Table:
    first: dict[Patient, dict[str, Any]] = {}
    for f in forms:  # forms are sorted, so the first form per patient is the earliest stay
        first.setdefault((f["facility_code"], f["data_id"]), f)
    rows = []
    for key, pid in sorted(pids.items(), key=lambda kv: kv[1]):
        f = first[key]
        b: date | None = f["birth_date"]
        rows.append(
            {
                "person_id": pid,
                "gender_concept_id": C.GENDER.get(f["sex"] or "", C.UNKNOWN),
                "year_of_birth": b.year if b else None,
                "month_of_birth": b.month if b else None,
                "day_of_birth": b.day if b else None,
                "race_concept_id": C.UNKNOWN,
                "ethnicity_concept_id": C.UNKNOWN,
                "person_source_value": source_value(*key),
                "gender_source_value": f["sex"],
            }
        )
    return pa.Table.from_pylist(rows, schema=S.PERSON)


def build_visit_occurrence(
    forms: list[dict[str, Any]], pids: dict[Patient, int], vids: dict[Stay, int]
) -> pa.Table:
    rows = []
    for f in forms:
        stay = (f["facility_code"], f["data_id"], f["admission_date"])
        rows.append(
            {
                "visit_occurrence_id": vids[stay],
                "person_id": pids[stay[:2]],
                "visit_concept_id": C.INPATIENT_VISIT,
                "visit_start_date": f["admission_date"],
                "visit_end_date": f["discharge_date"] or f["admission_date"],
                "visit_type_concept_id": C.TYPE_CLAIM,
                "visit_source_value": "dpc_yoshiki1",
                "visit_source_concept_id": C.UNKNOWN,
                "admitted_from_concept_id": C.UNKNOWN,
                "admitted_from_source_value": f["admission_route"],
                "discharged_to_concept_id": C.UNKNOWN,
                "discharged_to_source_value": f["discharge_to"],
            }
        )
    return pa.Table.from_pylist(rows, schema=S.VISIT_OCCURRENCE)


def build_visit_detail(ef: pa.Table, visits: pa.Table, vids: dict[Stay, int]) -> pa.Table:
    """One row per run of consecutive service dates on the same ward."""
    vinfo = {r["visit_occurrence_id"]: r for r in visits.to_pylist()}
    days: dict[int, dict[date, str]] = defaultdict(dict)
    for r in ef.select(
        ["facility_code", "data_id", "admission_date", "exec_date", "ward_code"]
    ).to_pylist():
        vid = vids.get((r["facility_code"], r["data_id"], r["admission_date"]))
        if vid is None or r["exec_date"] is None:
            continue
        days[vid].setdefault(r["exec_date"], r["ward_code"])
    rows = []
    next_id = 1
    for vid in sorted(days):
        v = vinfo[vid]
        runs: list[list[Any]] = []  # [ward, start, end]
        for d in sorted(days[vid]):
            ward = days[vid][d]
            if runs and runs[-1][0] == ward:
                runs[-1][2] = d
            else:
                runs.append([ward, d, d])
        prev = None
        for ward, start, end in runs:
            start = max(start, v["visit_start_date"])
            end = min(end, v["visit_end_date"])
            rows.append(
                {
                    "visit_detail_id": next_id,
                    "person_id": v["person_id"],
                    "visit_detail_concept_id": C.INPATIENT_VISIT,
                    "visit_detail_start_date": start,
                    "visit_detail_end_date": end,
                    "visit_detail_type_concept_id": C.TYPE_CLAIM,
                    "visit_detail_source_value": ward,
                    "visit_detail_source_concept_id": C.UNKNOWN,
                    "admitted_from_concept_id": C.UNKNOWN,
                    "discharged_to_concept_id": C.UNKNOWN,
                    "preceding_visit_detail_id": prev,
                    "visit_occurrence_id": vid,
                }
            )
            prev = next_id
            next_id += 1
    return pa.Table.from_pylist(rows, schema=S.VISIT_DETAIL)


def build_observation_period(visits: pa.Table) -> pa.Table:
    span: dict[int, list[date]] = {}
    for v in visits.to_pylist():
        s, e = v["visit_start_date"], v["visit_end_date"]
        if v["person_id"] in span:
            span[v["person_id"]][0] = min(span[v["person_id"]][0], s)
            span[v["person_id"]][1] = max(span[v["person_id"]][1], e)
        else:
            span[v["person_id"]] = [s, e]
    rows = [
        {
            "observation_period_id": pid,
            "person_id": pid,
            "observation_period_start_date": s,
            "observation_period_end_date": e,
            "period_type_concept_id": C.TYPE_CLAIM,
        }
        for pid, (s, e) in sorted(span.items())
    ]
    return pa.Table.from_pylist(rows, schema=S.OBSERVATION_PERIOD)


def build_death(forms: list[dict[str, Any]], pids: dict[Patient, int]) -> pa.Table:
    """A stay whose discharge outcome (退院時転帰) is death (6 or 7). Latest one per person."""
    death_codes = set(load_code_table("y1_discharge_outcome")["death"])
    latest: dict[int, date] = {}
    for f in forms:
        if f["discharge_outcome"] in death_codes and f["discharge_date"]:
            pid = pids[(f["facility_code"], f["data_id"])]
            latest[pid] = max(latest.get(pid, f["discharge_date"]), f["discharge_date"])
    rows = [
        {
            "person_id": pid,
            "death_date": d,
            "death_type_concept_id": C.TYPE_CLAIM,
            "cause_concept_id": C.UNKNOWN,
        }
        for pid, d in sorted(latest.items())
    ]
    return pa.Table.from_pylist(rows, schema=S.DEATH)
