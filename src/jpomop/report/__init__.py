"""Mapping coverage per domain, read back from a CDM DuckDB file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb

DOMAINS = {
    "condition_occurrence": ("condition_concept_id", "condition_source_value"),
    "drug_exposure": ("drug_concept_id", "drug_source_value"),
    "procedure_occurrence": ("procedure_concept_id", "procedure_source_value"),
}


@dataclass(frozen=True)
class Coverage:
    table: str
    rows: int
    mapped_rows: int
    codes: int
    mapped_codes: int
    top_unmapped: list[tuple[str, int]]

    @property
    def row_rate(self) -> float:
        return self.mapped_rows / self.rows if self.rows else 0.0

    @property
    def code_rate(self) -> float:
        return self.mapped_codes / self.codes if self.codes else 0.0


def coverage(cdm: Path, top: int = 10) -> list[Coverage]:
    con = duckdb.connect(str(cdm), read_only=True)
    out = []
    try:
        tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables")
                  .fetchall()}
        for table, (cid, src) in DOMAINS.items():
            if table not in tables:
                continue
            res = con.execute(f"""
                SELECT count(*), count(*) FILTER (WHERE {cid} <> 0),
                       count(DISTINCT {src}),
                       count(DISTINCT {src}) FILTER (WHERE {cid} <> 0)
                FROM {table}""").fetchone()
            assert res is not None
            unmapped = con.execute(f"""
                SELECT {src}, count(*) AS n FROM {table} WHERE {cid} = 0
                GROUP BY 1 ORDER BY n DESC, 1 LIMIT {top}""").fetchall()
            rows, mapped_rows, codes, mapped_codes = res
            out.append(Coverage(table, rows, mapped_rows, codes, mapped_codes,
                                [(s, n) for s, n in unmapped]))
    finally:
        con.close()
    return out
