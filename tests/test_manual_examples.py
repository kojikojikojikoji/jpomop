"""Records rebuilt from the worked examples in the FY2026 manual.

Values were read from the manual page by page and typed in; the manual's
text is not copied. Each test cites the page.
"""

from datetime import date
from pathlib import Path

from helpers import write

from jpomop.parse import pivot_yoshiki1, read_yoshiki1

HEADER = ["123456789", "0011223344", "20260401", "0", "0"]


def rec(code: str, *payloads: str) -> str:
    p = list(payloads) + [""] * (9 - len(payloads))
    return "\t".join([*HEADER, code, "20140401", "0", *p])


# p21, "ファイルレイアウト例". Payload columns were matched by position on the page.
P21 = [
    rec("A000010", "19640521", "1", "1920914"),
    rec("A000020", "20260401", "1", "0", "0", "100", "0"),
    rec("A000030", "20260410", "1", "2", "0"),
    rec("A000031", "20260401", "20260410"),
    rec("A000040", "", "060", "0"),
    rec("A000050", "", "1", "0", "0"),
    rec("A000060", "", "4", "0"),
    rec("A000070", "99999999", "99999999"),
]


def test_p21_layout_example(tmp_path: Path) -> None:
    res = read_yoshiki1(write(tmp_path / "y1.txt", P21))
    assert res.violations == []
    assert res.table.num_rows == 8
    tables = pivot_yoshiki1(res.table)
    form = tables.forms.to_pylist()[0]
    assert form["birth_date"] == date(1964, 5, 21)
    assert form["sex"] == "1"
    assert form["admission_route"] == "1"
    assert form["admission_type"] == "100"
    assert form["discharge_date"] == date(2026, 4, 10)
    assert form["discharge_to"] == "1"
    assert (form["period_start"], form["period_end"]) == (date(2026, 4, 1), date(2026, 4, 10))


def test_p21_example_outcome_is_not_in_the_p52_code_list(tmp_path: Path) -> None:
    """The p21 example records discharge outcome 2, but p52 allows 1, 3-7 and 9 only.

    jpomop follows the code list, so the example produces exactly one violation.
    """
    tables = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", P21)).table)
    assert [(v.field, v.value, v.rule) for v in tables.violations] == [
        ("A000030.3:discharge_outcome", "2", "code_not_in_table")
    ]


# p234, "EF統合ファイルの作成例": one cataract operation (data category 50) with a
# laterality comment, the procedure and four drugs. Admission and discharge dates,
# facility and patient IDs are not in the example and are invented here.
def ef(
    detail: str,
    hosp: str,
    code: str,
    name: str,
    qty: str,
    unit: str,
    pts: str,
    yen_point: str,
    ffs: str,
    flags: str,
) -> str:
    return "\t".join(
        [
            "123456789",
            "0011223344",
            "20260626",
            "20260623",
            "50",
            "0001",
            detail,
            hosp,
            code,
            "",
            name,
            qty,
            unit,
            pts,
            yen_point,
            ffs,
            flags,
            "12100",
            "1960",
            "0",
            "1",
            "39011077",
            "1317",
            "20260624",
            "26",
            "230",
            "603808",
            "N07",
            "0",
            "0",
            "001",
        ]
    )


P234 = [
    ef("001", "788005", "810000000", "右", "0", "000", "0", "0", "0", "000000000000"),
    ef(
        "002",
        "502331",
        "150253010",
        "水晶体再建術（眼内レンズを挿入する場合）",
        "0",
        "000",
        "12100",
        "0",
        "12100",
        "000010000000",
    ),
    ef(
        "003",
        "431709",
        "620003739",
        "セファメジンα点滴用キット１ｇ（生理食塩液１００ｍＬ付）",
        "1",
        "051",
        "731",
        "1",
        "0",
        "000000000000",
    ),
    ef(
        "004",
        "356530",
        "661310031",
        "エコリシン眼軟膏",
        "0.5",
        "033",
        "17",
        "1",
        "0",
        "000000000000",
    ),
    ef(
        "005",
        "359169",
        "620006397",
        "オペガンハイ０．８５眼粘弾剤１％ ０．８５ｍＬ",
        "1",
        "047",
        "7714.1",
        "1",
        "0",
        "000000000000",
    ),
    ef(
        "006",
        "384267",
        "621512501",
        "ヒーロンＶ０．６眼粘弾剤２．３％ ０．６ｍＬ",
        "1",
        "047",
        "10408.6",
        "1",
        "0",
        "000000000000",
    ),
]


def test_p234_ef_example(tmp_path: Path) -> None:
    from jpomop.etl import build_cdm
    from jpomop.parse import read_ef

    res = read_ef(write(tmp_path / "ef.txt", P234))
    assert res.violations == []
    y1 = [
        "\t".join(
            [
                "123456789",
                "0011223344",
                "20260623",
                "0",
                "0",
                code,
                "20140401",
                "0",
                *p,
                *[""] * (9 - len(p)),
            ]
        )
        for code, p in [
            ("A000010", ["19500101", "2", "1000001"]),
            ("A000030", ["20260626", "1", "1", "0"]),
        ]
    ]
    forms = pivot_yoshiki1(read_yoshiki1(write(tmp_path / "y1.txt", y1)).table)
    cdm, report = build_cdm(forms.forms, res.table, forms.diagnoses)
    assert report.invariant_problems == []
    procs = cdm["procedure_occurrence"].to_pylist()
    assert [p["procedure_source_value"] for p in procs] == ["150253010"]
    assert procs[0]["procedure_date"] == date(2026, 6, 24)
    drugs = cdm["drug_exposure"].to_pylist()
    assert [d["drug_source_value"] for d in drugs] == [
        "620003739",
        "661310031",
        "620006397",
        "621512501",
    ]
    assert [d["quantity"] for d in drugs] == [1.0, 0.5, 1.0, 1.0]
