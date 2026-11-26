"""Frontend static file routes, including the catch-all.

This blueprint owns ``/<path:path>`` and is registered LAST in
``webapp.routes.ALL_BLUEPRINTS`` so concrete routes always win.
"""

from flask import Blueprint, jsonify, send_from_directory

from webapp import REPO_ROOT

bp = Blueprint("static_docs", __name__)


@bp.route("/")
def index():
    return send_from_directory(str(REPO_ROOT / "frontend"), "index.html")


@bp.route("/<path:path>")
def static_files(path):
    # Don't serve hidden files or paths outside the frontend directory
    if path.startswith(".") or ".." in path:
        return jsonify({"error": "Not found"}), 404
    response = send_from_directory(str(REPO_ROOT / "frontend"), path)
    if path == "sw.js":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
