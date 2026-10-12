"""Turn parsed DPC tables into OMOP CDM v5.4 tables."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from jpomop.etl.build import (
    build_death,
    build_observation_period,
    build_person,
    build_visit_detail,
    build_visit_occurrence,
    person_ids,
    visit_ids,
    whole_stay_forms,
)
from jpomop.etl.checks import check_invariants
from jpomop.etl.clinical import (
    build_condition_occurrence,
    build_drug_exposure,
    build_procedure_occurrence,
)
from jpomop.parse import pivot_yoshiki1, read_ef, read_yoshiki1
from jpomop.vocab import Vocab

TABLE_ORDER = [
    "person", "observation_period", "visit_occurrence", "visit_detail",
    "condition_occurrence", "procedure_occurrence", "drug_exposure", "death",
]


@dataclass
class EtlReport:
    rows: dict[str, int]
    skipped_forms: dict[str, int] = field(default_factory=dict)
    skipped_rows: dict[str, dict[str, int]] = field(default_factory=dict)
    n_violations: int = 0
    invariant_problems: list[str] = field(default_factory=list)


def build_cdm(forms: pa.Table, ef: pa.Table, diagnoses: pa.Table | None = None,
              vocab: Vocab | None = None) -> tuple[dict[str, pa.Table], EtlReport]:
    vocab = vocab or Vocab()
    whole = whole_stay_forms(forms)
    pids, vids = person_ids(whole), visit_ids(whole)
    visits = build_visit_occurrence(whole, pids, vids)
    cdm = {
        "person": build_person(whole, pids),
        "observation_period": build_observation_period(visits),
        "visit_occurrence": visits,
        "visit_detail": build_visit_detail(ef, visits, vids),
        "death": build_death(whole, pids),
    }
    skipped_rows: dict[str, dict[str, int]] = {}
    if diagnoses is not None:
        cdm["condition_occurrence"], skip = build_condition_occurrence(
            diagnoses, visits, vids, vocab)
        skipped_rows["condition_occurrence"] = dict(skip)
    cdm["drug_exposure"], skip = build_drug_exposure(ef, visits, vids, vocab)
    skipped_rows["drug_exposure"] = dict(skip)
    cdm["procedure_occurrence"] = build_procedure_occurrence(ef, visits, vids)
    skipped = Counter(f"summary_no={s}" for s in forms.column("summary_no").to_pylist()
                      if s != "0")
    report = EtlReport(
        rows={k: t.num_rows for k, t in cdm.items()},
        skipped_forms=dict(skipped),
        skipped_rows=skipped_rows,
        invariant_problems=check_invariants(cdm),
    )
    return cdm, report


def write_cdm(cdm: dict[str, pa.Table], out: Path,
              fmt: Literal["duckdb", "parquet"] = "duckdb") -> None:
    if fmt == "parquet":
        out.mkdir(parents=True, exist_ok=True)
        for name in (n for n in TABLE_ORDER if n in cdm):
            pq.write_table(cdm[name], out / f"{name}.parquet")
        return
    out.unlink(missing_ok=True)
    con = duckdb.connect(str(out))
    try:
        for name in (n for n in TABLE_ORDER if n in cdm):
            tbl = cdm[name]  # noqa: F841  (read by DuckDB through the local variable)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM tbl")
    finally:
        con.close()


def run_etl(yoshiki1: list[Path], ef: list[Path], out: Path,
            fmt: Literal["duckdb", "parquet"] = "duckdb",
            vocab: Path | None = None) -> EtlReport:
    forms, dxs, efs, n_violations = [], [], [], 0
    for p in yoshiki1:
        res = read_yoshiki1(p)
        tables = pivot_yoshiki1(res.table)
        forms.append(tables.forms)
        dxs.append(tables.diagnoses)
        n_violations += len(res.violations) + len(tables.violations)
    for p in ef:
        res = read_ef(p)
        efs.append(res.table)
        n_violations += len(res.violations)
    cdm, report = build_cdm(pa.concat_tables(forms), pa.concat_tables(efs),
                            pa.concat_tables(dxs), Vocab.load(vocab) if vocab else None)
    report.n_violations = n_violations
    write_cdm(cdm, out, fmt)
    return report
