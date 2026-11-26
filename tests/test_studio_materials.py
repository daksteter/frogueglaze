"""Studio materials and lot analyses: stored, validated, and used in calculations."""

import json
from unittest.mock import patch

import pytest

RECIPE = "Custer Feldspar 45, Silica 25, Whiting 18, EPK 12"
LOCAL_CLAY = {
    "name": "Creek Clay",
    "aliases": "creek, local red",
    "category": "clay",
    "oxides": {"SiO2": 58.0, "Al2O3": 20.0, "Fe2O3": 6.0, "K2O": 2.5, "CaO": 1.0},
    "loi": 11.5,
    "source": "Lab test, 2026",
}


@pytest.fixture
def client(test_db_path):
    # Own rate-limit bucket (the limiter is process-global, keyed by IP)
    env = {"DATABASE_PATH": test_db_path, "TRUSTED_PROXY": "127.0.0.1"}
    with patch.dict("os.environ", env):
        from server import create_app

        app = create_app({"mode": "personal", "database": {"path": test_db_path}})
        test_client = app.test_client()
        test_client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.42.0.78"
        yield test_client


def _send(client, method, path, body=None):
    return client.open(
        path,
        method=method,
        data=json.dumps(body or {}),
        content_type="application/json",
    )


def _umf(client, recipe):
    return _send(
        client, "POST", "/api/chemistry/umf", {"recipe": recipe, "cone": "6"}
    ).get_json()


class TestStudioMaterials:
    def test_added_material_is_listed_and_calculates(self, client):
        resp = _send(client, "POST", "/api/materials", LOCAL_CLAY)
        assert resp.status_code == 201
        assert resp.get_json()["aliases"] == ["creek", "local red"]

        listed = {m["key"]: m for m in client.get("/api/materials").get_json()}
        assert listed["creek clay"]["studio"] is True
        assert listed["whiting"]["source"]["type"] == "theoretical"
        picker = client.get("/api/chemistry/materials").get_json()["materials"]
        assert "Creek Clay" in [m["name"] for m in picker]

        result = _umf(client, "Creek Clay 30, Whiting 20, Silica 50")
        assert result["success"] is True and result["missing_materials"] == []
        assert result["umf_formula"]["Fe2O3"] > 0

    def test_names_cannot_clash_with_the_library(self, client):
        for name in ("Whiting", "chalk"):  # a library name and a library alias
            resp = _send(client, "POST", "/api/materials", LOCAL_CLAY | {"name": name})
            assert resp.status_code == 400

    def test_analysis_is_validated(self, client):
        bad = LOCAL_CLAY | {"oxides": {"Unobtainium": 50}}
        assert _send(client, "POST", "/api/materials", bad).status_code == 400
        off = LOCAL_CLAY | {"name": "Off Clay", "oxides": {"SiO2": 60}, "loi": 5}
        assert _send(client, "POST", "/api/materials", off).status_code == 400  # 65%
        near = LOCAL_CLAY | {"name": "Near Clay", "loi": 9.0}  # adds to 96.5%
        resp = _send(client, "POST", "/api/materials", near)
        assert resp.status_code == 201
        assert resp.get_json()["warnings"]

    def test_edit_and_delete(self, client):
        _send(client, "POST", "/api/materials", LOCAL_CLAY)
        edited = _send(
            client, "PUT", "/api/materials/creek clay", LOCAL_CLAY | {"loi": 11.0}
        )
        assert edited.status_code == 200 and edited.get_json()["loi"] == 11.0
        assert (
            _send(client, "PUT", "/api/materials/whiting", LOCAL_CLAY).status_code
            == 404
        )

        assert client.delete("/api/materials/creek clay").status_code == 200
        result = _umf(client, "Creek Clay 30, Whiting 20, Silica 50")
        assert result["missing_materials"] == ["Creek Clay"]


class TestLots:
    LOT = {
        "lot": "2611-A",
        "oxides": {"SiO2": 66.0, "Al2O3": 18.5, "K2O": 11.5, "Na2O": 3.0, "CaO": 0.5},
        "loi": 0.3,
        "source": "Supplier certificate for lot 2611-A",
    }

    def test_current_lot_replaces_the_standard_analysis(self, client):
        standard = _umf(client, RECIPE)["umf_formula"]["K2O"]

        resp = _send(client, "POST", "/api/materials/custer feldspar/lots", self.LOT)
        assert resp.status_code == 201
        lot_id = resp.get_json()["id"]
        with_lot = _umf(client, RECIPE)["umf_formula"]["K2O"]
        assert with_lot > standard

        listed = {m["key"]: m for m in client.get("/api/materials").get_json()}
        assert listed["custer feldspar"]["current_lot"]["lot"] == "2611-A"

        back = _send(
            client,
            "PUT",
            "/api/materials/custer feldspar/current-lot",
            {"lot_id": None},
        )
        assert back.status_code == 200
        assert _umf(client, RECIPE)["umf_formula"]["K2O"] == standard

        _send(
            client,
            "PUT",
            "/api/materials/custer feldspar/current-lot",
            {"lot_id": lot_id},
        )
        assert _umf(client, RECIPE)["umf_formula"]["K2O"] == with_lot

    def test_lots_need_a_known_material_and_a_label(self, client):
        assert (
            _send(client, "POST", "/api/materials/nope/lots", self.LOT).status_code
            == 404
        )
        unlabelled = self.LOT | {"lot": ""}
        resp = _send(client, "POST", "/api/materials/whiting/lots", unlabelled)
        assert resp.status_code == 400

    def test_deleting_the_current_lot_restores_the_standard(self, client):
        standard = _umf(client, RECIPE)["umf_formula"]["K2O"]
        lot_id = _send(
            client, "POST", "/api/materials/custer feldspar/lots", self.LOT
        ).get_json()["id"]
        assert (
            client.delete(f"/api/materials/custer feldspar/lots/{lot_id}").status_code
            == 200
        )
        assert _umf(client, RECIPE)["umf_formula"]["K2O"] == standard
        assert client.get("/api/materials/custer feldspar/lots").get_json() == []
