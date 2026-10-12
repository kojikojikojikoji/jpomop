"""Conditions from Form 1, drugs and procedures from the EF file."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

import pyarrow as pa

from jpomop.etl import concepts as C
from jpomop.etl import schema as S
from jpomop.vocab import Vocab

Stay = tuple[str, str, date]

# When the same ICD-10 code appears in several Form 1 fields for one stay,
# keep one row, labelled with the first field in this order.
ROLE_PRIORITY = [
    "dx_main",
    "dx_resource1",
    "dx_trigger",
    "dx_resource2",
    "dx_comorbid",
    "dx_complication",
]

DRUG_PREFIX = "6"  # 医薬品 (receipt codes, p192-193)
PROCEDURE_PREFIX = "1"  # 医科診療行為
NOT_A_PROCEDURE = {"90", "92", "97"}  # 入院基本料, 特定入院料, 食事


def build_condition_occurrence(
    diagnoses: pa.Table, visits: pa.Table, vids: dict[Stay, int], vocab: Vocab
) -> tuple[pa.Table, Counter[str]]:
    """Returns the table and counts of rows left out, by reason."""
    vinfo = {r["visit_occurrence_id"]: r for r in visits.to_pylist()}
    skipped: Counter[str] = Counter()
    best: dict[tuple[int, str], dict[str, Any]] = {}
    for dx in diagnoses.to_pylist():
        if dx["summary_no"] != "0":
            continue
        vid = vids.get((dx["facility_code"], dx["data_id"], dx["admission_date"]))
        if vid is None:
            skipped["no_visit"] += 1
            continue
        if dx["suspected"]:
            skipped["suspected"] += 1
            continue
        if not dx["icd10"]:
            skipped["no_icd10"] += 1
            continue
        key = (vid, dx["icd10"])
        if key in best:
            skipped["duplicate_in_stay"] += 1
            if ROLE_PRIORITY.index(best[key]["role"]) <= ROLE_PRIORITY.index(dx["role"]):
                continue
        best[key] = dx
    rows: list[dict[str, Any]] = []
    for n, ((vid, icd), dx) in enumerate(sorted(best.items()), start=1):
        v = vinfo[vid]
        m = vocab.map_icd10(icd)
        rows.append(
            {
                "condition_occurrence_id": n,
                "person_id": v["person_id"],
                "condition_concept_id": m.concept_id,
                "condition_start_date": v["visit_start_date"],
                "condition_type_concept_id": C.TYPE_CLAIM,
                "condition_status_concept_id": C.CONDITION_STATUS.get(dx["role"], C.UNKNOWN),
                "visit_occurrence_id": vid,
                "condition_source_value": icd,
                "condition_source_concept_id": m.source_concept_id,
                "condition_status_source_value": dx["role"],
            }
        )
    return pa.Table.from_pylist(rows, schema=S.CONDITION_OCCURRENCE), skipped


def _ef_events(ef: pa.Table, vids: dict[Stay, int]) -> list[tuple[int, dict[str, Any]]]:
    out = []
    for r in ef.to_pylist():
        vid = vids.get((r["facility_code"], r["data_id"], r["admission_date"]))
        if vid is not None and r["exec_date"] is not None:
            out.append((vid, r))
    return out


def build_drug_exposure(
    ef: pa.Table, visits: pa.Table, vids: dict[Stay, int], vocab: Vocab
) -> tuple[pa.Table, Counter[str]]:
    vinfo = {r["visit_occurrence_id"]: r for r in visits.to_pylist()}
    skipped: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for vid, r in _ef_events(ef, vids):
        if not r["receipt_code"].startswith(DRUG_PREFIX):
            continue
        flags = r["detail_flags"] or "000000000000"
        if flags[2] != "0":  # 持参薬 (brought from home), p195
            skipped["brought_from_home"] += 1
            continue
        m = vocab.map_drug(r["receipt_code"])
        rows.append(
            {
                "drug_exposure_id": len(rows) + 1,
                "person_id": vinfo[vid]["person_id"],
                "drug_concept_id": m.concept_id,
                "drug_exposure_start_date": r["exec_date"],
                "drug_exposure_end_date": r["exec_date"],
                "drug_type_concept_id": C.TYPE_CLAIM,
                "quantity": r["quantity"],
                "route_concept_id": C.UNKNOWN,
                "visit_occurrence_id": vid,
                "drug_source_value": r["receipt_code"],
                "drug_source_concept_id": C.UNKNOWN,
                "route_source_value": r["data_kubun"],
                "dose_unit_source_value": r["unit_code"],
                "stop_reason": "discharge_prescription" if flags[0] == "1" else None,
            }
        )
    return pa.Table.from_pylist(rows, schema=S.DRUG_EXPOSURE), skipped


def build_procedure_occurrence(ef: pa.Table, visits: pa.Table, vids: dict[Stay, int]) -> pa.Table:
    """Procedures stay as source codes (concept_id 0) until a mapping exists."""
    vinfo = {r["visit_occurrence_id"]: r for r in visits.to_pylist()}
    rows: list[dict[str, Any]] = []
    for vid, r in _ef_events(ef, vids):
        if not r["receipt_code"].startswith(PROCEDURE_PREFIX):
            continue
        if r["data_kubun"] in NOT_A_PROCEDURE:
            continue
        rows.append(
            {
                "procedure_occurrence_id": len(rows) + 1,
                "person_id": vinfo[vid]["person_id"],
                "procedure_concept_id": C.UNKNOWN,
                "procedure_date": r["exec_date"],
                "procedure_type_concept_id": C.TYPE_CLAIM,
                "modifier_concept_id": C.UNKNOWN,
                "quantity": r["act_count"],
                "visit_occurrence_id": vid,
                "procedure_source_value": r["receipt_code"],
                "procedure_source_concept_id": C.UNKNOWN,
                "modifier_source_value": r["kaishaku_no"],
            }
        )
    return pa.Table.from_pylist(rows, schema=S.PROCEDURE_OCCURRENCE)
