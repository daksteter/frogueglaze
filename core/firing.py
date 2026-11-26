"""Firing schedules: the studio's kiln programs, with timing worked out.

A schedule is a list of segments, each a rate in degrees per hour (or None
for full speed: as fast as the kiln goes), a target temperature and a hold
in minutes, in the schedule's unit (F or C). A target below the previous
temperature is a controlled cool. Timing starts from room temperature.
Full-speed segments have no rate to time them by, so they are estimated at
FULL_SPEED_RATE and flagged, never silently counted as exact.
"""

import json
import math
from typing import Optional

from core.db import connect_db

UNITS = ("F", "C")
ROOM_TEMPERATURE = {"F": 70, "C": 21}
FULL_SPEED_RATE = {"F": 500, "C": 278}
MAX_TEMPERATURE = {"F": 2600, "C": 1430}
MAX_RATE = 9999
MAX_HOLD_MINUTES = 24 * 60
MAX_SEGMENTS = 30
MAX_NAME_LENGTH = 80
MAX_NOTE_LENGTH = 80
MAX_NOTES_LENGTH = 2000

_COLUMNS = "id, name, cone, unit, segments, notes, created_at, updated_at"


class ScheduleError(ValueError):
    """Invalid input; the message is meant for the person entering it."""


class ScheduleNotFound(LookupError):
    """No such schedule."""


def _number(value, what: str) -> float:
    if isinstance(value, bool) or value is None or value == "":
        raise ScheduleError(f"{what} needs a number.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ScheduleError(f"{what} needs a number, not {value!r}.") from None
    if not math.isfinite(number):
        raise ScheduleError(f"{what} needs a number.")
    return int(number) if number.is_integer() else round(number, 1)


def _segment(raw, n: int, unit: str) -> dict:
    if not isinstance(raw, dict):
        raise ScheduleError(
            f"Segment {n} must be an object with rate, target and hold."
        )
    rate = raw.get("rate")
    full = rate is None or (
        isinstance(rate, str) and rate.strip().lower() in ("", "full")
    )
    if not full:
        rate = _number(rate, f"Segment {n}'s rate")
        if not 0 < rate <= MAX_RATE:
            raise ScheduleError(
                f"Segment {n}'s rate must be more than 0 and at most {MAX_RATE} "
                f"degrees per hour; leave it blank for full speed."
            )
    target = _number(raw.get("target"), f"Segment {n}'s target temperature")
    if not 0 < target <= MAX_TEMPERATURE[unit]:
        raise ScheduleError(
            f"Segment {n}'s target must be more than 0 and at most "
            f"{MAX_TEMPERATURE[unit]} °{unit}."
        )
    hold = raw.get("hold")
    hold = 0 if hold in (None, "") else _number(hold, f"Segment {n}'s hold")
    if not 0 <= hold <= MAX_HOLD_MINUTES:
        raise ScheduleError(
            f"Segment {n}'s hold must be 0 to {MAX_HOLD_MINUTES} minutes."
        )
    note = str(raw.get("note") or "").strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise ScheduleError(
            f"Segment {n}'s note is too long (at most {MAX_NOTE_LENGTH})."
        )
    return {
        "rate": None if full else rate,
        "target": target,
        "hold": hold,
        "note": note or None,
    }


def clean_unit(value) -> str:
    unit = str(value or "F").strip().upper().lstrip("°")
    if unit not in UNITS:
        raise ScheduleError("The unit must be F or C.")
    return unit


def clean_segments(segments, unit: str) -> list[dict]:
    """Checked segments: rate (None = full speed), target, hold, note."""
    if not isinstance(segments, list) or not segments:
        raise ScheduleError("A schedule needs at least one segment.")
    if len(segments) > MAX_SEGMENTS:
        raise ScheduleError(f"A schedule can have at most {MAX_SEGMENTS} segments.")
    return [_segment(raw, n, unit) for n, raw in enumerate(segments, 1)]


def timing(segments: list[dict], unit: str) -> dict:
    """Time each segment from room temperature; points trace the curve.

    Each point is the end of a ramp or hold: {minutes, temp, full}, where
    ``full`` marks a ramp at full speed (its time is an estimate).
    """
    temp = ROOM_TEMPERATURE[unit]
    elapsed = 0.0
    points = [{"minutes": 0, "temp": temp, "full": False}]
    rows = []
    full_speed = 0
    for seg in segments:
        rate = seg["rate"] or FULL_SPEED_RATE[unit]
        full_speed += seg["rate"] is None
        ramp = abs(seg["target"] - temp) / rate * 60
        elapsed += ramp
        points.append(
            {
                "minutes": round(elapsed, 1),
                "temp": seg["target"],
                "full": seg["rate"] is None,
            }
        )
        if seg["hold"]:
            elapsed += seg["hold"]
            points.append(
                {"minutes": round(elapsed, 1), "temp": seg["target"], "full": False}
            )
        direction = (
            "hold"
            if seg["target"] == temp
            else "heat" if seg["target"] > temp else "cool"
        )
        rows.append(
            {
                "ramp_minutes": round(ramp, 1),
                "elapsed_minutes": round(elapsed, 1),
                "direction": direction,
            }
        )
        temp = seg["target"]
    return {
        "start": ROOM_TEMPERATURE[unit],
        "peak": max(seg["target"] for seg in segments),
        "total_minutes": round(elapsed, 1),
        "full_speed_segments": full_speed,
        "full_speed_rate": FULL_SPEED_RATE[unit],
        "segments": rows,
        "points": points,
    }


def _text(value, what: str, limit: int) -> Optional[str]:
    if isinstance(value, bool) or (
        value is not None and not isinstance(value, (str, int, float))
    ):
        raise ScheduleError(f"{what} must be text.")
    text = str(value if value is not None else "").strip()
    if len(text) > limit:
        raise ScheduleError(f"{what} is too long (at most {limit} characters).")
    return text or None


def clean_schedule(data: dict, current: Optional[dict] = None) -> dict:
    """The full checked schedule from ``data``, falling back to ``current``."""
    merged = {**(current or {}), **data}
    name = _text(merged.get("name"), "The name", MAX_NAME_LENGTH)
    if not name:
        raise ScheduleError("Give the schedule a name.")
    unit = clean_unit(merged.get("unit"))
    return {
        "name": name,
        "cone": _text(merged.get("cone"), "The cone", 20),
        "unit": unit,
        "segments": clean_segments(merged.get("segments"), unit),
        "notes": _text(merged.get("notes"), "The notes", MAX_NOTES_LENGTH),
    }


def _row_dict(row, tile_count: int = 0) -> dict:
    schedule = dict(row)
    schedule["segments"] = json.loads(schedule["segments"])
    schedule["timing"] = timing(schedule["segments"], schedule["unit"])
    schedule["tile_count"] = tile_count
    return schedule


def _tile_counts(conn) -> dict:
    rows = conn.execute(
        "SELECT schedule_id, COUNT(*) FROM test_tiles WHERE schedule_id IS NOT NULL GROUP BY schedule_id"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def list_schedules(db_path: str) -> list[dict]:
    """Every schedule, by name, with timing and how many tiles use it."""
    conn = connect_db(db_path)
    try:
        counts = _tile_counts(conn)
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM firing_schedules ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [_row_dict(row, counts.get(row["id"], 0)) for row in rows]
    finally:
        conn.close()


def _get(conn, schedule_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM firing_schedules WHERE id = ?", (schedule_id,)
    ).fetchone()
    return _row_dict(row, _tile_counts(conn).get(schedule_id, 0)) if row else None


def get_schedule(db_path: str, schedule_id: int) -> Optional[dict]:
    conn = connect_db(db_path)
    try:
        return _get(conn, schedule_id)
    finally:
        conn.close()


def _name_taken(conn, name: str, schedule_id: Optional[int] = None) -> bool:
    row = conn.execute(
        "SELECT id FROM firing_schedules WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
        (name, schedule_id),
    ).fetchone()
    return row is not None


def create_schedule(db_path: str, data: dict) -> dict:
    schedule = clean_schedule(data)
    conn = connect_db(db_path)
    try:
        with conn:
            if _name_taken(conn, schedule["name"]):
                raise ScheduleError(
                    f"There is already a schedule named {schedule['name']}."
                )
            cursor = conn.execute(
                "INSERT INTO firing_schedules (name, cone, unit, segments, notes) VALUES (?, ?, ?, ?, ?)",
                (
                    schedule["name"],
                    schedule["cone"],
                    schedule["unit"],
                    json.dumps(schedule["segments"]),
                    schedule["notes"],
                ),
            )
        return _get(conn, cursor.lastrowid)
    finally:
        conn.close()


def update_schedule(db_path: str, schedule_id: int, data: dict) -> dict:
    """Change the fields sent; the others stay as they were."""
    conn = connect_db(db_path)
    try:
        with conn:
            current = _get(conn, schedule_id)
            if current is None:
                raise ScheduleNotFound(f"Schedule not found: {schedule_id}")
            schedule = clean_schedule(data, current)
            if _name_taken(conn, schedule["name"], schedule_id):
                raise ScheduleError(
                    f"There is already a schedule named {schedule['name']}."
                )
            conn.execute(
                "UPDATE firing_schedules SET name = ?, cone = ?, unit = ?, segments = ?, "
                "notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    schedule["name"],
                    schedule["cone"],
                    schedule["unit"],
                    json.dumps(schedule["segments"]),
                    schedule["notes"],
                    schedule_id,
                ),
            )
        return _get(conn, schedule_id)
    finally:
        conn.close()


def delete_schedule(db_path: str, schedule_id: int) -> bool:
    """Delete a schedule; tiles that used it keep their records, unlinked."""
    conn = connect_db(db_path)
    try:
        with conn:
            return (
                conn.execute(
                    "DELETE FROM firing_schedules WHERE id = ?", (schedule_id,)
                ).rowcount
                > 0
            )
    finally:
        conn.close()


def schedule_exists(conn, schedule_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM firing_schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        is not None
    )
