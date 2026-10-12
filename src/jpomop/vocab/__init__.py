"""Build and use a local vocabulary for jpomop.

Nothing here is shipped with jpomop. Users download:

- OMOP vocabularies from Athena (https://athena.ohdsi.org) with ICD10,
  SNOMED, RxNorm and RxNorm Extension: CONCEPT.csv and
  CONCEPT_RELATIONSHIP.csv (tab-separated, with a header row).
- The drug master (医薬品マスター, y_*.csv) from
  https://www.hpdx.or.jp/seikyushiharai/tensuhyo/kihonmasta/kihonmasta_04.html
- Kimura et al. (2025) Japanese drug to RxNorm mapping, CC BY 4.0,
  https://doi.org/10.17632/y3756v8237.1 (Excel, or saved as CSV keeping the
  NHIDPLC and OSV_ID columns).

`build_vocab` joins them into one small DuckDB file.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import duckdb

# Column positions (1-based) in the drug master. Checked against
# y_ALL20261001.csv: 42 fields per row.
DRUG_MASTER_RECEIPT_COL = 3   # レセプト電算処理システム用コード
DRUG_MASTER_YJ_COL = 32       # 薬価基準収載医薬品コード


@dataclass(frozen=True)
class VocabBuildReport:
    icd10_codes: int
    icd10_mapped: int
    receipt_drugs: int
    receipt_drugs_mapped: int


def icd10_candidates(code: str) -> list[str]:
    """DPC writes ICD-10 without a dot and sometimes with a fifth character.

    Return Athena-style codes to try, most specific first: S7200 -> S72.00, S72.0, S72.
    """
    code = code.strip().upper()
    if len(code) <= 3:
        return [code]
    out = []
    for end in range(len(code), 3, -1):
        out.append(f"{code[:3]}.{code[3:end]}")
    out.append(code[:3])
    return out


def _read_drug_master(paths: list[Path]) -> list[tuple[str, str]]:
    rows: dict[str, str] = {}
    for p in paths:
        with p.open(encoding="cp932", newline="") as f:
            for r in csv.reader(f):
                if len(r) >= DRUG_MASTER_YJ_COL and r[DRUG_MASTER_YJ_COL - 1]:
                    rows[r[DRUG_MASTER_RECEIPT_COL - 1]] = r[DRUG_MASTER_YJ_COL - 1]
    return sorted(rows.items())


def _read_kimura(path: Path) -> list[tuple[str, int]]:
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError as e:  # pragma: no cover
            raise SystemExit("reading .xlsx needs: pip install 'jpomop[vocab]'") from e
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        records: list[dict[str, object]] = []
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            header = [str(h).strip() if h is not None else "" for h in next(it, ())]
            if "NHIDPLC" not in header or "OSV_ID" not in header:
                continue
            records += [dict(zip(header, row, strict=False)) for row in it]
    else:
        with path.open(encoding="utf-8-sig", newline="") as f:
            records = list(csv.DictReader(f))
    out = []
    for rec in records:
        code, cid = rec.get("NHIDPLC"), rec.get("OSV_ID")
        if code and cid not in (None, "", "N/A"):
            try:
                out.append((str(code).strip(), int(float(str(cid)))))
            except ValueError:
                continue
    return out


def build_vocab(athena_dir: Path, drug_master: list[Path], kimura: Path | None,
                out: Path) -> VocabBuildReport:
    out.unlink(missing_ok=True)
    con = duckdb.connect(str(out))
    try:
        opts = "delim='\t', header=true, quote='', all_varchar=true"
        con.execute(f"""
            CREATE TABLE icd10_map AS
            SELECT c.concept_code AS source_code,
                   CAST(c.concept_id AS BIGINT) AS source_concept_id,
                   CAST(t.concept_id AS BIGINT) AS concept_id
            FROM read_csv('{athena_dir / "CONCEPT.csv"}', {opts}) c
            LEFT JOIN read_csv('{athena_dir / "CONCEPT_RELATIONSHIP.csv"}', {opts}) r
              ON r.concept_id_1 = c.concept_id AND r.relationship_id = 'Maps to'
                 AND (r.invalid_reason IS NULL OR r.invalid_reason = '')
            LEFT JOIN read_csv('{athena_dir / "CONCEPT.csv"}', {opts}) t
              ON t.concept_id = r.concept_id_2 AND t.standard_concept = 'S'
            WHERE c.vocabulary_id = 'ICD10'
        """)
        con.execute("CREATE TABLE receipt_yj (receipt_code VARCHAR, yj_code VARCHAR)")
        con.executemany("INSERT INTO receipt_yj VALUES (?, ?)", _read_drug_master(drug_master))
        con.execute("CREATE TABLE yj_rxnorm (yj_code VARCHAR, concept_id BIGINT)")
        if kimura:
            con.executemany("INSERT INTO yj_rxnorm VALUES (?, ?)", _read_kimura(kimura))
        con.execute("""
            CREATE TABLE drug_map AS
            SELECT r.receipt_code, r.yj_code, min(k.concept_id) AS concept_id
            FROM receipt_yj r LEFT JOIN yj_rxnorm k USING (yj_code)
            GROUP BY 1, 2
        """)
        n = con.execute("""
            SELECT (SELECT count(DISTINCT source_code) FROM icd10_map),
                   (SELECT count(DISTINCT source_code) FROM icd10_map WHERE concept_id IS NOT NULL),
                   (SELECT count(*) FROM drug_map),
                   (SELECT count(*) FROM drug_map WHERE concept_id IS NOT NULL)
        """).fetchone()
    finally:
        con.close()
    assert n is not None
    return VocabBuildReport(*n)


@dataclass(frozen=True)
class ConceptMatch:
    concept_id: int
    source_concept_id: int
    source_value: str


class Vocab:
    """Lookups used by the ETL. An empty Vocab maps everything to 0."""

    def __init__(self, icd10: dict[str, tuple[int, int]] | None = None,
                 drugs: dict[str, int] | None = None) -> None:
        self._icd10 = icd10 or {}
        self._drugs = drugs or {}

    @classmethod
    def load(cls, path: Path) -> Vocab:
        con = duckdb.connect(str(path), read_only=True)
        try:
            icd: dict[str, tuple[int, int]] = {}
            for code, scid, cid in con.execute(
                "SELECT source_code, source_concept_id, concept_id FROM icd10_map "
                "ORDER BY concept_id NULLS LAST"
            ).fetchall():
                icd.setdefault(code, (scid, cid or 0))
            drugs = {code: cid for code, cid in con.execute(
                "SELECT receipt_code, concept_id FROM drug_map WHERE concept_id IS NOT NULL"
            ).fetchall()}
        finally:
            con.close()
        return cls(icd, drugs)

    def map_icd10(self, code: str) -> ConceptMatch:
        for cand in icd10_candidates(code):
            if cand in self._icd10:
                scid, cid = self._icd10[cand]
                return ConceptMatch(cid, scid, code)
        return ConceptMatch(0, 0, code)

    def map_drug(self, receipt_code: str) -> ConceptMatch:
        return ConceptMatch(self._drugs.get(receipt_code, 0), 0, receipt_code)
