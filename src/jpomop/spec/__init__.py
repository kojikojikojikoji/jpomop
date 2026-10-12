"""Load the DPC file specifications bundled with jpomop.

Each YAML file records field names, lengths, types and the page of the
specification document they come from. The text of the specification is
not copied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Literal

import yaml

SpecId = Literal["dpc_ef", "dpc_yoshiki1"]

FIELD_TYPES = {
    "digits",
    "string",
    "code",
    "integer",
    "decimal",
    "date8",
    "date8_or_zero",
    "date8_partial",
}


@dataclass(frozen=True)
class SourceRef:
    title: str
    fiscal_year: int
    edition: str
    url: str
    retrieved: str
    sha256: str


@dataclass(frozen=True)
class FieldSpec:
    col: int
    name: str
    name_ja: str
    type: str
    required: str  # "always", "never" or "ffs_only"
    page: int
    length: int | None = None
    zero_pad: bool = False
    codes: str | None = None
    drop: bool = False


@dataclass(frozen=True)
class Spec:
    spec_id: str
    source: SourceRef
    encoding: str
    delimiter: str
    n_fields: int
    fields: tuple[FieldSpec, ...]
    payloads: dict[str, Any] = field(default_factory=dict)
    item_sets: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]


def _read_yaml(*parts: str) -> Any:
    path = resources.files("jpomop.spec").joinpath(*parts)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_codes(name: str) -> dict[str, str]:
    """Return the code table `name` as {code: label}."""
    data = _read_yaml("codes", f"{name}.yaml")
    return {str(k): str(v) for k, v in data["values"].items()}


def load_code_table(name: str) -> dict[str, Any]:
    """Return the whole code table file, including extra keys such as `death`."""
    data: dict[str, Any] = _read_yaml("codes", f"{name}.yaml")
    return data


def load_spec(spec_id: SpecId) -> Spec:
    raw = _read_yaml(f"{spec_id}.yaml")
    known = {"spec_id", "source", "file", "fields", "payloads", "item_sets", "type_inferred"}
    return Spec(
        spec_id=raw["spec_id"],
        source=SourceRef(**{k: raw["source"][k] for k in SourceRef.__dataclass_fields__}),
        encoding=raw["file"]["encoding"],
        delimiter=raw["file"]["delimiter"],
        n_fields=raw["file"]["n_fields"],
        fields=tuple(FieldSpec(**f) for f in raw["fields"]),
        payloads=raw.get("payloads", {}),
        item_sets=raw.get("item_sets", {}),
        extra={k: v for k, v in raw.items() if k not in known},
    )
