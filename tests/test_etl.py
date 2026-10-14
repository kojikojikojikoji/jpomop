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
        1950,
        1,
        2,
    )
    assert len(person["person_source_value"]) == 16
    assert "0000000001" not in person["person_source_value"]
    visit = cdm["visit_occurrence"].to_pylist()[0]
    assert visit["visit_start_date"] == date(2026, 6, 10)
    assert visit["visit_end_date"] == date(2026, 6, 15)
    assert visit["admitted_from_source_value"] == "1"


def test_death_only_for_outcome_6_or_7(tmp_path: Path) -> None:
    y1 = basic_form("0000000001", outcome="6", discharge_to="8") + basic_form(
        "0000000002", outcome="5", discharge_to="8"
    )
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
    assert [
        (
            d["visit_detail_source_value"],
            d["visit_detail_start_date"].day,
            d["visit_detail_end_date"].day,
        )
        for d in details
    ] == [("W1", 10, 11), ("ICU", 12, 12), ("W1", 13, 13)]
    assert details[1]["preceding_visit_detail_id"] == details[0]["visit_detail_id"]


def test_ward_group_forms_are_counted_not_converted(tmp_path: Path) -> None:
    y1 = [
        *basic_form(),
        y1_line("A000010", {1: "19500102", 2: "2", 3: "1000001"}, summary="1"),
        y1_line("A000030", {1: "20260612", 2: "0", 3: "1", 4: "0"}, summary="1"),
    ]
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


def test_conditions(tmp_path: Path) -> None:
    from jpomop.vocab import Vocab

    y1 = basic_form()
    # same ICD-10 as the main diagnosis, in a lower-priority field
    y1.append(y1_line("A006050", {2: "J189", 4: "4860021", 9: "肺炎"}, seq="1"))
    vocab = Vocab(icd10={"J18.9": (900000001, [900000101])})
    forms_t = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", y1)).table)
    cdm, report = build_cdm(
        forms_t.forms,
        read_ef(write(tmp_path / "ef.txt", [ef_line()])).table,
        forms_t.diagnoses,
        vocab,
    )
    rows = cdm["condition_occurrence"].to_pylist()
    assert sorted(r["condition_source_value"] for r in rows) == ["E119", "I10", "J189"]
    j18 = next(r for r in rows if r["condition_source_value"] == "J189")
    assert j18["condition_concept_id"] == 900000101
    assert j18["condition_status_source_value"] == "dx_main"
    assert j18["condition_status_concept_id"] == 32902
    assert j18["condition_start_date"] == date(2026, 6, 10)
    assert report.skipped_rows["condition_occurrence"] == {"duplicate_in_stay": 1}
    assert report.invariant_problems == []


def test_code_with_two_standard_concepts_gives_two_rows(tmp_path: Path) -> None:
    from jpomop.vocab import Vocab

    vocab = Vocab(icd10={"J18.9": (900000001, [900000101, 900000102])})
    forms_t = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", basic_form())).table)
    cdm, report = build_cdm(
        forms_t.forms,
        read_ef(write(tmp_path / "ef.txt", [ef_line()])).table,
        forms_t.diagnoses,
        vocab,
    )
    rows = [
        r for r in cdm["condition_occurrence"].to_pylist() if r["condition_source_value"] == "J189"
    ]
    assert [r["condition_concept_id"] for r in rows] == [900000101, 900000102]
    assert {r["condition_source_concept_id"] for r in rows} == {900000001}
    ids = [r["condition_occurrence_id"] for r in cdm["condition_occurrence"].to_pylist()]
    assert ids == list(range(1, len(ids) + 1))
    assert report.invariant_problems == []


def test_suspected_diagnosis_is_left_out(tmp_path: Path) -> None:
    forms_t = pivot_yoshiki1(
        read_yoshiki1(write(tmp_path / "y1.txt", basic_form(dx_modifiers=("8002",)))).table
    )
    cdm, report = build_cdm(
        forms_t.forms, read_ef(write(tmp_path / "ef.txt", [ef_line()])).table, forms_t.diagnoses
    )
    sources = [r["condition_source_value"] for r in cdm["condition_occurrence"].to_pylist()]
    assert "J189" not in sources
    assert report.skipped_rows["condition_occurrence"]["suspected"] == 1


def test_drugs_and_procedures(tmp_path: Path) -> None:
    ef = [
        ef_line(),  # drug
        ef_line(c17="001000000000"),  # brought from home
        ef_line(c17="100000000000", c24="20260615"),  # discharge prescription
        ef_line(c5="50", c9="150000001", c10="K9999", c21="1"),  # surgery
        ef_line(c5="90", c9="190000001"),  # room charge, not a procedure
    ]
    cdm, report = cdm_from(tmp_path, basic_form(), ef)
    drugs = cdm["drug_exposure"].to_pylist()
    assert len(drugs) == 2
    assert drugs[0]["drug_source_value"] == "620000001"
    assert drugs[0]["quantity"] == 2.0
    assert drugs[1]["stop_reason"] == "discharge_prescription"
    assert report.skipped_rows["drug_exposure"] == {"brought_from_home": 1}
    procs = cdm["procedure_occurrence"].to_pylist()
    assert [(p["procedure_source_value"], p["modifier_source_value"]) for p in procs] == [
        ("150000001", "K9999")
    ]
    assert report.invariant_problems == []


def test_interim_form_used_only_without_whole_stay_form(tmp_path: Path) -> None:
    # patient 1: interim form only (still in hospital); patient 2: both
    def interim(patient: str) -> list[str]:
        return [
            y1_line("A000010", {1: "19500102", 2: "1", 3: "1000001"}, summary="Z", patient=patient),
            y1_line("A000030", {2: "b", 3: "9", 4: "0"}, summary="Z", patient=patient),
        ]

    y1 = interim("0000000001") + interim("0000000002") + basic_form("0000000002")
    ef = [ef_line(c3="00000000", c24="20260620"), ef_line(c2="0000000002")]
    cdm, report = cdm_from(tmp_path, y1, ef)
    visits = {v["person_id"]: v for v in cdm["visit_occurrence"].to_pylist()}
    assert len(visits) == 2
    assert visits[1]["visit_end_date"] == date(2026, 6, 20)  # last date of service
    assert visits[2]["visit_end_date"] == date(2026, 6, 15)
    assert report.skipped_forms == {"interim_form_used": 1, "summary_no=Z": 1}
    assert report.invariant_problems == []


def test_same_day_stays_become_one_visit(tmp_path: Path) -> None:
    def day_stay(stay_no: str) -> list[str]:
        return [
            line.replace("\t20260610\t0\t0\t", f"\t20260610\t{stay_no}\t0\t", 1)
            for line in [
                y1_line("A000010", {1: "19500102", 2: "2", 3: "1000001"}),
                y1_line("A000030", {1: "20260610", 2: "1", 3: "1", 4: "0"}),
            ]
        ]

    cdm, report = cdm_from(
        tmp_path, day_stay("1") + day_stay("2"), [ef_line(c3="20260610", c24="20260610")]
    )
    assert cdm["visit_occurrence"].num_rows == 1
    assert report.skipped_forms == {"same_day_stays_merged": 1}
    assert report.invariant_problems == []


def test_stay_after_death_is_reported(tmp_path: Path) -> None:
    first = basic_form(outcome="6", discharge_to="8")
    second = [
        y1_line("A000010", {1: "19500102", 2: "2", 3: "1000001"}, admission="20260620"),
        y1_line("A000020", {1: "20260620", 2: "1", 5: "100", 6: "0"}, admission="20260620"),
        y1_line("A000030", {1: "20260622", 2: "1", 3: "1", 4: "0"}, admission="20260620"),
    ]
    ef = [ef_line(), ef_line(c3="20260622", c4="20260620", c24="20260621")]
    _, report = cdm_from(tmp_path, first + second, ef)
    assert report.invariant_problems == ["visit_occurrence: stay starts after death for 1"]


def test_synthetic_patients_have_no_stay_after_death(tmp_path: Path) -> None:
    from jpomop.synth import generate

    m = generate(tmp_path / "s", 500)
    report = run_etl([m.yoshiki1], [m.ef], tmp_path / "cdm.duckdb")
    assert report.rows["death"] > 0
    assert report.invariant_problems == []
