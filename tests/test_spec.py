import pytest

from jpomop.spec import FIELD_TYPES, load_code_table, load_codes, load_spec


@pytest.mark.parametrize("spec_id, n", [("dpc_ef", 31), ("dpc_yoshiki1", 17)])
def test_fields_are_numbered_from_one(spec_id: str, n: int) -> None:
    spec = load_spec(spec_id)  # type: ignore[arg-type]
    assert spec.n_fields == n
    assert [f.col for f in spec.fields] == list(range(1, n + 1))


@pytest.mark.parametrize("spec_id", ["dpc_ef", "dpc_yoshiki1"])
def test_every_field_has_a_page_and_known_type(spec_id: str) -> None:
    spec = load_spec(spec_id)  # type: ignore[arg-type]
    for f in spec.fields:
        assert f.page > 0, f.name
        assert f.type in FIELD_TYPES, f.name
        assert f.required in {"always", "never", "ffs_only"}, f.name


@pytest.mark.parametrize("spec_id", ["dpc_ef", "dpc_yoshiki1"])
def test_field_names_are_unique(spec_id: str) -> None:
    names = load_spec(spec_id).field_names()  # type: ignore[arg-type]
    assert len(names) == len(set(names))


def test_code_tables_referenced_by_fields_exist() -> None:
    for spec_id in ("dpc_ef", "dpc_yoshiki1"):
        spec = load_spec(spec_id)  # type: ignore[arg-type]
        refs = [f.codes for f in spec.fields if f.codes]
        for payload in spec.payloads.values():
            refs += [i["codes"] for i in payload.get("items", {}).values() if "codes" in i]
        for ref in refs:
            assert load_codes(ref)


def test_yoshiki1_diagnosis_payloads_use_a_known_item_set() -> None:
    spec = load_spec("dpc_yoshiki1")
    for code, payload in spec.payloads.items():
        if "item_set" in payload:
            assert payload["item_set"] in spec.item_sets, code


def test_ef_inpatient_data_kubun_excludes_outpatient_codes() -> None:
    codes = load_codes("ef_data_kubun")
    assert "12" not in codes and "25" not in codes
    assert len(codes) == 22


def test_death_outcomes() -> None:
    assert load_code_table("y1_discharge_outcome")["death"] == ["6", "7"]


def test_ef_and_yoshiki1_cite_the_same_document() -> None:
    assert load_spec("dpc_ef").source == load_spec("dpc_yoshiki1").source
