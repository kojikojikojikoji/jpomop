from click.testing import CliRunner

from jpomop import __version__
from jpomop.cli import main


def test_version() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
