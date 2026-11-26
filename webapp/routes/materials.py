"""Materials routes: the published library, studio materials, and lot analyses."""

from flask import Blueprint, current_app, jsonify, request

from core.chemistry.materials import LIBRARY, normalize_material_name
from core.errors import error_payload
from core.security import rate_limit
from core import studio_materials as store

bp = Blueprint("materials", __name__)


def _db_path() -> str:
    return current_app.config.get("DATABASE_PATH", "glaze.db")


def _bad_request(error: Exception):
    return jsonify(error_payload(str(error), "invalid_material")), 400


def _not_found(what: str):
    return jsonify(error_payload(f"{what} not found", "not_found")), 404


def _library_dict(key, material) -> dict:
    return {
        "key": key,
        "name": material.name,
        "aliases": list(material.aliases),
        "category": material.category,
        "oxides": dict(material.oxides),
        "loi": material.loi,
        "source": dict(material.source),
    }


def _material_exists(key: str) -> bool:
    return key in LIBRARY or any(m["key"] == key for m in store.list_custom(_db_path()))


@bp.route("/api/materials")
@rate_limit(requests_per_minute=60)
def list_materials():
    """Every material: library and studio, each with its current lot if any."""
    lots = store.list_lots(_db_path())
    current = {lot["material_key"]: lot for lot in lots if lot["current"]}
    counts: dict = {}
    for lot in lots:
        counts[lot["material_key"]] = counts.get(lot["material_key"], 0) + 1
    materials = [
        _library_dict(key, m) | {"studio": False} for key, m in LIBRARY.items()
    ]
    materials += [m | {"studio": True} for m in store.list_custom(_db_path())]
    for material in materials:
        material["current_lot"] = current.get(material["key"])
        material["lot_count"] = counts.get(material["key"], 0)
    materials.sort(key=lambda m: m["name"].lower())
    return jsonify(materials)


@bp.route("/api/materials", methods=["POST"])
@rate_limit(requests_per_minute=30)
def create_material():
    """Add a studio material (name, aliases, category, oxides, loi, source, notes)."""
    try:
        material, warnings = store.save_custom(_db_path(), request.json or {})
    except store.MaterialError as e:
        return _bad_request(e)
    return jsonify(material | {"studio": True, "warnings": warnings}), 201


@bp.route("/api/materials/<key>", methods=["PUT"])
@rate_limit(requests_per_minute=30)
def update_material(key: str):
    """Edit a studio material. Library materials are read-only; record a lot instead."""
    try:
        material, warnings = store.save_custom(
            _db_path(), request.json or {}, key=normalize_material_name(key)
        )
    except LookupError:
        return _not_found("Studio material")
    except store.MaterialError as e:
        return _bad_request(e)
    return jsonify(material | {"studio": True, "warnings": warnings})


@bp.route("/api/materials/<key>", methods=["DELETE"])
@rate_limit(requests_per_minute=30)
def delete_material(key: str):
    if not store.delete_custom(_db_path(), normalize_material_name(key)):
        return _not_found("Studio material")
    return jsonify({"success": True})


@bp.route("/api/materials/<key>/lots")
@rate_limit(requests_per_minute=60)
def list_material_lots(key: str):
    key = normalize_material_name(key)
    if not _material_exists(key):
        return _not_found("Material")
    return jsonify(store.list_lots(_db_path(), key))


@bp.route("/api/materials/<key>/lots", methods=["POST"])
@rate_limit(requests_per_minute=30)
def add_material_lot(key: str):
    """Record a lot analysis (lot, oxides, loi, source, current=true)."""
    key = normalize_material_name(key)
    if not _material_exists(key):
        return _not_found("Material")
    try:
        lot, warnings = store.add_lot(_db_path(), key, request.json or {})
    except store.MaterialError as e:
        return _bad_request(e)
    return jsonify(lot | {"warnings": warnings}), 201


@bp.route("/api/materials/<key>/current-lot", methods=["PUT"])
@rate_limit(requests_per_minute=30)
def set_material_current_lot(key: str):
    """Body {"lot_id": <id>} to use a lot, or {"lot_id": null} for the standard analysis."""
    lot_id = (request.json or {}).get("lot_id")
    if lot_id is not None and not isinstance(lot_id, int):
        return _bad_request(ValueError("lot_id must be a lot id or null"))
    if not store.set_current_lot(_db_path(), normalize_material_name(key), lot_id):
        return _not_found("Lot")
    return jsonify({"success": True})


@bp.route("/api/materials/<key>/lots/<int:lot_id>", methods=["DELETE"])
@rate_limit(requests_per_minute=30)
def delete_material_lot(key: str, lot_id: int):
    if not store.delete_lot(_db_path(), normalize_material_name(key), lot_id):
        return _not_found("Lot")
    return jsonify({"success": True})
