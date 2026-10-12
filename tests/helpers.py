"""Build small DPC files for tests. All values are invented."""

from __future__ import annotations

from pathlib import Path

FACILITY = "131234567"
PATIENT = "0000000001"

EF_DEFAULTS = {
    1: FACILITY, 2: PATIENT, 3: "20260615", 4: "20260610", 5: "21", 6: "0001", 7: "001",
    8: "H00000000001", 9: "620000001", 10: "", 11: "架空錠１０ｍｇ", 12: "0000002.000",
    13: "009", 14: "12.5", 15: "1", 16: "25", 17: "000000000000", 18: "0", 19: "25",
    20: "0", 21: "1", 22: "06130012", 23: "1110", 24: "20260611", 25: "01", 26: "010",
    27: "D000000001", 28: "W1", 29: "1", 30: "0", 31: "001",
}


def ef_line(**overrides: str) -> str:
    cols = dict(EF_DEFAULTS)
    for k, v in overrides.items():
        cols[int(k.lstrip("c"))] = v
    return "\t".join(cols[i] for i in range(1, 32))


def y1_line(code: str, payloads: dict[int, str], *, seq: str = "0", summary: str = "0",
            admission: str = "20260610", patient: str = PATIENT, version: str = "20140401") -> str:
    p = [payloads.get(i, "") for i in range(1, 10)]
    return "\t".join([FACILITY, patient, admission, "0", summary, code, version, seq, *p])


def basic_form(patient: str = PATIENT, *, outcome: str = "1", discharge_to: str = "1",
               dx_modifiers: tuple[str, ...] = ()) -> list[str]:
    mods = {5 + i: m for i, m in enumerate(dx_modifiers)}
    return [
        y1_line("A000010", {1: "19500102", 2: "2", 3: "1000001"}, patient=patient),
        y1_line("A000020", {1: "20260610", 2: "1", 5: "100", 6: "0"}, patient=patient),
        y1_line("A000030", {1: "20260615", 2: discharge_to, 3: outcome, 4: "0"}, patient=patient),
        y1_line("A006010", {2: "J189", 4: "4860021", 9: "肺炎", **mods}, patient=patient),
        y1_line("A006040", {2: "E119", 4: "2500013", 9: "２型糖尿病"}, seq="1", patient=patient),
        y1_line("A006040", {2: "I10", 4: "4019002", 9: "高血圧症"}, seq="2", patient=patient),
    ]


def write(path: Path, lines: list[str]) -> Path:
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp932"))
    return path


def fake_athena(d: Path) -> Path:
    """A tiny Athena export. Concept IDs are invented (900000000+)."""
    d.mkdir(parents=True, exist_ok=True)
    head = ("concept_id\tconcept_name\tdomain_id\tvocabulary_id\tconcept_class_id\t"
            "standard_concept\tconcept_code\tvalid_start_date\tvalid_end_date\tinvalid_reason")
    rows = [
        "900000001\tPneumonia, unspecified\tCondition\tICD10\tICD10 code\t\tJ18.9\t19700101\t20991231\t",
        "900000002\tType 2 diabetes\tCondition\tICD10\tICD10 code\t\tE11.9\t19700101\t20991231\t",
        "900000003\tFracture of neck of femur\tCondition\tICD10\tICD10 code\t\tS72.0\t19700101\t20991231\t",
        "900000101\tPneumonia\tCondition\tSNOMED\tClinical Finding\tS\t233604007\t19700101\t20991231\t",
        "900000102\tType 2 diabetes mellitus\tCondition\tSNOMED\tClinical Finding\tS\t44054006\t19700101\t20991231\t",
        "900000103\tFracture of neck of femur\tCondition\tSNOMED\tClinical Finding\tS\t5913000\t19700101\t20991231\t",
    ]
    (d / "CONCEPT.csv").write_text("\n".join([head, *rows]) + "\n", encoding="utf-8")
    rel_head = ("concept_id_1\tconcept_id_2\trelationship_id\tvalid_start_date\t"
                "valid_end_date\tinvalid_reason")
    rels = [
        "900000001\t900000101\tMaps to\t19700101\t20991231\t",
        "900000002\t900000102\tMaps to\t19700101\t20991231\t",
        "900000003\t900000103\tMaps to\t19700101\t20991231\t",
    ]
    (d / "CONCEPT_RELATIONSHIP.csv").write_text("\n".join([rel_head, *rels]) + "\n",
                                                encoding="utf-8")
    return d


def fake_drug_master(path: Path, pairs: dict[str, str]) -> Path:
    """Rows shaped like the drug master: 42 quoted fields, receipt code in 3, YJ code in 32."""
    lines = []
    for receipt, yj in pairs.items():
        cols = ["0", "Y", receipt] + [""] * 39
        cols[31] = yj
        lines.append(",".join(f'"{c}"' for c in cols))
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("cp932"))
    return path
