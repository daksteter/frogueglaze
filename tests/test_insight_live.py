"""Insight-Live recipe export: reading, material matching, and importing as glazes.

The sample export is made up but laid out like a real one, including the
extra quotes and Windows line break Insight-Live puts inside comments.
"""

import json
from unittest.mock import patch

import pytest

from core.insight_live import (
    ADDITIONS_FOUND,
    ADDITIONS_GUESSED,
    ADDITIONS_NONE,
    ADDITIONS_UNCLEAR,
    KIND_ADDITION,
    KIND_BASE,
    ExportMaterial,
    ImportFormatError,
    clean_text,
    decode,
    match_materials,
    material_kind,
    parse_export,
    recipe_string,
    split_additions,
)

EXPORT = (
    'Code,Name,Description,Date,Batch,Location,"Mystery Kaolin","Ferro Frit 3134",'
    'Silica,Whiting,"Custer Feldspar",Zircopax,"Red Iron Oxide","Batch total (g)",'
    "Comments\r\n"
    'T101,"Test Clear","Base clear",2026-01-05,0.00,,20,25,30,10,15,,,100,'
    '"""A comment.\r\n"""\r\n'
    'T102,"Test White","10/27/26 - keeper",2026-02-01,0.00,"Shelf 3",20,25,30,10,15,'
    "10,,110,\r\n"
    'T103,"Test Speckle",,2026-03-01,0.00,,,,40,30,,,2,72,\r\n'
)


def _materials(*amounts):
    return [ExportMaterial(f"M{i}", amount) for i, amount in enumerate(amounts)]


class TestReadingTheExport:
    def test_reads_recipes_materials_and_metadata(self):
        export = parse_export(EXPORT)
        assert [r.code for r in export.recipes] == ["T101", "T102", "T103"]
        assert export.material_names[0] == "Mystery Kaolin"
        assert export.ignored_columns == []

        clear, white, speckle = export.recipes
        assert clear.row == 2 and white.row == 4  # the comment spans two lines
        assert clear.comments == "A comment."
        assert clear.description == "Base clear" and clear.date == "2026-01-05"
        assert clear.additions == ADDITIONS_NONE and clear.warnings == []
        assert white.location == "Shelf 3"
        assert [m.name for m in white.materials if m.addition] == ["Zircopax"]
        assert (white.base_total, white.additions_total) == (100, 10)
        assert speckle.additions == ADDITIONS_NONE
        assert "add up to 72" in speckle.warnings[0]

    def test_text_columns_are_ignored_not_read_as_materials(self):
        text = "Code,Name,Glaze Type,Silica,Whiting\nA1,One,matte,60,40\n"
        export = parse_export(text)
        assert export.material_names == ["Silica", "Whiting"]
        assert export.ignored_columns == ["Glaze Type"]

    def test_batch_total_mismatch_is_reported(self):
        text = 'Code,Name,Silica,Whiting,"Batch total (g)"\nA1,One,60,40,120\n'
        warning = parse_export(text).recipes[0].warnings[0]
        assert "batch total is 120" in warning

    @pytest.mark.parametrize(
        "text, message",
        [
            ("", "empty"),
            ("Code,Silica\nA1,50\n", "no Name column"),
            ("Code,Name,Notes\nA1,One,hello\n", "no material columns"),
        ],
    )
    def test_unreadable_files_are_refused(self, text, message):
        with pytest.raises(ImportFormatError, match=message):
            parse_export(text)

    def test_text_cleanup_and_decoding(self):
        assert clean_text('"Duplicated from T100.\r\n"') == "Duplicated from T100."
        assert clean_text('Said "hi"') == 'Said "hi"'
        assert decode("Café".encode("cp1252")) == "Café"
        assert decode("﻿Code".encode("utf-8")) == "Code"


class TestAdditions:
    def test_leading_materials_adding_to_100_are_the_base(self):
        materials = _materials(26, 28, 22, 12, 12, 6, 8, 1.5, 0.2)
        assert split_additions(materials) == ADDITIONS_FOUND
        assert [m.addition for m in materials] == [False] * 5 + [True] * 4

    def test_the_one_combination_adding_to_100_is_the_base(self):
        # Column order follows the whole export, so an addition can come first
        materials = _materials(2, 5, 95)
        assert split_additions(materials) == ADDITIONS_FOUND
        assert [m.addition for m in materials] == [True, False, False]

    @pytest.mark.parametrize("amounts", [(70, 40, 30, 30), (70, 45)])
    def test_ambiguous_or_impossible_splits_are_unclear(self, amounts):
        materials = _materials(*amounts)
        assert split_additions(materials) == ADDITIONS_UNCLEAR
        assert not any(m.addition for m in materials)

    def test_unclear_recipes_get_a_warning(self):
        recipe = parse_export("Code,Name,A,B\nX1,One,70,45\n").recipes[0]
        assert recipe.additions == ADDITIONS_UNCLEAR
        assert "mark the additions in the recipe editor" in recipe.warnings[0]

    def test_material_types_pick_between_splits(self):
        # Columns follow the oldest recipe, so the newer recipe's Tin Oxide
        # addition comes before its Wollastonite. Both 5-material sets reach 100.
        text = (
            'Code,Name,"Mystery Kaolin","Ferro Frit 3134",Silica,Whiting,'
            '"Custer Feldspar","Tin Oxide",Wollastonite,"Blue Stain"\n'
            "T202,Newer,15,25,30,,20,10,10,3\n"
            "T201,Older,25,25,30,20,,2,,\n"
        )
        newer, older = parse_export(text).recipes
        assert newer.additions == ADDITIONS_GUESSED
        assert [m.name for m in newer.materials if m.addition] == [
            "Tin Oxide",
            "Blue Stain",
        ]
        assert "check them" in newer.warnings[0]
        assert older.additions == ADDITIONS_FOUND and older.warnings == []

    def test_file_order_is_decisive_only_for_one_recipe(self):
        # {50, 50} leads; {50, 30, 20} also adds up to 100 and fits as well
        materials = _materials(50, 50, 30, 20)
        assert split_additions(materials, in_order=True) == ADDITIONS_FOUND
        assert [m.addition for m in materials] == [False, False, True, True]
        assert split_additions(_materials(50, 50, 30, 20), in_order=False) == (
            ADDITIONS_GUESSED
        )

    def test_too_many_combinations_is_unclear(self):
        assert split_additions(_materials(*[2] * 60)) == ADDITIONS_UNCLEAR

    @pytest.mark.parametrize(
        "name, kind",
        [
            ("Zircopax", KIND_ADDITION),
            ("Red Iron Oxide", KIND_ADDITION),
            ("Whiting", KIND_BASE),
            ("EPK", KIND_BASE),
            ("Bentonite", None),
            ("Alumina Hydrate", None),
            ("Mystery Kaolin", KIND_BASE),
            ("Blue Stain", KIND_ADDITION),
            ("Meadow 1234", None),
        ],
    )
    def test_material_kinds(self, name, kind):
        assert material_kind(name) == kind


class TestMatchingAndRecipes:
    def test_names_match_exactly_partially_or_not_at_all(self):
        matches = match_materials(["Zircopax", "Silica 325 mesh", "Mystery Kaolin"])
        assert matches["Zircopax"].key == "zirconium silicate"
        assert not matches["Zircopax"].partial
        assert matches["Silica 325 mesh"].key == "silica"
        assert matches["Silica 325 mesh"].partial
        assert matches["Mystery Kaolin"].key is None

    def test_recipe_string_puts_additions_last_with_a_plus(self):
        white = parse_export(EXPORT).recipes[1]
        text = recipe_string(white, {"Mystery Kaolin": "EPK"})
        assert text == (
            "EPK 20, Ferro Frit 3134 25, Silica 30, Whiting 10, Custer Feldspar 15, "
            "+Zircopax 10"
        )


@pytest.fixture
def client(test_db_path):
    # Own rate-limit bucket (the limiter is process-global, keyed by IP)
    env = {"DATABASE_PATH": test_db_path, "TRUSTED_PROXY": "127.0.0.1"}
    with patch.dict("os.environ", env):
        from server import create_app

        app = create_app({"mode": "personal", "database": {"path": test_db_path}})
        test_client = app.test_client()
        test_client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.42.0.91"
        yield test_client


def _post(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


def _preview(client, text=EXPORT):
    return _post(client, "/api/import/insight-live/preview", {"csv": text})


def _import(client, rows, **extra):
    return _post(
        client, "/api/import/insight-live", {"csv": EXPORT, "rows": rows, **extra}
    )


class TestImportRoutes:
    def test_preview_reports_matches_and_writes_nothing(self, client):
        before = len(client.get("/api/glazes").get_json())
        resp = _preview(client)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["unmatched"] == ["Mystery Kaolin"]
        materials = {m["name"]: m for m in data["materials"]}
        assert materials["Zircopax"]["material"] == "Zirconium Silicate"
        assert materials["Silica"]["source_type"] == "theoretical"
        assert materials["Mystery Kaolin"]["recipes"] == 2
        assert [r["existing"] for r in data["recipes"]] == [None, None, None]
        assert len(client.get("/api/glazes").get_json()) == before

    def test_import_creates_glazes_with_versions_and_origin(self, client, test_db_path):
        resp = _import(client, [4], cone="6")
        assert resp.status_code == 201
        [made] = resp.get_json()["imported"]
        assert made["name"] == "Test White" and made["code"] == "T102"
        assert made["missing"] == ["Mystery Kaolin"]

        glaze = client.get(f"/api/glazes/{made['id']}").get_json()
        assert glaze["recipe"].endswith("+Zircopax 10")
        assert glaze["recipe"].startswith("Mystery Kaolin 20")
        assert glaze["cone"] == "6"
        assert glaze["notes"].startswith("Imported from Insight-Live recipe T102")
        assert "Location: Shelf 3" in glaze["notes"]

        versions = client.get(f"/api/glazes/{made['id']}/versions").get_json()
        assert [v["note"] for v in versions] == ["Imported from Insight-Live (T102)"]

        from core.db import connect_db

        conn = connect_db(test_db_path)
        row = conn.execute("SELECT * FROM glaze_imports").fetchone()
        conn.close()
        assert row["source_code"] == "T102" and row["source_date"] == "2026-02-01"
        assert json.loads(row["original"])[-1] == {
            "name": "Zircopax",
            "amount": 10.0,
            "addition": True,
        }

        again = _preview(client).get_json()["recipes"]
        assert again[1]["existing"]["reason"] == "code"
        assert again[1]["existing"]["id"] == made["id"]

    def test_mapping_rewrites_unmatched_names(self, client):
        resp = _import(client, [2, 4], mapping={"Mystery Kaolin": "epk"})
        assert resp.status_code == 201
        imported = resp.get_json()["imported"]
        assert all(item["missing"] == [] for item in imported)
        assert imported[0]["recipe"].startswith("EPK 20, Ferro Frit 3134 25")
        umf = _post(
            client, "/api/chemistry/umf", {"recipe": imported[0]["recipe"], "cone": "6"}
        ).get_json()
        assert umf["success"] is True

    def test_kept_names_calculate_once_a_studio_material_exists(self, client):
        made = _import(client, [2]).get_json()["imported"][0]
        studio = {
            "name": "Mystery Kaolin",
            "category": "clay",
            "oxides": {"SiO2": 46.0, "Al2O3": 38.0, "Fe2O3": 0.5, "K2O": 0.5},
            "loi": 14.0,
            "source": "Supplier sheet",
        }
        assert _post(client, "/api/materials", studio).status_code == 201
        umf = _post(
            client, "/api/chemistry/umf", {"recipe": made["recipe"], "cone": "6"}
        ).get_json()
        assert umf["success"] is True and umf["missing_materials"] == []

    def test_reimporting_gives_a_new_id(self, client):
        first = _import(client, [2]).get_json()["imported"][0]["id"]
        second = _import(client, [2]).get_json()["imported"][0]["id"]
        assert second == f"{first}-2"

    @pytest.mark.parametrize(
        "body, message",
        [
            ({"rows": []}, "Choose at least one recipe"),
            ({"rows": "2"}, "rows must be a list"),
            (
                {"rows": [2], "mapping": {"Mystery Kaolin": "no such"}},
                "unknown material",
            ),
            ({"rows": [2], "cone": "hot"}, "Not a cone"),
        ],
    )
    def test_bad_import_requests_are_refused(self, client, body, message):
        resp = _post(client, "/api/import/insight-live", {"csv": EXPORT, **body})
        assert resp.status_code == 400
        assert message in resp.get_json()["message"]

    def test_bad_files_are_refused(self, client):
        resp = _preview(client, "Code,Silica\nA1,50\n")
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "invalid_export"
        assert _post(client, "/api/import/insight-live/preview", {}).status_code == 400
