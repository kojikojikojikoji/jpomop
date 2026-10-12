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
