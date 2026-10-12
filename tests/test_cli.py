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
