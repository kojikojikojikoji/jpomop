from pathlib import Path

from helpers import fake_athena, fake_drug_master

from jpomop.vocab import Vocab, build_vocab, icd10_candidates


def test_icd10_candidates() -> None:
    assert icd10_candidates("S7200") == ["S72.00", "S72.0", "S72"]
    assert icd10_candidates("J189") == ["J18.9", "J18"]
    assert icd10_candidates("I10") == ["I10"]


def test_build_and_map(tmp_path: Path) -> None:
    master = fake_drug_master(
        tmp_path / "y.csv", {"620000001": "1111111F1011", "620000002": "2222222F1011"}
    )
    kimura = tmp_path / "kimura.csv"
    kimura.write_text(
        "Category,NHIDPLC,OSV_ID,OSV_NAME\nPO,1111111F1011,900001001,x\nPO,2222222F1011,N/A,\n",
        encoding="utf-8",
    )
    out = tmp_path / "vocab.duckdb"
    report = build_vocab(fake_athena(tmp_path / "athena"), [master], kimura, out)
    assert (report.icd10_codes, report.icd10_mapped) == (3, 3)
    assert (report.receipt_drugs, report.receipt_drugs_mapped) == (2, 1)

    v = Vocab.load(out)
    assert v.map_icd10("J189").concept_id == 900000101
    assert v.map_icd10("J189").source_concept_id == 900000001
    assert v.map_icd10("S7200").concept_id == 900000103  # falls back to S72.0
    assert v.map_icd10("Z999").concept_id == 0
    assert v.map_drug("620000001").concept_id == 900001001
    assert v.map_drug("620000002").concept_id == 0
