"""Invariants every CDM output must satisfy. Each returns a list of problems."""

from __future__ import annotations

from collections import Counter

import pyarrow as pa


def check_invariants(cdm: dict[str, pa.Table]) -> list[str]:
    problems: list[str] = []
    person_ids = cdm["person"].column("person_id").to_pylist()
    dup = [p for p, n in Counter(person_ids).items() if n > 1]
    if dup:
        problems.append(f"person: duplicate person_id {dup[:5]}")
    known = set(person_ids)

    periods: dict[int, tuple[object, object]] = {}
    for r in cdm["observation_period"].to_pylist():
        if r["person_id"] in periods:
            problems.append(f"observation_period: more than one period for {r['person_id']}")
        periods[r["person_id"]] = (
            r["observation_period_start_date"],
            r["observation_period_end_date"],
        )

    events = {
        "visit_occurrence": ("visit_start_date", "visit_end_date"),
        "visit_detail": ("visit_detail_start_date", "visit_detail_end_date"),
        "death": ("death_date", "death_date"),
        "condition_occurrence": ("condition_start_date", "condition_start_date"),
        "drug_exposure": ("drug_exposure_start_date", "drug_exposure_end_date"),
        "procedure_occurrence": ("procedure_date", "procedure_date"),
    }
    for table, (start_col, end_col) in events.items():
        if table not in cdm:
            continue
        for r in cdm[table].to_pylist():
            pid, s, e = r["person_id"], r[start_col], r[end_col]
            if pid not in known:
                problems.append(f"{table}: person_id {pid} not in person")
                continue
            if s > e:
                problems.append(f"{table}: start after end for person {pid}")
            ps, pe = periods.get(pid, (None, None))
            if ps is None or s < ps or e > pe:  # type: ignore[operator]
                problems.append(f"{table}: outside observation_period for person {pid}")

    visits = {r["visit_occurrence_id"]: r for r in cdm["visit_occurrence"].to_pylist()}
    for r in cdm["visit_detail"].to_pylist():
        v = visits.get(r["visit_occurrence_id"])
        if v is None:
            problems.append(f"visit_detail {r['visit_detail_id']}: unknown visit")
        elif not (
            v["visit_start_date"] <= r["visit_detail_start_date"]
            and r["visit_detail_end_date"] <= v["visit_end_date"]
        ):
            problems.append(f"visit_detail {r['visit_detail_id']}: outside its visit")
    return problems
