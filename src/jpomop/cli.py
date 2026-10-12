from __future__ import annotations

from collections import Counter
from pathlib import Path

import click
import pyarrow as pa
import pyarrow.csv as pacsv

from jpomop import __version__
from jpomop.parse import (
    Violation,
    check_cross_file,
    pivot_yoshiki1,
    read_ef,
    read_yoshiki1,
    violations_table,
)

_existing = click.Path(exists=True, dir_okay=False, path_type=Path)


@click.group()
@click.version_option(__version__)
def main() -> None:
    """jpomop: DPC to OMOP CDM v5.4."""


@main.command()
@click.option("--yoshiki1", "y1_paths", type=_existing, multiple=True, help="Form 1 file(s).")
@click.option("--ef", "ef_paths", type=_existing, multiple=True, help="EF integrated file(s).")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path),
              help="Write every violation to this CSV file.")
def validate(y1_paths: tuple[Path, ...], ef_paths: tuple[Path, ...], out: Path | None) -> None:
    """Check DPC files against the FY2026 specification.

    Exits with status 1 if any violation is found.
    """
    if not y1_paths and not ef_paths:
        raise click.UsageError("give at least one --yoshiki1 or --ef file")

    violations: list[Violation] = []
    forms = []
    for p in y1_paths:
        res = read_yoshiki1(p)
        tables = pivot_yoshiki1(res.table)
        violations += res.violations + tables.violations
        forms.append(tables.forms)
    efs = []
    for p in ef_paths:
        res = read_ef(p)
        violations += res.violations
        efs.append(res.table)
    if forms and efs:
        violations += check_cross_file(pa.concat_tables(efs), pa.concat_tables(forms),
                                       ef_file=ef_paths[0].name, y1_file=y1_paths[0].name)

    counts = Counter(v.rule for v in violations)
    if not violations:
        click.echo("no violations")
    for rule, n in sorted(counts.items()):
        click.echo(f"{rule}\t{n}")
    if out:
        pacsv.write_csv(violations_table(violations), out)
        click.echo(f"wrote {len(violations)} rows to {out}")
    if violations:
        raise SystemExit(1)
