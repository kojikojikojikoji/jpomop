from click.testing import CliRunner

from jpomop import __version__
from jpomop.cli import main


def test_version() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_validate_clean_files(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from helpers import basic_form, ef_line, write

    y1 = write(tmp_path / "y1.txt", basic_form())
    ef = write(tmp_path / "ef.txt", [ef_line()])
    result = CliRunner().invoke(main, ["validate", "--yoshiki1", str(y1), "--ef", str(ef)])
    assert result.exit_code == 0, result.output
    assert "no violations" in result.output


def test_validate_reports_and_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from helpers import ef_line, write

    ef = write(tmp_path / "ef.txt", [ef_line(c24="20260631")])
    out = tmp_path / "v.csv"
    result = CliRunner().invoke(main, ["validate", "--ef", str(ef), "--out", str(out)])
    assert result.exit_code == 1
    assert "date_invalid\t1" in result.output
    assert out.read_text(encoding="utf-8").count("\n") == 2


def test_synth_then_convert(tmp_path) -> None:  # type: ignore[no-untyped-def]
    runner = CliRunner()
    r = runner.invoke(main, ["synth", "--n", "20", "--out", str(tmp_path / "s")])
    assert r.exit_code == 0, r.output
    r = runner.invoke(
        main,
        [
            "convert",
            "--yoshiki1",
            str(tmp_path / "s" / "yoshiki1.txt"),
            "--ef",
            str(tmp_path / "s" / "ef.txt"),
            "--out",
            str(tmp_path / "cdm"),
            "--format",
            "parquet",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "person\t20" in r.output
    assert (tmp_path / "cdm" / "visit_detail.parquet").exists()


def test_vocab_convert_report(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from helpers import basic_form, ef_line, fake_athena, fake_drug_master, write

    runner = CliRunner()
    master = fake_drug_master(tmp_path / "y.csv", {"620000001": "1111111F1011"})
    kimura = tmp_path / "k.csv"
    kimura.write_text("NHIDPLC,OSV_ID\n1111111F1011,900001001\n", encoding="utf-8")
    r = runner.invoke(
        main,
        [
            "vocab",
            "build",
            "--athena",
            str(fake_athena(tmp_path / "a")),
            "--drug-master",
            str(master),
            "--kimura",
            str(kimura),
            "--out",
            str(tmp_path / "v.duckdb"),
        ],
    )
    assert r.exit_code == 0, r.output
    y1 = write(tmp_path / "y1.txt", basic_form())
    ef = write(tmp_path / "ef.txt", [ef_line(), ef_line(c9="620000009")])
    r = runner.invoke(
        main,
        [
            "convert",
            "--yoshiki1",
            str(y1),
            "--ef",
            str(ef),
            "--vocab",
            str(tmp_path / "v.duckdb"),
            "--out",
            str(tmp_path / "cdm.duckdb"),
        ],
    )
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, ["report", "--cdm", str(tmp_path / "cdm.duckdb")])
    assert r.exit_code == 0, r.output
    # J189 and E119 are in the fake Athena; I10 is not
    assert "condition_occurrence\trows 2/3 (66.7%)" in r.output
    assert "drug_exposure\trows 1/2 (50.0%)" in r.output
    assert "unmapped 620000009\t1" in r.output
