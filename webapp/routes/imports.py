"""Import routes: read an Insight-Live recipe export and import its recipes.

The client sends the CSV text with both calls; the server keeps nothing
between the preview and the import.
"""

from flask import Blueprint, current_app, g, jsonify, request

from core.errors import error_payload
from core.glazes.importer import RecipeImportError, import_recipes, preview
from core.insight_live import ImportFormatError
from core.security import rate_limit

bp = Blueprint("imports", __name__)


def _db_path() -> str:
    return current_app.config.get("DATABASE_PATH", "glaze.db")


def _bad_request(text: str, code: str = "invalid_import"):
    return jsonify(error_payload(text, code, message=text)), 400


def _csv_text(data: dict):
    text = data.get("csv")
    return text if isinstance(text, str) and text.strip() else None


@bp.route("/api/import/insight-live/preview", methods=["POST"])
@rate_limit(requests_per_minute=30)
def preview_insight_live():
    """Report what importing an Insight-Live recipe CSV would do.

    Request body:
        csv: The export's text
    """
    text = _csv_text(request.get_json(silent=True) or {})
    if text is None:
        return _bad_request("No CSV text was sent.")
    try:
        return jsonify(preview(_db_path(), g.glaze_manager.user_id, text))
    except ImportFormatError as error:
        return _bad_request(str(error), "invalid_export")


@bp.route("/api/import/insight-live", methods=["POST"])
@rate_limit(requests_per_minute=10)
def import_insight_live():
    """Import chosen recipes from an Insight-Live recipe CSV as new glazes.

    Request body:
        csv: The export's text (the same text that was previewed)
        rows: Line numbers of the recipes to import, from the preview
        mapping: Optional {export material name: our material key}
        cone: Optional firing cone stored with every imported glaze
    """
    data = request.get_json(silent=True) or {}
    text = _csv_text(data)
    if text is None:
        return _bad_request("No CSV text was sent.")
    rows = data.get("rows")
    if not isinstance(rows, list) or not all(
        isinstance(row, int) and not isinstance(row, bool) for row in rows
    ):
        return _bad_request("rows must be a list of line numbers from the preview.")
    mapping = data.get("mapping") or {}
    if not isinstance(mapping, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()
    ):
        return _bad_request("mapping must map material names to material keys.")
    try:
        result = import_recipes(
            _db_path(),
            g.glaze_manager.user_id,
            text,
            rows,
            mapping=mapping,
            cone=data.get("cone"),
        )
    except ImportFormatError as error:
        return _bad_request(str(error), "invalid_export")
    except RecipeImportError as error:
        return _bad_request(str(error))
    return jsonify(result), 201
