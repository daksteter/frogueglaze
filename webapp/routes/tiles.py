"""Test-tile routes: tile records, their photos, and the photo files."""

from flask import Blueprint, abort, current_app, jsonify, request, send_from_directory

from core import tiles as store
from core.errors import error_payload
from core.security import rate_limit

bp = Blueprint("tiles", __name__)


def _db_path() -> str:
    return current_app.config.get("DATABASE_PATH", "glaze.db")


def _photos_dir() -> str:
    return current_app.config.get("TILE_PHOTOS_PATH") or store.default_photos_dir(
        _db_path()
    )


def _bad_request(error: Exception, code: str = "invalid_tile"):
    return jsonify(error_payload(str(error), code, message=str(error))), 400


def _not_found(text: str):
    return jsonify(error_payload(text, "not_found", message=text)), 404


@bp.route("/api/tiles")
@rate_limit(requests_per_minute=60)
def list_tiles():
    """All tiles, or one glaze's with ?glaze_id=, most recently fired first."""
    return jsonify(store.list_tiles(_db_path(), request.args.get("glaze_id") or None))


@bp.route("/api/tiles/<int:tile_id>")
@rate_limit(requests_per_minute=60)
def get_tile(tile_id: int):
    """One tile with its photos."""
    tile = store.get_tile(_db_path(), tile_id)
    return jsonify(tile) if tile else _not_found(f"Tile not found: {tile_id}")


@bp.route("/api/tiles", methods=["POST"])
@rate_limit(requests_per_minute=30)
def create_tile():
    """Record a tile.

    Request body: glaze_id (required); version_id (optional, the saved
    version tested; default the glaze's current recipe); label, fired_on
    (YYYY-MM-DD), cone, atmosphere, kiln, clay_body, application, result,
    verdict (keep, retest or reject).
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _bad_request(ValueError("Send the tile as a JSON object."))
    try:
        return jsonify(store.create_tile(_db_path(), data)), 201
    except store.TileNotFound as e:
        return _not_found(str(e))
    except store.TileError as e:
        return _bad_request(e)


@bp.route("/api/tiles/<int:tile_id>", methods=["PUT"])
@rate_limit(requests_per_minute=30)
def update_tile(tile_id: int):
    """Change the fields sent; the others stay as they were."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _bad_request(ValueError("Send the changes as a JSON object."))
    try:
        return jsonify(store.update_tile(_db_path(), tile_id, data))
    except store.TileNotFound as e:
        return _not_found(str(e))
    except store.TileError as e:
        return _bad_request(e)


@bp.route("/api/tiles/<int:tile_id>", methods=["DELETE"])
@rate_limit(requests_per_minute=30)
def delete_tile(tile_id: int):
    """Delete a tile and its photos."""
    if not store.delete_tile(_db_path(), _photos_dir(), tile_id):
        return _not_found(f"Tile not found: {tile_id}")
    return jsonify({"deleted": True})


@bp.route("/api/tiles/<int:tile_id>/photos", methods=["POST"])
@rate_limit(requests_per_minute=60)
def add_tile_photo(tile_id: int):
    """Add a photo: multipart/form-data with the image in the ``photo`` field."""
    limit = store.MAX_PHOTO_BYTES + 64 * 1024  # room for the form around it
    if request.content_length and request.content_length > limit:
        text = f"The photo is too large (at most {store.MAX_PHOTO_BYTES >> 20} MB)."
        return jsonify(error_payload(text, "photo_too_large", message=text)), 413
    upload = request.files.get("photo")
    if upload is None:
        return _bad_request(ValueError("Attach the photo in the 'photo' field."))
    data = upload.read(store.MAX_PHOTO_BYTES + 1)
    try:
        photo = store.add_photo(_db_path(), _photos_dir(), tile_id, data)
    except store.TileNotFound as e:
        return _not_found(str(e))
    except store.TileError as e:
        return _bad_request(e, "invalid_photo")
    return jsonify(photo), 201


@bp.route("/api/tiles/<int:tile_id>/photos/<int:photo_id>", methods=["DELETE"])
@rate_limit(requests_per_minute=30)
def delete_tile_photo(tile_id: int, photo_id: int):
    """Delete one of a tile's photos."""
    if not store.delete_photo(_db_path(), _photos_dir(), tile_id, photo_id):
        return _not_found(f"Photo not found: {photo_id}")
    return jsonify({"deleted": True})


@bp.route(store.PHOTO_URL_PREFIX + "<filename>")
def tile_photo(filename: str):
    """A photo file. Names are random and never reused, so it caches forever."""
    if not store.PHOTO_NAME.match(filename):
        abort(404)
    return send_from_directory(_photos_dir(), filename, max_age=365 * 24 * 3600)
