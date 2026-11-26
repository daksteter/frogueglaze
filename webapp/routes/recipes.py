"""Recipe editor routes: saved recipe versions and batch sheets."""

from flask import Blueprint, current_app, g, jsonify, request

from core.batch_sheet import BatchSheetError, batch_sheet
from core.errors import error_payload
from core.glazes.versions import list_versions, save_version
from core.security import rate_limit

bp = Blueprint("recipes", __name__)

MAX_RECIPE_LENGTH = 4000
MAX_NOTE_LENGTH = 200


def _db_path() -> str:
    return current_app.config.get("DATABASE_PATH", "glaze.db")


def _glaze_not_found(glaze_id: str):
    return jsonify(error_payload(f"Glaze not found: {glaze_id}", "not_found")), 404


@bp.route("/api/glazes/<glaze_id>/versions")
@rate_limit(requests_per_minute=60)
def list_recipe_versions(glaze_id: str):
    """List a glaze's saved recipe versions, newest first."""
    if g.glaze_manager.get_by_id(glaze_id) is None:
        return _glaze_not_found(glaze_id)
    return jsonify(list_versions(_db_path(), glaze_id))


@bp.route("/api/glazes/<glaze_id>/versions", methods=["POST"])
@rate_limit(requests_per_minute=30)
def save_recipe_version(glaze_id: str):
    """Save a recipe as the glaze's newest version and current recipe.

    Request body:
        recipe: Recipe string, e.g. "Custer Feldspar 45, Silica 25, +Red Iron Oxide 2"
        note: Optional short note about what changed
        cone: Optional firing cone; also stored on the glaze
    """
    glaze = g.glaze_manager.get_by_id(glaze_id)
    if glaze is None:
        return _glaze_not_found(glaze_id)

    data = request.json or {}
    recipe = str(data.get("recipe") or "").strip()
    note = str(data.get("note") or "").strip() or None
    cone = str(data.get("cone") or "").strip() or None
    if not recipe:
        return jsonify(error_payload("recipe is required", "missing_recipe")), 400
    if len(recipe) > MAX_RECIPE_LENGTH:
        return jsonify(error_payload("recipe is too long", "recipe_too_long")), 400
    if note and len(note) > MAX_NOTE_LENGTH:
        return jsonify(error_payload("note is too long", "note_too_long")), 400

    version = save_version(
        _db_path(),
        glaze_id,
        recipe,
        previous_recipe=glaze.recipe,
        note=note,
        cone=cone,
    )
    return jsonify(version), 201


@bp.route("/api/batch-sheet", methods=["POST"])
@rate_limit(requests_per_minute=120)
def make_batch_sheet():
    """Scale a recipe to a batch size for weighing out.

    Request body:
        recipe: Recipe string; materials keep their names, known or not
        size: Batch size in grams
        basis: "base" (the base weighs size, additions on top; default) or
            "total" (everything together weighs size)
    """
    data = request.get_json(silent=True) or {}
    recipe = str(data.get("recipe") or "").strip()
    size = data.get("size")
    if not recipe:
        return jsonify(error_payload("recipe is required", "missing_recipe")), 400
    if len(recipe) > MAX_RECIPE_LENGTH:
        return jsonify(error_payload("recipe is too long", "recipe_too_long")), 400
    if isinstance(size, bool):
        size = None
    try:
        sheet = batch_sheet(recipe, size, str(data.get("basis") or "base"))
    except BatchSheetError as error:
        text = str(error)
        return jsonify(error_payload(text, "invalid_batch", message=text)), 400
    return jsonify(sheet)
