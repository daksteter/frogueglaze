"""Firing schedule routes: the studio's kiln programs, with timing."""

from flask import Blueprint, current_app, jsonify, request

from core import firing as store
from core.errors import error_payload
from core.security import rate_limit

bp = Blueprint("firing", __name__)


def _db_path() -> str:
    return current_app.config.get("DATABASE_PATH", "glaze.db")


def _bad_request(text: str):
    return jsonify(error_payload(text, "invalid_schedule", message=text)), 400


def _not_found(schedule_id: int):
    text = f"Schedule not found: {schedule_id}"
    return jsonify(error_payload(text, "not_found", message=text)), 404


def _json_object():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@bp.route("/api/firing-schedules")
@rate_limit(requests_per_minute=60)
def list_schedules():
    """Every schedule by name, each with ``timing`` and ``tile_count``."""
    return jsonify(store.list_schedules(_db_path()))


@bp.route("/api/firing-schedules/<int:schedule_id>")
@rate_limit(requests_per_minute=60)
def get_schedule(schedule_id: int):
    schedule = store.get_schedule(_db_path(), schedule_id)
    return jsonify(schedule) if schedule else _not_found(schedule_id)


@bp.route("/api/firing-schedules", methods=["POST"])
@rate_limit(requests_per_minute=30)
def create_schedule():
    """Save a schedule.

    Request body: name (required, unique), cone, unit ("F" default, or "C"),
    notes, and segments: a list of {rate, target, hold, note}. rate is
    degrees per hour, or null for full speed; hold is in minutes.
    """
    data = _json_object()
    if data is None:
        return _bad_request("Send the schedule as a JSON object.")
    try:
        return jsonify(store.create_schedule(_db_path(), data)), 201
    except store.ScheduleError as e:
        return _bad_request(str(e))


@bp.route("/api/firing-schedules/<int:schedule_id>", methods=["PUT"])
@rate_limit(requests_per_minute=30)
def update_schedule(schedule_id: int):
    """Change the fields sent; segments, when sent, replace the old ones."""
    data = _json_object()
    if data is None:
        return _bad_request("Send the changes as a JSON object.")
    try:
        return jsonify(store.update_schedule(_db_path(), schedule_id, data))
    except store.ScheduleNotFound:
        return _not_found(schedule_id)
    except store.ScheduleError as e:
        return _bad_request(str(e))


@bp.route("/api/firing-schedules/<int:schedule_id>", methods=["DELETE"])
@rate_limit(requests_per_minute=30)
def delete_schedule(schedule_id: int):
    """Delete a schedule; test tiles that used it keep their records."""
    if not store.delete_schedule(_db_path(), schedule_id):
        return _not_found(schedule_id)
    return jsonify({"deleted": True})


@bp.route("/api/firing-schedules/timing", methods=["POST"])
@rate_limit(requests_per_minute=240)
def schedule_timing():
    """Time segments without saving them (for the editor's live preview).

    Request body: unit and segments, as for saving.
    """
    data = _json_object()
    if data is None:
        return _bad_request("Send the segments as a JSON object.")
    try:
        unit = store.clean_unit(data.get("unit"))
        segments = store.clean_segments(data.get("segments"), unit)
    except store.ScheduleError as e:
        return _bad_request(str(e))
    return jsonify(store.timing(segments, unit))
