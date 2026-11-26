"""Firing schedules: segment checks, timing, the routes, and links from tiles."""

import json
import sqlite3
from unittest.mock import patch

import pytest

from core.firing import ScheduleError, clean_schedule, clean_segments, timing

CONE6 = [
    {"rate": 200, "target": 220, "hold": 60, "note": "candle"},
    {"rate": 400, "target": 2000},
    {"rate": 108, "target": 2232, "hold": 10},
    {"rate": None, "target": 1900},
    {"rate": 150, "target": 1400, "note": "slow cool"},
]


class TestSegments:
    def test_segments_are_tidied(self):
        segments = clean_segments(
            [
                {"rate": "200", "target": "220.0", "hold": ""},
                {"rate": "full", "target": 2232},
            ],
            "F",
        )
        assert segments == [
            {"rate": 200, "target": 220, "hold": 0, "note": None},
            {"rate": None, "target": 2232, "hold": 0, "note": None},
        ]

    @pytest.mark.parametrize(
        "segments, unit, message",
        [
            ([], "F", "at least one segment"),
            ([{"rate": 0, "target": 100}], "F", "more than 0 and at most 9999"),
            ([{"rate": 100}], "F", "target temperature needs a number"),
            ([{"rate": 100, "target": "hot"}], "F", "needs a number, not 'hot'"),
            ([{"rate": 100, "target": 1500}], "C", "at most 1430 °C"),
            (
                [{"rate": 100, "target": 2000, "hold": -5}],
                "F",
                "hold must be 0 to 1440",
            ),
            (
                [{"rate": 100, "target": 2000, "note": "x" * 81}],
                "F",
                "note is too long",
            ),
            (["fast"], "F", "Segment 1 must be an object"),
            ([{"rate": 100, "target": 500}] * 31, "F", "at most 30 segments"),
        ],
    )
    def test_bad_segments_are_refused(self, segments, unit, message):
        with pytest.raises(ScheduleError, match=message):
            clean_segments(segments, unit)

    def test_schedule_needs_a_name_and_a_known_unit(self):
        with pytest.raises(ScheduleError, match="name"):
            clean_schedule({"segments": CONE6})
        with pytest.raises(ScheduleError, match="F or C"):
            clean_schedule({"name": "x", "unit": "K", "segments": CONE6})
        assert (
            clean_schedule({"name": " Glaze ", "unit": "°c", "segments": CONE6[:1]})[
                "unit"
            ]
            == "C"
        )


class TestTiming:
    def test_cone6_slow_cool(self):
        result = timing(clean_segments(CONE6, "F"), "F")
        # 45 + 60 hold, 267, 128.9 + 10 hold, 39.8 at full speed, 200
        assert [s["ramp_minutes"] for s in result["segments"]] == [
            45,
            267,
            128.9,
            39.8,
            200,
        ]
        assert [s["elapsed_minutes"] for s in result["segments"]] == [
            105,
            372,
            510.9,
            550.7,
            750.7,
        ]
        assert [s["direction"] for s in result["segments"]] == [
            "heat",
            "heat",
            "heat",
            "cool",
            "cool",
        ]
        assert (result["peak"], result["total_minutes"]) == (2232, 750.7)
        assert (result["full_speed_segments"], result["full_speed_rate"]) == (1, 500)
        # A point at the end of each ramp and each hold; the full-speed one flagged
        assert len(result["points"]) == 1 + 5 + 2
        assert [p["full"] for p in result["points"]].count(True) == 1

    def test_celsius_starts_from_room_temperature(self):
        result = timing(
            clean_segments([{"rate": 100, "target": 1221, "hold": 15}], "C"), "C"
        )
        assert result["start"] == 21 and result["total_minutes"] == 735

    def test_a_segment_at_the_same_temperature_is_a_hold(self):
        segments = clean_segments(
            [{"rate": 100, "target": 170}, {"rate": 100, "target": 170, "hold": 30}],
            "F",
        )
        result = timing(segments, "F")
        assert result["segments"][1] == {
            "ramp_minutes": 0,
            "elapsed_minutes": 90,
            "direction": "hold",
        }


@pytest.fixture
def client(test_db_path, tmp_path):
    # Own rate-limit bucket (the limiter is process-global, keyed by IP)
    env = {
        "DATABASE_PATH": test_db_path,
        "TRUSTED_PROXY": "127.0.0.1",
        "TILE_PHOTOS_PATH": str(tmp_path / "tile-photos"),
    }
    with patch.dict("os.environ", env):
        from server import create_app

        app = create_app({"mode": "personal", "database": {"path": test_db_path}})
        test_client = app.test_client()
        test_client.environ_base["HTTP_X_FORWARDED_FOR"] = "10.42.0.130"
        yield test_client


def _send(client, method, path, body):
    return client.open(
        path, method=method, data=json.dumps(body), content_type="application/json"
    )


def _schedule(client, **fields):
    body = {"name": "Cone 6 slow cool", "cone": "6", "segments": CONE6} | fields
    resp = _send(client, "POST", "/api/firing-schedules", body)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


class TestScheduleRoutes:
    def test_save_list_edit_and_delete(self, client):
        saved = _schedule(client, notes="Big kiln")
        assert saved["unit"] == "F" and saved["timing"]["total_minutes"] == 750.7
        assert saved["segments"][3]["rate"] is None and saved["tile_count"] == 0
        _schedule(client, name="bisque 04", cone="04", segments=CONE6[:2])
        names = [s["name"] for s in client.get("/api/firing-schedules").get_json()]
        assert names == ["bisque 04", "Cone 6 slow cool"]

        path = f"/api/firing-schedules/{saved['id']}"
        edited = _send(client, "PUT", path, {"segments": CONE6[:3]}).get_json()
        assert edited["name"] == "Cone 6 slow cool" and edited["notes"] == "Big kiln"
        assert edited["timing"]["total_minutes"] == 510.9
        assert client.delete(path).get_json() == {"deleted": True}
        assert client.get(path).status_code == 404

    def test_names_are_unique_ignoring_case(self, client):
        first = _schedule(client)
        resp = _send(
            client,
            "POST",
            "/api/firing-schedules",
            {"name": "CONE 6 SLOW COOL", "segments": CONE6},
        )
        assert (
            resp.status_code == 400
            and "already a schedule" in resp.get_json()["message"]
        )
        # Renaming to its own name (other case) is fine
        path = f"/api/firing-schedules/{first['id']}"
        assert (
            _send(client, "PUT", path, {"name": "cone 6 slow cool"}).status_code == 200
        )

    @pytest.mark.parametrize(
        "method, path, body, status",
        [
            ("POST", "/api/firing-schedules", {"name": "x", "segments": []}, 400),
            ("POST", "/api/firing-schedules", ["not", "an", "object"], 400),
            ("PUT", "/api/firing-schedules/999", {"name": "x"}, 404),
            ("DELETE", "/api/firing-schedules/999", {}, 404),
        ],
    )
    def test_bad_requests(self, client, method, path, body, status):
        assert _send(client, method, path, body).status_code == status

    def test_timing_without_saving(self, client):
        body = {"unit": "C", "segments": [{"rate": 100, "target": 1221, "hold": 15}]}
        resp = _send(client, "POST", "/api/firing-schedules/timing", body)
        assert resp.status_code == 200 and resp.get_json()["total_minutes"] == 735
        bad = _send(client, "POST", "/api/firing-schedules/timing", {"segments": [{}]})
        assert bad.status_code == 400 and "Segment 1" in bad.get_json()["message"]
        assert client.get("/api/firing-schedules").get_json() == []


class TestTileLinks:
    def test_tiles_link_to_a_schedule_and_survive_its_deletion(self, client):
        schedule = _schedule(client)
        tile = _send(
            client,
            "POST",
            "/api/tiles",
            {"glaze_id": "glaze-1", "schedule_id": schedule["id"]},
        ).get_json()
        assert tile["schedule_name"] == "Cone 6 slow cool"
        listed = client.get("/api/firing-schedules").get_json()[0]
        assert listed["tile_count"] == 1

        client.delete(f"/api/firing-schedules/{schedule['id']}")
        kept = client.get(f"/api/tiles/{tile['id']}").get_json()
        assert kept["schedule_id"] is None and kept["schedule_name"] is None

    def test_unknown_schedules_are_refused_and_links_can_be_cleared(self, client):
        resp = _send(
            client, "POST", "/api/tiles", {"glaze_id": "glaze-1", "schedule_id": 999}
        )
        assert resp.status_code == 400 and "doesn't exist" in resp.get_json()["message"]
        schedule = _schedule(client)
        tile = _send(
            client,
            "POST",
            "/api/tiles",
            {"glaze_id": "glaze-1", "schedule_id": schedule["id"]},
        ).get_json()
        cleared = _send(
            client, "PUT", f"/api/tiles/{tile['id']}", {"schedule_id": None}
        )
        assert cleared.get_json()["schedule_id"] is None


def test_older_tile_tables_gain_the_schedule_column(tmp_path):
    """A database made before schedules existed gets test_tiles.schedule_id."""
    from webapp.db import init_db

    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE test_tiles (id INTEGER PRIMARY KEY, glaze_id TEXT NOT NULL, "
        "version_id INTEGER, recipe TEXT, label TEXT, fired_on TEXT, cone TEXT, "
        "atmosphere TEXT, kiln TEXT, clay_body TEXT, application TEXT, result TEXT, "
        "verdict TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)"
    )
    conn.commit()
    conn.close()
    init_db(path)
    conn = sqlite3.connect(path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(test_tiles)")}
    conn.close()
    assert "schedule_id" in columns
