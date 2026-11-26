"""Batch sheets: scaling, names kept as written, additions, lots, and the route."""

import json
from unittest.mock import patch

import pytest

from core.batch_sheet import BatchSheetError, batch_sheet, split_recipe

RECIPE = (
    "Mystery Kaolin 26, Fusion Frit F-12 28, Silica 22, Whiting 12, "
    "Nepheline Syenite 12, +Zircopax 8, +Rutile 1.5"
)


class TestSplitRecipe:
    def test_keeps_names_order_and_additions(self):
        lines = split_recipe(
            "Silica 25,  Mystery   Kaolin 20%; +Red Iron Oxide 2\nGlaze title"
        )
        assert [(x.name, x.amount, x.addition) for x in lines] == [
            ("Silica", 25.0, False),
            ("Mystery Kaolin", 20.0, False),
            ("Red Iron Oxide", 2.0, True),
        ]

    def test_unreadable_parts_are_refused(self):
        with pytest.raises(BatchSheetError, match="Couldn't read"):
            split_recipe("Silica 25, Whiting 1.2.3")


class TestBatchSheet:
    def test_base_is_scaled_and_additions_go_on_top(self):
        sheet = batch_sheet(RECIPE, 1000)
        rows = sheet["rows"]
        assert [r["grams"] for r in rows] == [260, 280, 220, 120, 120, 80, 15]
        assert [r["running"] for r in rows][-3:] == [1000, 1080, 1095]
        assert (sheet["base_grams"], sheet["additions_grams"]) == (1000, 95)
        assert sheet["total_grams"] == 1095
        assert rows[0] == {
            "name": "Mystery Kaolin",
            "amount": 26.0,
            "addition": False,
            "grams": 260.0,
            "running": 260.0,
            "known": False,
            "lot": None,
        }
        assert rows[5]["addition"] and rows[5]["known"]

    def test_whole_batch_basis_includes_additions(self):
        sheet = batch_sheet("Silica 50, Whiting 50, +Red Iron Oxide 5", 2100, "total")
        assert [r["grams"] for r in sheet["rows"]] == [1000, 1000, 100]
        assert sheet["total_grams"] == 2100

    def test_base_not_written_to_100_still_scales_to_the_size(self):
        sheet = batch_sheet("Silica 30, Whiting 20, +Zircopax 5", 500)
        assert [r["grams"] for r in sheet["rows"]] == [300, 200, 50]
        assert sheet["base_percent"] == 50

    def test_running_total_adds_the_rounded_weights(self):
        sheet = batch_sheet("Silica 33.33, Whiting 33.33, EPK 33.34", 100)
        assert [r["grams"] for r in sheet["rows"]] == [33.3, 33.3, 33.3]
        assert sheet["total_grams"] == 99.9 == sheet["rows"][-1]["running"]

    @pytest.mark.parametrize(
        "recipe, size, basis, message",
        [
            ("+Zircopax 8", 1000, "base", "no base materials"),
            ("Silica 50", 0, "base", "more than 0"),
            ("Silica 50", 2_000_000, "base", "at most 1000 kg"),
            ("Silica 50", "lots", "base", "more than 0"),
            ("Silica 50", 100, "bucket", "Unknown basis"),
        ],
    )
    def test_bad_requests(self, recipe, size, basis, message):
        with pytest.raises(BatchSheetError, match=message):
            batch_sheet(recipe, size, basis)


@pytest.fixture
def client(test_db_path):
    # Own rate-limit bucket (the limiter is process-global, keyed by IP)
    env = {"DATABASE_PATH": test_db_path, "TRUSTED_PROXY": "127.0.0.1"}
    with patch.dict("os.environ", env):
        from server import create_app

        app = create_app({"mode": "personal", "database": {"path": test_db_path}})
        test_client = app.test_client()
        test_client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.42.0.104"
        yield test_client


def _post(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


class TestBatchSheetRoute:
    def test_sheet_shows_the_lot_in_use(self, client):
        lot = {
            "lot": "W-2291",
            "oxides": {"CaO": 55.5, "MgO": 0.4},
            "loi": 44.1,
            "source": "Supplier certificate",
        }
        assert _post(client, "/api/materials/whiting/lots", lot).status_code == 201
        resp = _post(client, "/api/batch-sheet", {"recipe": RECIPE, "size": 1000})
        assert resp.status_code == 200
        rows = {r["name"]: r for r in resp.get_json()["rows"]}
        assert rows["Whiting"]["lot"] == "W-2291"
        assert rows["Silica"]["lot"] is None

    @pytest.mark.parametrize(
        "body, code",
        [
            ({"size": 1000}, "missing_recipe"),
            ({"recipe": RECIPE, "size": True}, "invalid_batch"),
            ({"recipe": RECIPE, "size": 1000, "basis": "bucket"}, "invalid_batch"),
        ],
    )
    def test_bad_requests_are_refused(self, client, body, code):
        resp = _post(client, "/api/batch-sheet", body)
        assert resp.status_code == 400
        assert resp.get_json()["code"] == code
