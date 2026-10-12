from datetime import date
from pathlib import Path

import duckdb
from helpers import basic_form, ef_line, write, y1_line

from jpomop.etl import build_cdm, run_etl
from jpomop.parse import pivot_yoshiki1, read_ef, read_yoshiki1


def cdm_from(tmp_path: Path, y1: list[str], ef: list[str]):  # type: ignore[no-untyped-def]
    forms = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", y1)).table).forms
    return build_cdm(forms, read_ef(write(tmp_path / "ef.txt", ef)).table)


def test_person_and_visit(tmp_path: Path) -> None:
    cdm, report = cdm_from(tmp_path, basic_form(), [ef_line()])
    assert report.invariant_problems == []
    person = cdm["person"].to_pylist()[0]
    assert person["gender_concept_id"] == 8532
    assert (person["year_of_birth"], person["month_of_birth"], person["day_of_birth"]) == (
        1950, 1, 2)
    assert len(person["person_source_value"]) == 16
    assert "0000000001" not in person["person_source_value"]
    visit = cdm["visit_occurrence"].to_pylist()[0]
    assert visit["visit_start_date"] == date(2026, 6, 10)
    assert visit["visit_end_date"] == date(2026, 6, 15)
    assert visit["admitted_from_source_value"] == "1"


def test_death_only_for_outcome_6_or_7(tmp_path: Path) -> None:
    y1 = basic_form("0000000001", outcome="6", discharge_to="8") + basic_form(
        "0000000002", outcome="5", discharge_to="8")
    cdm, _ = cdm_from(tmp_path, y1, [ef_line()])
    deaths = cdm["death"].to_pylist()
    assert len(deaths) == 1
    assert deaths[0]["death_date"] == date(2026, 6, 15)


def test_ward_runs_become_visit_details(tmp_path: Path) -> None:
    ef = [
        ef_line(c24="20260610", c28="W1"),
        ef_line(c24="20260611", c28="W1"),
        ef_line(c24="20260612", c28="ICU"),
        ef_line(c24="20260613", c28="W1"),
    ]
    cdm, report = cdm_from(tmp_path, basic_form(), ef)
    assert report.invariant_problems == []
    details = cdm["visit_detail"].to_pylist()
    assert [(d["visit_detail_source_value"], d["visit_detail_start_date"].day,
             d["visit_detail_end_date"].day) for d in details] == [
        ("W1", 10, 11), ("ICU", 12, 12), ("W1", 13, 13)]
    assert details[1]["preceding_visit_detail_id"] == details[0]["visit_detail_id"]


def test_ward_group_forms_are_counted_not_converted(tmp_path: Path) -> None:
    y1 = basic_form() + [y1_line("A000010", {1: "19500102", 2: "2", 3: "1000001"}, summary="1"),
                         y1_line("A000030", {1: "20260612", 2: "0", 3: "1", 4: "0"}, summary="1")]
    cdm, report = cdm_from(tmp_path, y1, [ef_line()])
    assert cdm["visit_occurrence"].num_rows == 1
    assert report.skipped_forms == {"summary_no=1": 1}


def test_synthetic_end_to_end(tmp_path: Path) -> None:
    from jpomop.synth import generate

    m = generate(tmp_path / "synth", 100)
    out = tmp_path / "cdm.duckdb"
    report = run_etl([m.yoshiki1], [m.ef], out)
    assert report.n_violations == 0
    assert report.invariant_problems == []
    con = duckdb.connect(str(out), read_only=True)
    n_person = con.execute("select count(*) from person").fetchone()[0]  # type: ignore[index]
    n_visit = con.execute("select count(*) from visit_occurrence").fetchone()[0]  # type: ignore[index]
    con.close()
    assert n_person == 100
    assert n_visit == m.n_stays


def test_synthetic_is_reproducible(tmp_path: Path) -> None:
    from jpomop.synth import generate

    a = generate(tmp_path / "a", 50, seed=1)
    b = generate(tmp_path / "b", 50, seed=1)
    c = generate(tmp_path / "c", 50, seed=2)
    assert a.sha256 == b.sha256
    assert a.sha256 != c.sha256
