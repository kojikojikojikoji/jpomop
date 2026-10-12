"""Generate a small, fixed synthetic DPC dataset.

Everything here is invented. ICD-10 codes are real classification codes,
but disease codes (傷病名コード), receipt codes (レセプト電算コード) and
hospital codes are made up and only have the right shape. They are not
taken from the code masters, which jpomop does not redistribute.

The same seed always produces byte-identical files.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

FACILITY = "999999999"  # not a real facility code

# (ICD-10, made-up 7-digit disease code, name)
DIAGNOSES = [
    ("J189", "9000001", "肺炎"),
    ("I639", "9000002", "脳梗塞"),
    ("I500", "9000003", "うっ血性心不全"),
    ("K802", "9000004", "胆のう結石症"),
    ("S7200", "9000005", "大腿骨頚部骨折"),
    ("C189", "9000006", "結腸癌"),
    ("N390", "9000007", "尿路感染症"),
]
COMORBID = [
    ("E119", "9000101", "２型糖尿病"),
    ("I10", "9000102", "本態性高血圧症"),
    ("E785", "9000103", "脂質異常症"),
    ("N189", "9000104", "慢性腎臓病"),
]
# (data_kubun, made-up receipt code, name, unit_code, quantity)
DAILY = ("90", "190999901", "架空入院基本料", "", "0000000.000")
DRUGS = [
    ("21", "620999901", "架空錠Ａ　５ｍｇ", "009", "0000001.000"),
    ("21", "620999902", "架空カプセルＢ", "009", "0000002.000"),
    ("33", "640999903", "架空注射液Ｃ　５００ｍＬ", "033", "0000001.000"),
]
TESTS = [
    ("60", "160999901", "架空検査（血液）", "", "0000000.000"),
    ("70", "170999901", "架空画像診断", "", "0000000.000"),
]
SURGERY = ("50", "150999901", "架空手術", "K9999")


@dataclass(frozen=True)
class SynthManifest:
    yoshiki1: Path
    ef: Path
    n_patients: int
    n_stays: int
    sha256: dict[str, str]


def _y1(pid: str, adm: str, code: str, seq: int, payloads: dict[int, str]) -> str:
    p = [payloads.get(i, "") for i in range(1, 10)]
    return "\t".join([FACILITY, pid, adm, "0", "0", code, "20140401", str(seq), *p])


def _ef(pid: str, adm: str, dis: str, kubun: str, order: int, detail: int, code: str,
        name: str, unit: str, qty: str, exec_date: str, ward: str, kaishaku: str = "") -> str:
    cols = [FACILITY, pid, dis, adm, kubun, f"{order:04d}", f"{detail:03d}",
            f"H{code}00", code, kaishaku, name, qty, unit or "000", "100", "0", "100",
            "000000000000", "100", "0", "0", "1", "06999999", "1110", exec_date, "01",
            "010", "", ward, "1", "0", "001"]
    return "\t".join(cols)


def generate(out_dir: Path, n_patients: int = 100, *, seed: int = 20261012) -> SynthManifest:
    """Write yoshiki1.txt and ef.txt for June 2026 into `out_dir`."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    y1: list[str] = []
    ef: list[str] = []
    n_stays = 0
    for i in range(1, n_patients + 1):
        pid = f"{i:010d}"
        birth = date(1930, 1, 1) + timedelta(days=rng.randrange(0, 365 * 90))
        sex = rng.choice(["1", "2"])
        day = 1
        for _ in range(rng.choice([1, 1, 1, 2])):
            if day > 20:
                break
            adm_d = date(2026, 6, rng.randint(day, 20))
            dis_d = adm_d + timedelta(days=rng.randint(1, 9))
            day = dis_d.day + 2
            adm, dis = adm_d.strftime("%Y%m%d"), dis_d.strftime("%Y%m%d")
            n_stays += 1
            died = rng.random() < 0.04
            route = rng.choice(["1", "1", "1", "4", "5"])
            y1.append(_y1(pid, adm, "A000010", 0,
                          {1: birth.strftime("%Y%m%d"), 2: sex, 3: "1000001"}))
            y1.append(_y1(pid, adm, "A000020", 0, {1: adm, 2: route, 5: "100", 6: "0"}))
            y1.append(_y1(pid, adm, "A000030", 0, {
                1: dis, 2: "8" if died else rng.choice(["1", "2", "4"]),
                3: rng.choice(["6", "7"]) if died else rng.choice(["1", "1", "4"]), 4: "0"}))
            icd, dcode, name = rng.choice(DIAGNOSES)
            suspected = rng.random() < 0.1
            main = {2: icd, 4: dcode, 9: name + ("の疑い" if suspected else "")}
            if suspected:
                main[5] = "8002"
            for code in ("A006010", "A006020", "A006030"):
                y1.append(_y1(pid, adm, code, 0, main))
            for seq, (c_icd, c_code, c_name) in enumerate(
                rng.sample(COMORBID, rng.randint(0, 2)), start=1
            ):
                y1.append(_y1(pid, adm, "A006040", seq, {2: c_icd, 4: c_code, 9: c_name}))
            operated = icd in ("K802", "S7200", "C189") and rng.random() < 0.7
            op_day = adm_d + timedelta(days=1)
            if operated:
                y1.append(_y1(pid, adm, "A007010", 1,
                              {1: op_day.strftime("%Y%m%d"), 2: SURGERY[3], 9: SURGERY[2]}))

            move_day = adm_d + timedelta(days=rng.randint(1, 5)) if rng.random() < 0.2 else None
            order = 1
            d = adm_d
            while d <= dis_d:
                ds = d.strftime("%Y%m%d")
                ward = "W2" if move_day and d >= move_day else "W1"
                k, c, n, u, q = DAILY
                ef.append(_ef(pid, adm, dis, k, order, 1, c, n, u, q, ds, ward))
                order += 1
                for k, c, n, u, q in rng.sample(DRUGS, rng.randint(0, 2)):
                    ef.append(_ef(pid, adm, dis, k, order, 1, c, n, u, q, ds, ward))
                    order += 1
                if d == adm_d or rng.random() < 0.3:
                    k, c, n, u, q = rng.choice(TESTS)
                    ef.append(_ef(pid, adm, dis, k, order, 1, c, n, u, q, ds, ward))
                    order += 1
                if operated and d == op_day:
                    k, c, n, kai = SURGERY
                    ef.append(_ef(pid, adm, dis, k, order, 1, c, n, "", "0000000.000", ds,
                                  ward, kai))
                    order += 1
                d += timedelta(days=1)

    paths = {"yoshiki1": out_dir / "yoshiki1.txt", "ef": out_dir / "ef.txt"}
    for key, lines in (("yoshiki1", y1), ("ef", ef)):
        paths[key].write_bytes(("\r\n".join(lines) + "\r\n").encode("cp932"))
    digests = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
    return SynthManifest(paths["yoshiki1"], paths["ef"], n_patients, n_stays, digests)
