from datetime import date
from pathlib import Path

from helpers import basic_form, ef_line, write, y1_line

from jpomop.parse import (
    check_cross_file,
    parse_date8,
    pivot_yoshiki1,
    read_ef,
    read_yoshiki1,
)


def rules(violations: list) -> list[str]:
    return sorted(v.rule for v in violations)


def test_parse_date8() -> None:
    assert parse_date8("20260611") == date(2026, 6, 11)
    assert parse_date8("20270229") is None
    assert parse_date8("00000000") is None
    assert parse_date8("2026061") is None


def test_valid_ef_row_is_typed(tmp_path: Path) -> None:
    res = read_ef(write(tmp_path / "ef.txt", [ef_line()]))
    assert res.violations == []
    row = res.table.to_pylist()[0]
    assert row["exec_date"] == date(2026, 6, 11)
    assert row["quantity"] == 2.0
    assert row["act_count"] == 1
    assert row["item_name"] == "架空錠10mg"  # full-width digits normalised
    assert "insurer_no" not in res.table.column_names
    assert "doctor_code" not in res.table.column_names


def test_still_in_hospital_discharge_date_is_null(tmp_path: Path) -> None:
    res = read_ef(write(tmp_path / "ef.txt", [ef_line(c3="00000000")]))
    assert res.violations == []
    assert res.table.column("discharge_date")[0].as_py() is None


def test_each_ef_problem_is_one_violation(tmp_path: Path) -> None:
    lines = [
        ef_line(c1="13123456"),  # facility code not zero-padded to 9
        ef_line(c5=""),  # required data_kubun empty
        ef_line(c24="20260631"),  # no such date
        ef_line(c5="12"),  # outpatient-only code
        ef_line(c12="abc"),  # quantity not a number
        ef_line(c9="62000000123"),  # receipt code too long
        "\t".join(["x"] * 30),  # wrong number of fields
    ]
    res = read_ef(write(tmp_path / "ef.txt", lines))
    assert rules(res.violations) == sorted(
        [
            "length",
            "required",
            "date_invalid",
            "code_not_in_table",
            "type",
            "length",
            "n_fields",
        ]
    )
    # unknown code keeps the row; malformed rows are dropped
    assert res.table.num_rows == 1


def test_bytes_outside_cp932_are_reported(tmp_path: Path) -> None:
    path = tmp_path / "ef.txt"
    line = ef_line(c11="NAME").encode("cp932").replace(b"NAME", b"\x85\x40")
    path.write_bytes(line + b"\r\n")
    res = read_ef(path)
    assert "encoding" in rules(res.violations)


def test_yoshiki1_pivot(tmp_path: Path) -> None:
    res = read_yoshiki1(write(tmp_path / "y1.txt", basic_form()))
    assert res.violations == []
    tables = pivot_yoshiki1(res.table)
    assert tables.violations == []
    form = tables.forms.to_pylist()[0]
    assert form["birth_date"] == date(1950, 1, 2)
    assert form["sex"] == "2"
    assert form["discharge_date"] == date(2026, 6, 15)
    dx = tables.diagnoses.to_pylist()
    assert [d["role"] for d in dx] == ["dx_main", "dx_comorbid", "dx_comorbid"]
    assert dx[1]["disease_name"] == "2型糖尿病"
    assert not any(d["suspected"] for d in dx)


def test_partial_birth_date(tmp_path: Path) -> None:
    lines = basic_form()
    lines[0] = y1_line("A000010", {1: "19500000", 2: "1", 3: "1000001"})
    tables = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", lines)).table)
    assert tables.forms.to_pylist()[0]["birth_date"] == date(1950, 1, 1)


def test_suspected_diagnosis(tmp_path: Path) -> None:
    lines = basic_form(dx_modifiers=("8002",))
    tables = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", lines)).table)
    main = next(d for d in tables.diagnoses.to_pylist() if d["role"] == "dx_main")
    assert main["suspected"] is True


def test_yoshiki1_payload_problems(tmp_path: Path) -> None:
    lines = basic_form()
    lines[0] = y1_line("A000010", {1: "19500102", 2: "3", 3: "1000001"})  # sex 3
    lines[2] = y1_line("A000030", {1: "20260615", 2: "1", 3: "1"})  # 24h death empty
    lines.append(y1_line("A006010", {2: "J189", 4: "4860021", 9: "肺炎"}))  # second main dx
    tables = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", lines)).table)
    assert rules(tables.violations) == ["code_not_in_table", "duplicate_key", "required"]


def test_missing_patient_record(tmp_path: Path) -> None:
    lines = basic_form()[1:]
    tables = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", lines)).table)
    assert rules(tables.violations) == ["missing_record"]


def test_cross_file(tmp_path: Path) -> None:
    y1 = basic_form() + basic_form("0000000002")
    forms = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", y1)).table).forms
    ef = read_ef(
        write(
            tmp_path / "ef.txt",
            [
                ef_line(),
                ef_line(c24="20260620"),  # after discharge
                ef_line(c2="0000000003"),  # no Form 1
                ef_line(c2="0000000003", c24="20260612"),
            ],
        )
    ).table
    found = rules(check_cross_file(ef, forms))
    assert found == ["ef_without_yoshiki1", "exec_outside_stay", "yoshiki1_without_ef"]


def test_impossible_birth_date_is_reported(tmp_path: Path) -> None:
    lines = basic_form()
    lines[0] = y1_line("A000010", {1: "19520230", 2: "1", 3: "1000001"})  # 30 February
    tables = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", lines)).table)
    assert [(v.field, v.rule) for v in tables.violations] == [
        ("A000010.1:birth_date", "date_invalid")
    ]
