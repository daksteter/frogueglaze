"""Test-tile records: one fired test of a glaze, with its photos.

A tile keeps the recipe as it was tested (a copy, plus the saved version it
came from when there is one), so later edits to the glaze don't rewrite its
history. Photos are files in a folder beside the database, named by a random
token and listed in ``tile_photos``. The browser shrinks and re-encodes them
before upload, which also drops the camera's location data; the server only
checks that the bytes are a JPEG, PNG or WebP image.
"""

import os
import re
import secrets
from datetime import date
from typing import Optional

from core.db import connect_db
from core.firing import schedule_exists

ATMOSPHERES = ("oxidation", "reduction", "neutral", "salt", "wood")
VERDICTS = ("keep", "retest", "reject")
MAX_SHORT_LENGTH = 120
MAX_RESULT_LENGTH = 4000
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTOS_PER_TILE = 20
PHOTO_URL_PREFIX = "/tile-photos/"
PHOTO_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

_SHORT_FIELDS = ("label", "cone", "kiln", "clay_body", "application")
_FIELDS = _SHORT_FIELDS + ("fired_on", "atmosphere", "result", "verdict")
_COLUMNS = (
    "t.id, t.glaze_id, g.name AS glaze_name, t.version_id, t.recipe, t.label, "
    "t.fired_on, t.cone, t.atmosphere, t.kiln, t.schedule_id, "
    "s.name AS schedule_name, t.clay_body, t.application, t.result, t.verdict, "
    "t.created_at, t.updated_at"
)
_LABELS = {"clay_body": "Clay body", "fired_on": "Date fired"}


class TileError(ValueError):
    """Invalid input; the message is meant for the person entering it."""


class TileNotFound(LookupError):
    """The tile, glaze, version or photo doesn't exist."""


def default_photos_dir(db_path: str) -> str:
    """Where tile photos live unless configured: beside the database."""
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), "tile-photos")


def _label(field: str) -> str:
    return _LABELS.get(field, field.replace("_", " ").capitalize())


def _text(field: str, value, limit: int) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise TileError(f"{_label(field)} must be text.")
    text = str(value).strip()
    if len(text) > limit:
        raise TileError(f"{_label(field)} is too long (at most {limit} characters).")
    return text or None


def _clean(field: str, value) -> Optional[str]:
    if field == "result":
        return _text(field, value, MAX_RESULT_LENGTH)
    text = _text(field, value, MAX_SHORT_LENGTH)
    if text is None:
        return None
    if field == "fired_on":
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            raise TileError("Date fired must be a date like 2026-11-26.") from None
    if field == "atmosphere" and text.lower() not in ATMOSPHERES:
        raise TileError(f"Atmosphere must be one of: {', '.join(ATMOSPHERES)}.")
    if field == "verdict" and text.lower() not in VERDICTS:
        raise TileError(f"Verdict must be one of: {', '.join(VERDICTS)}.")
    return text.lower() if field in ("atmosphere", "verdict") else text


def clean_fields(data: dict) -> dict:
    """The tile fields present in ``data``, checked and tidied."""
    return {f: _clean(f, data[f]) for f in _FIELDS if f in data}


def _id(value, what: str = "version_id") -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise TileError(f"{what} must be a number.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise TileError(f"{what} must be a number.") from None


def _schedule_field(conn, data: dict) -> dict:
    """{"schedule_id": ...} when ``data`` sets the firing schedule, else {}."""
    if "schedule_id" not in data:
        return {}
    schedule_id = _id(data["schedule_id"], "schedule_id")
    if schedule_id is not None and not schedule_exists(conn, schedule_id):
        raise TileError("That firing schedule doesn't exist.")
    return {"schedule_id": schedule_id}


def _recipe_tested(conn, glaze_id: str, version_id: Optional[int]) -> tuple:
    """(version_id, recipe) for the tile: the chosen version, or the current recipe.

    The current recipe is linked to the newest saved version when that
    version is the same recipe.
    """
    glaze = conn.execute("SELECT recipe FROM glazes WHERE id = ?", (glaze_id,))
    glaze = glaze.fetchone()
    if glaze is None:
        raise TileNotFound(f"Glaze not found: {glaze_id}")
    if version_id is not None:
        row = conn.execute(
            "SELECT id, recipe FROM recipe_versions WHERE id = ? AND glaze_id = ?",
            (version_id, glaze_id),
        ).fetchone()
        if row is None:
            raise TileError("That recipe version isn't one of this glaze's.")
        return row["id"], row["recipe"]
    newest = conn.execute(
        "SELECT id, recipe FROM recipe_versions WHERE glaze_id = ? ORDER BY id DESC LIMIT 1",
        (glaze_id,),
    ).fetchone()
    if newest is not None and newest["recipe"] == glaze["recipe"]:
        return newest["id"], newest["recipe"]
    return None, glaze["recipe"]


def _photo_dict(row) -> dict:
    return {
        "id": row["id"],
        "url": PHOTO_URL_PREFIX + row["filename"],
        "created_at": row["created_at"],
    }


def _with_photos(conn, tiles: list[dict]) -> list[dict]:
    by_id = {tile["id"]: tile for tile in tiles}
    for tile in tiles:
        tile["photos"] = []
    if not by_id:
        return tiles
    marks = ", ".join("?" * len(by_id))
    rows = conn.execute(
        f"SELECT id, tile_id, filename, created_at FROM tile_photos "
        f"WHERE tile_id IN ({marks}) ORDER BY id",
        tuple(by_id),
    ).fetchall()
    for row in rows:
        by_id[row["tile_id"]]["photos"].append(_photo_dict(row))
    return tiles


def _select(conn, where: str, params: tuple) -> list[dict]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM test_tiles t JOIN glazes g ON g.id = t.glaze_id "
        "LEFT JOIN firing_schedules s ON s.id = t.schedule_id "
        f"{where} ORDER BY t.fired_on IS NULL, t.fired_on DESC, t.id DESC",
        params,
    ).fetchall()
    return _with_photos(conn, [dict(row) for row in rows])


def list_tiles(db_path: str, glaze_id: Optional[str] = None) -> list[dict]:
    """Every tile, or one glaze's, most recently fired first, with photos."""
    conn = connect_db(db_path)
    try:
        if glaze_id is None:
            return _select(conn, "", ())
        return _select(conn, "WHERE t.glaze_id = ?", (glaze_id,))
    finally:
        conn.close()


def get_tile(db_path: str, tile_id: int) -> Optional[dict]:
    """One tile with its photos, or None."""
    conn = connect_db(db_path)
    try:
        tiles = _select(conn, "WHERE t.id = ?", (tile_id,))
        return tiles[0] if tiles else None
    finally:
        conn.close()


def create_tile(db_path: str, data: dict) -> dict:
    """Record a tile for ``data["glaze_id"]``; returns the saved tile."""
    glaze_id = _text("glaze_id", data.get("glaze_id"), MAX_SHORT_LENGTH)
    if not glaze_id:
        raise TileError("Choose the glaze this tile tests.")
    fields = clean_fields(data)
    conn = connect_db(db_path)
    try:
        with conn:
            version_id, recipe = _recipe_tested(
                conn, glaze_id, _id(data.get("version_id"))
            )
            fields |= _schedule_field(conn, data)
            columns = ["glaze_id", "version_id", "recipe", *fields]
            values = [glaze_id, version_id, recipe, *fields.values()]
            cursor = conn.execute(
                f"INSERT INTO test_tiles ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' * len(columns))})",
                values,
            )
        return _select(conn, "WHERE t.id = ?", (cursor.lastrowid,))[0]
    finally:
        conn.close()


def update_tile(db_path: str, tile_id: int, data: dict) -> dict:
    """Change the fields present in ``data``; returns the saved tile.

    Sending ``version_id`` (a saved version, or null for the glaze's current
    recipe) or moving the tile to another glaze takes that recipe as the one
    tested. Otherwise the recorded recipe stays as it was, whatever the
    glaze's recipe is now.
    """
    fields = clean_fields(data)
    new_glaze = _text("glaze_id", data.get("glaze_id"), MAX_SHORT_LENGTH)
    new_version = _id(data.get("version_id"))
    conn = connect_db(db_path)
    try:
        with conn:
            row = conn.execute(
                "SELECT glaze_id FROM test_tiles WHERE id = ?", (tile_id,)
            ).fetchone()
            if row is None:
                raise TileNotFound(f"Tile not found: {tile_id}")
            glaze_id = new_glaze or row["glaze_id"]
            if glaze_id != row["glaze_id"] or "version_id" in data:
                version_id, recipe = _recipe_tested(conn, glaze_id, new_version)
                fields |= {
                    "glaze_id": glaze_id,
                    "version_id": version_id,
                    "recipe": recipe,
                }
            fields |= _schedule_field(conn, data)
            sets = ", ".join(f"{column} = ?" for column in fields)
            conn.execute(
                f"UPDATE test_tiles SET {sets + ', ' if sets else ''}"
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*fields.values(), tile_id),
            )
        return _select(conn, "WHERE t.id = ?", (tile_id,))[0]
    finally:
        conn.close()


def remove_photo_files(photos_dir: str, filenames) -> None:
    """Delete photo files; ones already gone are fine."""
    for name in filenames:
        if PHOTO_NAME.match(name):
            try:
                os.remove(os.path.join(photos_dir, name))
            except FileNotFoundError:
                pass


def delete_tile(db_path: str, photos_dir: str, tile_id: int) -> bool:
    """Delete a tile and its photos; False if there was no such tile."""
    conn = connect_db(db_path)
    try:
        with conn:
            names = [
                row["filename"]
                for row in conn.execute(
                    "SELECT filename FROM tile_photos WHERE tile_id = ?", (tile_id,)
                )
            ]
            deleted = conn.execute(
                "DELETE FROM test_tiles WHERE id = ?", (tile_id,)
            ).rowcount
    finally:
        conn.close()
    remove_photo_files(photos_dir, names)
    return deleted > 0


def glaze_photo_files(db_path: str, glaze_id: str) -> list[str]:
    """Photo files of a glaze's tiles, to remove after the glaze is deleted."""
    conn = connect_db(db_path)
    try:
        rows = conn.execute(
            "SELECT p.filename FROM tile_photos p "
            "JOIN test_tiles t ON t.id = p.tile_id WHERE t.glaze_id = ?",
            (glaze_id,),
        ).fetchall()
        return [row["filename"] for row in rows]
    finally:
        conn.close()


def photo_kind(data: bytes) -> Optional[str]:
    """File extension for JPEG, PNG or WebP bytes, else None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def add_photo(db_path: str, photos_dir: str, tile_id: int, data: bytes) -> dict:
    """Store a photo for a tile; returns {id, url, created_at}."""
    if len(data) > MAX_PHOTO_BYTES:
        raise TileError(f"The photo is too large (at most {MAX_PHOTO_BYTES >> 20} MB).")
    kind = photo_kind(data)
    if kind is None:
        raise TileError("That file isn't a JPEG, PNG or WebP photo.")
    conn = connect_db(db_path)
    try:
        if (
            conn.execute("SELECT 1 FROM test_tiles WHERE id = ?", (tile_id,)).fetchone()
            is None
        ):
            raise TileNotFound(f"Tile not found: {tile_id}")
        count = conn.execute(
            "SELECT COUNT(*) FROM tile_photos WHERE tile_id = ?", (tile_id,)
        ).fetchone()[0]
        if count >= MAX_PHOTOS_PER_TILE:
            raise TileError(f"A tile can have at most {MAX_PHOTOS_PER_TILE} photos.")
        os.makedirs(photos_dir, exist_ok=True)
        name = f"{secrets.token_hex(16)}.{kind}"
        with open(os.path.join(photos_dir, name), "xb") as handle:
            handle.write(data)
        try:
            with conn:
                cursor = conn.execute(
                    "INSERT INTO tile_photos (tile_id, filename) VALUES (?, ?)",
                    (tile_id, name),
                )
        except Exception:
            remove_photo_files(photos_dir, [name])
            raise
        row = conn.execute(
            "SELECT id, filename, created_at FROM tile_photos WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return _photo_dict(row)
    finally:
        conn.close()


def delete_photo(db_path: str, photos_dir: str, tile_id: int, photo_id: int) -> bool:
    """Delete one of a tile's photos; False if the tile has no such photo."""
    conn = connect_db(db_path)
    try:
        with conn:
            row = conn.execute(
                "SELECT filename FROM tile_photos WHERE id = ? AND tile_id = ?",
                (photo_id, tile_id),
            ).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM tile_photos WHERE id = ?", (photo_id,))
    finally:
        conn.close()
    remove_photo_files(photos_dir, [row["filename"]])
    return True
