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
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write every violation to this CSV file.",
)
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
        violations += check_cross_file(
            pa.concat_tables(efs),
            pa.concat_tables(forms),
            ef_file=ef_paths[0].name,
            y1_file=y1_paths[0].name,
        )

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


@main.command()
@click.option("--n", "n_patients", default=100, show_default=True, help="Number of patients.")
@click.option("--seed", default=20261012, show_default=True)
@click.option("--out", type=click.Path(file_okay=False, path_type=Path), required=True)
def synth(n_patients: int, seed: int, out: Path) -> None:
    """Write a synthetic Form 1 and EF file (June 2026). Everything is invented."""
    from jpomop.synth import generate

    m = generate(out, n_patients, seed=seed)
    click.echo(f"{m.n_patients} patients, {m.n_stays} stays")
    click.echo(f"{m.yoshiki1}\n{m.ef}")


@main.command()
@click.option("--yoshiki1", "y1_paths", type=_existing, multiple=True, required=True)
@click.option("--ef", "ef_paths", type=_existing, multiple=True, required=True)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    required=True,
    help="DuckDB file, or a directory with --format parquet.",
)
@click.option(
    "--format", "fmt", type=click.Choice(["duckdb", "parquet"]), default="duckdb", show_default=True
)
@click.option(
    "--vocab",
    "vocab_path",
    type=_existing,
    help="vocab.duckdb from `jpomop vocab build`. Without it, concept IDs are 0.",
)
def convert(
    y1_paths: tuple[Path, ...],
    ef_paths: tuple[Path, ...],
    out: Path,
    fmt: str,
    vocab_path: Path | None,
) -> None:
    """Convert DPC files to OMOP CDM v5.4 tables."""
    from jpomop.etl import run_etl

    report = run_etl(
        list(y1_paths),
        list(ef_paths),
        out,
        fmt,  # type: ignore[arg-type]
        vocab=vocab_path,
    )
    for name, n in report.rows.items():
        click.echo(f"{name}\t{n}")
    for kind, n in sorted(report.skipped_forms.items()):
        click.echo(f"skipped forms {kind}\t{n}")
    for table, reasons in report.skipped_rows.items():
        for reason, n in sorted(reasons.items()):
            click.echo(f"left out of {table}: {reason}\t{n}")
    if report.n_violations:
        click.echo(f"input violations\t{report.n_violations} (run jpomop validate for details)")
    for p in report.invariant_problems:
        click.echo(f"INVARIANT\t{p}", err=True)
    if report.invariant_problems:
        raise SystemExit(2)


@main.group()
def vocab() -> None:
    """Build the local vocabulary from files you download yourself."""


@vocab.command("build")
@click.option(
    "--athena",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Folder with CONCEPT.csv and CONCEPT_RELATIONSHIP.csv.",
)
@click.option(
    "--drug-master",
    type=_existing,
    multiple=True,
    required=True,
    help="医薬品マスター y_*.csv (repeat for several files).",
)
@click.option("--kimura", type=_existing, help="Kimura et al. 2025 mapping (.xlsx or .csv).")
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), required=True)
def vocab_build(
    athena: Path, drug_master: tuple[Path, ...], kimura: Path | None, out: Path
) -> None:
    from jpomop.vocab import build_vocab

    r = build_vocab(athena, list(drug_master), kimura, out)
    click.echo(f"ICD-10 codes\t{r.icd10_codes} ({r.icd10_mapped} map to a standard concept)")
    click.echo(f"drug receipt codes\t{r.receipt_drugs} ({r.receipt_drugs_mapped} mapped)")


@main.command()
@click.option("--cdm", type=_existing, required=True, help="DuckDB file from jpomop convert.")
@click.option("--top", default=10, show_default=True, help="Unmapped source codes to list.")
def report(cdm: Path, top: int) -> None:
    """Show how much of each domain maps to standard concepts."""
    from jpomop.report import coverage

    for c in coverage(cdm, top):
        click.echo(
            f"{c.table}\trows {c.mapped_rows}/{c.rows} ({c.row_rate:.1%})\t"
            f"codes {c.mapped_codes}/{c.codes} ({c.code_rate:.1%})"
        )
        for code, n in c.top_unmapped:
            click.echo(f"  unmapped {code}\t{n}")
