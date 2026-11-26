"""Test tiles: field checks, the recipe as tested, photos, and the routes."""

import io
import json
import os
from unittest.mock import patch

import pytest

from core import tiles
from core.tiles import TileError, clean_fields, photo_kind

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


class TestFields:
    def test_fields_are_tidied(self):
        assert clean_fields(
            {
                "label": "  T-114 ",
                "fired_on": "2026-11-20",
                "cone": 6,
                "atmosphere": "Reduction",
                "verdict": "KEEP",
                "clay_body": "",
                "ignored": "x",
            }
        ) == {
            "label": "T-114",
            "fired_on": "2026-11-20",
            "cone": "6",
            "atmosphere": "reduction",
            "verdict": "keep",
            "clay_body": None,
        }

    @pytest.mark.parametrize(
        "data, message",
        [
            ({"fired_on": "20/11/2026"}, "date like"),
            ({"atmosphere": "electric"}, "Atmosphere must be"),
            ({"verdict": "maybe"}, "Verdict must be"),
            ({"label": "x" * 121}, "too long"),
            ({"result": "x" * 4001}, "too long"),
            ({"kiln": ["big"]}, "must be text"),
            ({"cone": True}, "must be text"),
        ],
    )
    def test_bad_fields_are_refused(self, data, message):
        with pytest.raises(TileError, match=message):
            clean_fields(data)

    def test_photo_kinds(self):
        assert [photo_kind(d) for d in (JPEG, PNG, WEBP)] == ["jpg", "png", "webp"]
        assert photo_kind(b"GIF89a" + b"\x00" * 20) is None


@pytest.fixture
def photos_dir(tmp_path):
    return str(tmp_path / "tile-photos")


@pytest.fixture
def client(test_db_path, photos_dir):
    # Own rate-limit bucket (the limiter is process-global, keyed by IP)
    env = {
        "DATABASE_PATH": test_db_path,
        "TRUSTED_PROXY": "127.0.0.1",
        "TILE_PHOTOS_PATH": photos_dir,
    }
    with patch.dict("os.environ", env):
        from server import create_app

        app = create_app({"mode": "personal", "database": {"path": test_db_path}})
        test_client = app.test_client()
        test_client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.42.0.117"
        yield test_client


def _post(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


def _put(client, path, body):
    return client.put(path, data=json.dumps(body), content_type="application/json")


def _save_recipe(client, glaze_id, recipe):
    resp = _post(client, f"/api/glazes/{glaze_id}/versions", {"recipe": recipe})
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _tile(client, **fields):
    resp = _post(client, "/api/tiles", {"glaze_id": "glaze-1"} | fields)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _upload(client, tile_id, data=JPEG):
    return client.post(
        f"/api/tiles/{tile_id}/photos",
        data={"photo": (io.BytesIO(data), "tile.jpg")},
        content_type="multipart/form-data",
    )


class TestRecipeTested:
    def test_tile_keeps_the_recipe_it_tested(self, client):
        v1 = _save_recipe(client, "glaze-1", "Silica 30, Whiting 20, EPK 50")
        tile = _tile(client, label="T-1", fired_on="2026-11-20")
        assert (tile["version_id"], tile["recipe"]) == (
            v1,
            "Silica 30, Whiting 20, EPK 50",
        )
        assert tile["glaze_name"] == "Chun Blue" and tile["photos"] == []

        _save_recipe(client, "glaze-1", "Silica 35, Whiting 15, EPK 50")
        edited = _put(client, f"/api/tiles/{tile['id']}", {"result": "Glossy"})
        assert edited.get_json()["recipe"] == "Silica 30, Whiting 20, EPK 50"
        assert edited.get_json()["result"] == "Glossy"
        assert edited.get_json()["label"] == "T-1"  # fields not sent stay

        # Choosing again (null = the glaze's current recipe) takes the new one
        retaken = _put(client, f"/api/tiles/{tile['id']}", {"version_id": None})
        assert retaken.get_json()["recipe"] == "Silica 35, Whiting 15, EPK 50"

    def test_an_older_version_can_be_chosen(self, client):
        v1 = _save_recipe(client, "glaze-1", "Silica 30, Whiting 20, EPK 50")
        _save_recipe(client, "glaze-1", "Silica 35, Whiting 15, EPK 50")
        tile = _tile(client, version_id=v1)
        assert (tile["version_id"], tile["recipe"]) == (
            v1,
            "Silica 30, Whiting 20, EPK 50",
        )

    def test_versions_of_other_glazes_are_refused(self, client):
        other = _save_recipe(client, "glaze-2", "Silica 50, Whiting 50")
        resp = _post(client, "/api/tiles", {"glaze_id": "glaze-1", "version_id": other})
        assert resp.status_code == 400
        assert "isn't one of this glaze's" in resp.get_json()["message"]

    def test_moving_a_tile_takes_the_new_glazes_recipe(self, client):
        _save_recipe(client, "glaze-2", "Silica 50, Whiting 50")
        tile = _tile(client)
        moved = _put(client, f"/api/tiles/{tile['id']}", {"glaze_id": "glaze-2"})
        assert moved.get_json()["glaze_name"] == "Iron Red"
        assert moved.get_json()["recipe"] == "Silica 50, Whiting 50"


class TestTileRoutes:
    def test_list_newest_firing_first_and_by_glaze(self, client):
        a = _tile(client, fired_on="2026-10-01")
        b = _tile(client, fired_on="2026-11-01")
        c = _tile(client)  # not fired yet: last
        d = _tile(client, glaze_id="glaze-2", fired_on="2026-12-01")
        ids = [t["id"] for t in client.get("/api/tiles").get_json()]
        assert ids == [d["id"], b["id"], a["id"], c["id"]]
        mine = client.get("/api/tiles?glaze_id=glaze-1").get_json()
        assert [t["id"] for t in mine] == [b["id"], a["id"], c["id"]]

    @pytest.mark.parametrize(
        "body, status, code",
        [
            ({}, 400, "invalid_tile"),
            ({"glaze_id": "no-such-glaze"}, 404, "not_found"),
            ({"glaze_id": "glaze-1", "verdict": "maybe"}, 400, "invalid_tile"),
            ({"glaze_id": "glaze-1", "version_id": "two"}, 400, "invalid_tile"),
        ],
    )
    def test_bad_tiles_are_refused(self, client, body, status, code):
        resp = _post(client, "/api/tiles", body)
        assert resp.status_code == status
        assert resp.get_json()["code"] == code

    def test_missing_tiles(self, client):
        assert client.get("/api/tiles/999").status_code == 404
        assert _put(client, "/api/tiles/999", {"label": "x"}).status_code == 404
        assert client.delete("/api/tiles/999").status_code == 404
        assert _upload(client, 999).status_code == 404


class TestPhotos:
    def test_photo_is_stored_served_and_deleted(self, client, photos_dir):
        tile = _tile(client)
        resp = _upload(client, tile["id"])
        assert resp.status_code == 201
        url = resp.get_json()["url"]
        assert url.startswith("/tile-photos/") and url.endswith(".jpg")
        served = client.get(url)
        assert served.status_code == 200 and served.data == JPEG
        assert "max-age=31536000" in served.headers["Cache-Control"]
        assert (
            client.get(f"/api/tiles/{tile['id']}").get_json()["photos"][0]["url"] == url
        )

        photo_id = resp.get_json()["id"]
        assert (
            client.delete(f"/api/tiles/{tile['id']}/photos/{photo_id}").status_code
            == 200
        )
        assert os.listdir(photos_dir) == []
        assert client.get(url).status_code == 404
        assert client.get(f"/api/tiles/{tile['id']}").get_json()["photos"] == []

    def test_deleting_a_tile_deletes_its_photos(self, client, photos_dir):
        tile = _tile(client)
        _upload(client, tile["id"], JPEG)
        _upload(client, tile["id"], PNG)
        assert len(os.listdir(photos_dir)) == 2
        assert client.delete(f"/api/tiles/{tile['id']}").status_code == 200
        assert os.listdir(photos_dir) == []

    def test_deleting_a_glaze_deletes_its_tiles_and_photos(self, client, photos_dir):
        tile = _tile(client)
        _upload(client, tile["id"])
        assert client.delete("/api/glazes/glaze-1").status_code == 200
        assert client.get(f"/api/tiles/{tile['id']}").status_code == 404
        assert os.listdir(photos_dir) == []

    def test_only_photos_are_accepted(self, client):
        tile = _tile(client)
        resp = _upload(client, tile["id"], b"GIF89a" + b"\x00" * 20)
        assert resp.status_code == 400 and resp.get_json()["code"] == "invalid_photo"
        resp = client.post(f"/api/tiles/{tile['id']}/photos", data={})
        assert resp.status_code == 400

    def test_size_and_count_limits(self, client):
        tile = _tile(client)
        with patch.object(tiles, "MAX_PHOTO_BYTES", 16):
            resp = _upload(client, tile["id"])
            assert resp.status_code == 400 and "too large" in resp.get_json()["message"]
        with patch.object(tiles, "MAX_PHOTOS_PER_TILE", 1):
            assert _upload(client, tile["id"]).status_code == 201
            resp = _upload(client, tile["id"])
            assert (
                resp.status_code == 400
                and "at most 1 photos" in resp.get_json()["message"]
            )

    def test_only_photo_names_are_served(self, client, photos_dir, test_db_path):
        os.makedirs(photos_dir, exist_ok=True)
        with open(os.path.join(photos_dir, "notes.txt"), "w") as handle:
            handle.write("private")
        assert client.get("/tile-photos/notes.txt").status_code == 404
        assert client.get("/tile-photos/..%2Fglaze.db").status_code == 404
        assert client.get(f"/tile-photos/{'0' * 32}.jpg").status_code == 404
