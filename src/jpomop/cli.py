import click

from jpomop import __version__


@click.group()
@click.version_option(__version__)
def main() -> None:
    """jpomop: DPC to OMOP CDM v5.4."""
