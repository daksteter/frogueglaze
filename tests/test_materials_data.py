"""The material library: every analysis has a source, and the numbers hold up."""

import json
from pathlib import Path

import pytest

from core.chemistry.formulas import theoretical_analysis
from core.chemistry.materials import LIBRARY, OXIDE_MOLECULAR_WEIGHTS

DATA_FILE = (
    Path(__file__).resolve().parents[1] / "ceramics-foundation/data/materials.json"
)
DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))["materials"]
SECOND_HAND_SITES = ("digitalfire", "glazy")


def _keys(*types):
    return [key for key, m in DATA.items() if m["source"]["type"] in types]


def test_engine_loads_the_whole_library():
    assert set(LIBRARY) == set(DATA)


def test_every_material_records_its_source():
    for key, material in DATA.items():
        source = material["source"]
        assert source["type"] in {"supplier", "theoretical", "unverified"}, key
        if source["type"] == "supplier":
            assert source.get("supplier"), key
            assert source.get("url", "").startswith("http"), key
            assert not any(site in source["url"] for site in SECOND_HAND_SITES), key


@pytest.mark.parametrize("key", _keys("theoretical"))
def test_theoretical_analyses_match_their_formulas(key):
    material = DATA[key]
    oxides, loi = theoretical_analysis(
        material["source"]["formula"], material["source"]["yields"]
    )
    assert material["oxides"] == oxides
    assert material["loi"] == loi


@pytest.mark.parametrize("key", _keys("theoretical", "supplier"))
def test_sourced_analyses_add_up(key):
    total = sum(DATA[key]["oxides"].values()) + DATA[key]["loi"]
    assert 97.0 <= total <= 101.5, f"{key}: oxides + LOI = {total:.1f}%"


def test_engine_knows_every_oxide():
    """An oxide without a molecular weight would be silently left out of UMF."""
    for key, material in DATA.items():
        for oxide in material["oxides"]:
            assert oxide in OXIDE_MOLECULAR_WEIGHTS, f"{key}: {oxide}"


def test_names_and_aliases_point_at_one_material():
    owner = {}
    for key, material in DATA.items():
        for name in [key, *[a.lower() for a in material["aliases"]]]:
            assert (
                owner.setdefault(name, key) == key
            ), f"{name!r}: {owner[name]} and {key}"
