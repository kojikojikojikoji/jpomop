"""Checks that need both Form 1 and the EF file."""

from __future__ import annotations

from typing import Any

import pyarrow as pa

from jpomop.parse.fields import Violation


def check_cross_file(
    ef: pa.Table, forms: pa.Table, ef_file: str = "", y1_file: str = ""
) -> list[Violation]:
    """Compare stays in the EF file with whole-stay forms (統括診療情報番号 0, or Z
    when there is no 0 yet).

    A stay is (facility_code, data_id, admission_date).
    """
    parents: dict[tuple[Any, ...], dict[str, Any]] = {}
    interim: dict[tuple[Any, ...], dict[str, Any]] = {}
    for f in forms.to_pylist():
        stay = (f["facility_code"], f["data_id"], f["admission_date"])
        if f["summary_no"] == "0":
            parents[stay] = f
        elif f["summary_no"] == "Z":
            interim[stay] = f
    for stay, f in interim.items():  # still in hospital: only the day-90 form exists
        parents.setdefault(stay, f)

    out: list[Violation] = []
    ef_stays: set[tuple[Any, ...]] = set()
    for row in ef.select(
        ["_line", "facility_code", "data_id", "admission_date", "discharge_date", "exec_date"]
    ).to_pylist():
        stay = (row["facility_code"], row["data_id"], row["admission_date"])
        first_time = stay not in ef_stays
        ef_stays.add(stay)
        if stay not in parents:
            if first_time:
                out.append(
                    Violation(
                        ef_file,
                        row["_line"],
                        "data_id",
                        row["data_id"],
                        "ef_without_yoshiki1",
                        "no Form 1 for this stay",
                    )
                )
            continue
        d = row["exec_date"]
        end = row["discharge_date"]
        if d is not None and (d < row["admission_date"] or (end is not None and d > end)):
            out.append(
                Violation(
                    ef_file,
                    row["_line"],
                    "exec_date",
                    d.isoformat(),
                    "exec_outside_stay",
                    "date of service is outside the stay",
                )
            )
    for stay, f in parents.items():
        if stay not in ef_stays:
            out.append(
                Violation(
                    y1_file,
                    0,
                    "data_id",
                    f["data_id"],
                    "yoshiki1_without_ef",
                    "no EF records for this stay",
                )
            )
    return out
