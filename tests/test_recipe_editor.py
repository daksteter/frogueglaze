"""Recipe editor backend: live UMF, materials list, additions, saved versions."""

import json
from unittest.mock import patch

import pytest

from core.chemistry.parser import parse_recipe_string
from core.chemistry.umf import calculate_umf

RECIPE = "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12"


@pytest.fixture
def client(test_db_path):
    # The rate limiter is process-global and bucketed by client IP; use our own
    # bucket (trusted-proxy X-Forwarded-For) so other test files aren't starved.
    env = {"DATABASE_PATH": test_db_path, "TRUSTED_PROXY": "127.0.0.1"}
    with patch.dict("os.environ", env):
        from server import create_app

        app = create_app({"mode": "personal", "database": {"path": test_db_path}})
        app.config["TESTING"] = True
        test_client = app.test_client()
        test_client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.42.0.77"
        yield test_client


def _post(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


def _create_glaze(client, recipe=None):
    resp = _post(client, "/api/glazes", {"name": "Editor Test", "recipe": recipe})
    assert resp.status_code == 201
    return resp.get_json()["id"]


class TestAdditionsMarker:
    def test_plus_prefix_parses_as_an_addition(self):
        result = parse_recipe_string(RECIPE + ", +Red Iron Oxide 2")
        assert result.success
        assert "Could not parse" not in " ".join(result.errors)
        assert len(result.materials) == 5

    def test_marker_does_not_change_the_chemistry(self):
        plain = calculate_umf(RECIPE + ", Red Iron Oxide 2", cone=6)
        marked = calculate_umf(RECIPE + ", +Red Iron Oxide 2", cone=6)
        assert plain.success and marked.success
        assert marked.umf_formula == plain.umf_formula


class TestLiveUmf:
    def test_returns_ratios_cte_and_limits(self, client):
        resp = _post(client, "/api/chemistry/umf", {"recipe": RECIPE, "cone": "6"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["ratios"]["sio2_al2o3"] > 0
        assert body["thermal_expansion"] is not None
        assert body["cone"] == "6"
        assert isinstance(body["limit_warnings"], list)

    def test_unknown_material_returns_partial_result(self, client):
        resp = _post(
            client, "/api/chemistry/umf", {"recipe": RECIPE + ", Mystery Frit 5"}
        )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["success"] is False
        assert body["missing_materials"] == ["Mystery Frit"]
        assert body["umf_formula"]  # partial UMF still shown

    def test_empty_recipe_is_rejected(self, client):
        resp = _post(client, "/api/chemistry/umf", {"recipe": "  "})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "missing_recipe"


def test_materials_endpoint_lists_materials_and_cones(client):
    body = client.get("/api/chemistry/materials").get_json()
    names = [m["name"] for m in body["materials"]]
    assert "Custer Feldspar" in names
    assert names == sorted(names, key=str.lower)
    assert {"6", "10", "04"} <= set(body["cones"])


class TestRecipeVersions:
    def test_first_save_keeps_the_original_recipe(self, client):
        glaze_id = _create_glaze(client, recipe=RECIPE)
        resp = _post(
            client,
            f"/api/glazes/{glaze_id}/versions",
            {"recipe": RECIPE + ", +Red Iron Oxide 2", "note": "add iron", "cone": "6"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["note"] == "add iron"

        versions = client.get(f"/api/glazes/{glaze_id}/versions").get_json()
        assert [v["recipe"] for v in versions] == [
            RECIPE + ", +Red Iron Oxide 2",
            RECIPE,
        ]
        assert versions[1]["note"] == "Recipe before first edit"

        glaze = client.get(f"/api/glazes/{glaze_id}").get_json()
        assert glaze["recipe"] == RECIPE + ", +Red Iron Oxide 2"
        assert glaze["cone"] == "6"

    def test_later_saves_append_one_version_each(self, client):
        glaze_id = _create_glaze(client)
        for amount in (1, 2):
            recipe = f"{RECIPE}, +Red Iron Oxide {amount}"
            _post(client, f"/api/glazes/{glaze_id}/versions", {"recipe": recipe})
        versions = client.get(f"/api/glazes/{glaze_id}/versions").get_json()
        assert len(versions) == 2
        assert versions[0]["recipe"].endswith("Red Iron Oxide 2")

    def test_missing_recipe_and_unknown_glaze(self, client):
        glaze_id = _create_glaze(client)
        resp = _post(client, f"/api/glazes/{glaze_id}/versions", {"recipe": ""})
        assert resp.status_code == 400
        assert client.get("/api/glazes/no-such-glaze/versions").status_code == 404
        resp = _post(client, "/api/glazes/no-such-glaze/versions", {"recipe": RECIPE})
        assert resp.status_code == 404
