"""The studio's own materials and lot analyses, stored in SQLite.

The published library is ceramics-foundation/data/materials.json. Studio
materials are added to it; a material's *current* lot analysis replaces its
standard analysis in every calculation. ``sync_engine`` pushes both into the
chemistry engine, reloading only when the ``materials_rev`` counter changed,
so every server process stays current.
"""

import json
import threading
from typing import Optional

from core.chemistry.materials import (
    LIBRARY,
    OXIDE_MOLECULAR_WEIGHTS,
    Material,
    normalize_material_name,
    set_studio_materials,
)
from core.db import connect_db

CATEGORIES = (
    "feldspar",
    "clay",
    "silica",
    "flux",
    "frit",
    "colorant",
    "opacifier",
    "other",
)
MAX_NAME_LENGTH = 80
MAX_TEXT_LENGTH = 500


class MaterialError(ValueError):
    """Invalid input; the message is meant for the person entering it."""


# ---- Validation -------------------------------------------------------------


def validate_analysis(oxides, loi) -> tuple[dict, float, list[str]]:
    """Check an as-received analysis; return (oxides, loi, warnings)."""
    if not isinstance(oxides, dict) or not oxides:
        raise MaterialError("Enter the analysis: at least one oxide percentage.")
    clean = {}
    for oxide, value in oxides.items():
        if oxide not in OXIDE_MOLECULAR_WEIGHTS:
            raise MaterialError(f"Unknown oxide: {oxide}")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise MaterialError(f"{oxide} must be a number.") from None
        if not 0 <= number <= 100:
            raise MaterialError(f"{oxide} must be between 0 and 100.")
        if number > 0:
            clean[oxide] = round(number, 4)
    if not clean:
        raise MaterialError("Enter the analysis: at least one oxide percentage.")
    try:
        loi_value = float(loi or 0)
    except (TypeError, ValueError):
        raise MaterialError("LOI must be a number.") from None
    if not 0 <= loi_value < 100:
        raise MaterialError("LOI must be between 0 and 100.")
    total = sum(clean.values()) + loi_value
    if not 80 <= total <= 110:
        raise MaterialError(
            f"Oxides plus LOI add up to {total:.1f}%; check the numbers."
        )
    warnings = []
    if not 98 <= total <= 102:
        warnings.append(f"Oxides plus LOI add up to {total:.1f}%, not about 100%.")
    return clean, loi_value, warnings


def _text(value, field: str) -> Optional[str]:
    text = str(value or "").strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise MaterialError(f"{field} is too long.")
    return text or None


def _taken_names(conn, ignore_key: Optional[str] = None) -> set[str]:
    taken = set(LIBRARY)
    for material in LIBRARY.values():
        taken.update(a.lower() for a in material.aliases)
    for row in conn.execute("SELECT material_key, aliases FROM custom_materials"):
        if row["material_key"] == ignore_key:
            continue
        taken.add(row["material_key"])
        taken.update(a.lower() for a in json.loads(row["aliases"] or "[]"))
    return taken


def _validate_names(conn, name, aliases, ignore_key=None) -> tuple[str, list[str]]:
    name = str(name or "").strip()
    if not name or len(name) > MAX_NAME_LENGTH or any(c in name for c in "/,;+"):
        raise MaterialError("Give the material a name (no / , ; or +).")
    if isinstance(aliases, str):
        aliases = aliases.split(",")
    aliases = [str(a).strip() for a in aliases or [] if str(a).strip()]
    taken = _taken_names(conn, ignore_key)
    for candidate in [name, *aliases]:
        if normalize_material_name(candidate) in taken:
            raise MaterialError(f"“{candidate}” is already a material name.")
    return name, aliases


# ---- Studio materials ---------------------------------------------------------


def _bump(conn) -> None:
    conn.execute(
        "INSERT INTO studio_state (key, value) VALUES ('materials_rev', 1) "
        "ON CONFLICT(key) DO UPDATE SET value = value + 1"
    )


def _custom_dict(row) -> dict:
    return {
        "key": row["material_key"],
        "name": row["name"],
        "aliases": json.loads(row["aliases"] or "[]"),
        "category": row["category"],
        "oxides": json.loads(row["oxides"]),
        "loi": row["loi"],
        "source": {"type": "custom", "text": row["source"], "notes": row["notes"]},
    }


def list_custom(db_path: str) -> list[dict]:
    conn = connect_db(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM custom_materials ORDER BY name COLLATE NOCASE"
        )
        return [_custom_dict(row) for row in rows]
    finally:
        conn.close()


def save_custom(
    db_path: str, data: dict, key: Optional[str] = None
) -> tuple[dict, list]:
    """Create a studio material, or update the one at ``key``."""
    conn = connect_db(db_path)
    try:
        with conn:
            if key is not None:
                row = conn.execute(
                    "SELECT * FROM custom_materials WHERE material_key = ?", (key,)
                ).fetchone()
                if row is None:
                    raise LookupError(key)
                name = row["name"]  # renaming would orphan recipes that use it
                _, aliases = _validate_names(
                    conn, name, data.get("aliases"), ignore_key=key
                )
            else:
                name, aliases = _validate_names(
                    conn, data.get("name"), data.get("aliases")
                )
            oxides, loi, warnings = validate_analysis(
                data.get("oxides"), data.get("loi")
            )
            category = (
                data.get("category") if data.get("category") in CATEGORIES else "other"
            )
            values = (
                json.dumps(aliases),
                category,
                json.dumps(oxides),
                loi,
                _text(data.get("source"), "Source"),
                _text(data.get("notes"), "Notes"),
            )
            if key is None:
                key = normalize_material_name(name)
                conn.execute(
                    "INSERT INTO custom_materials (material_key, name, aliases, category, "
                    "oxides, loi, source, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (key, name, *values),
                )
            else:
                conn.execute(
                    "UPDATE custom_materials SET aliases = ?, category = ?, oxides = ?, "
                    "loi = ?, source = ?, notes = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE material_key = ?",
                    (*values, key),
                )
            _bump(conn)
            row = conn.execute(
                "SELECT * FROM custom_materials WHERE material_key = ?", (key,)
            ).fetchone()
        return _custom_dict(row), warnings
    finally:
        conn.close()


def delete_custom(db_path: str, key: str) -> bool:
    conn = connect_db(db_path)
    try:
        with conn:
            deleted = conn.execute(
                "DELETE FROM custom_materials WHERE material_key = ?", (key,)
            ).rowcount
            if deleted:
                conn.execute("DELETE FROM material_lots WHERE material_key = ?", (key,))
                _bump(conn)
        return bool(deleted)
    finally:
        conn.close()


# ---- Lot analyses -------------------------------------------------------------


def _lot_dict(row) -> dict:
    return {
        "id": row["id"],
        "material_key": row["material_key"],
        "lot": row["lot"],
        "oxides": json.loads(row["oxides"]),
        "loi": row["loi"],
        "source": row["source"],
        "current": bool(row["is_current"]),
        "created_at": row["created_at"],
    }


def list_lots(db_path: str, key: Optional[str] = None) -> list[dict]:
    """Lots of one material (or of all materials), newest first."""
    conn = connect_db(db_path)
    try:
        if key is None:
            rows = conn.execute("SELECT * FROM material_lots ORDER BY id DESC")
        else:
            rows = conn.execute(
                "SELECT * FROM material_lots WHERE material_key = ? ORDER BY id DESC",
                (key,),
            )
        return [_lot_dict(row) for row in rows]
    finally:
        conn.close()


def add_lot(db_path: str, key: str, data: dict) -> tuple[dict, list]:
    lot = _text(data.get("lot"), "Lot")
    if not lot or len(lot) > MAX_NAME_LENGTH:
        raise MaterialError("Give the lot a number or label.")
    oxides, loi, warnings = validate_analysis(data.get("oxides"), data.get("loi"))
    current = bool(data.get("current", True))
    conn = connect_db(db_path)
    try:
        with conn:
            if current:
                conn.execute(
                    "UPDATE material_lots SET is_current = 0 WHERE material_key = ?",
                    (key,),
                )
            cursor = conn.execute(
                "INSERT INTO material_lots (material_key, lot, oxides, loi, source, is_current) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    key,
                    lot,
                    json.dumps(oxides),
                    loi,
                    _text(data.get("source"), "Source"),
                    int(current),
                ),
            )
            _bump(conn)
            row = conn.execute(
                "SELECT * FROM material_lots WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return _lot_dict(row), warnings
    finally:
        conn.close()


def set_current_lot(db_path: str, key: str, lot_id: Optional[int]) -> bool:
    """Make ``lot_id`` the current lot for a material, or None for the standard analysis."""
    conn = connect_db(db_path)
    try:
        with conn:
            if (
                lot_id is not None
                and conn.execute(
                    "SELECT 1 FROM material_lots WHERE id = ? AND material_key = ?",
                    (lot_id, key),
                ).fetchone()
                is None
            ):
                return False
            conn.execute(
                "UPDATE material_lots SET is_current = 0 WHERE material_key = ?", (key,)
            )
            if lot_id is not None:
                conn.execute(
                    "UPDATE material_lots SET is_current = 1 WHERE id = ?", (lot_id,)
                )
            _bump(conn)
        return True
    finally:
        conn.close()


def delete_lot(db_path: str, key: str, lot_id: int) -> bool:
    conn = connect_db(db_path)
    try:
        with conn:
            deleted = conn.execute(
                "DELETE FROM material_lots WHERE id = ? AND material_key = ?",
                (lot_id, key),
            ).rowcount
            if deleted:
                _bump(conn)
        return bool(deleted)
    finally:
        conn.close()


# ---- Engine sync --------------------------------------------------------------

_sync_lock = threading.Lock()
_synced: dict = {"db_path": None, "rev": None}


def _engine_materials(db_path: str) -> tuple[list[Material], dict[str, Material]]:
    custom = {
        m["key"]: Material(
            name=m["name"],
            aliases=m["aliases"],
            oxides=m["oxides"],
            loi=m["loi"],
            category=m["category"],
            source=m["source"],
        )
        for m in list_custom(db_path)
    }
    active = {}
    for lot in (x for x in list_lots(db_path) if x["current"]):
        base = custom.get(lot["material_key"]) or LIBRARY.get(lot["material_key"])
        if base is None:
            continue
        active[lot["material_key"]] = Material(
            name=base.name,
            aliases=base.aliases,
            oxides=lot["oxides"],
            loi=lot["loi"],
            category=base.category,
            source={
                "type": "lot",
                "lot": lot["lot"],
                "lot_id": lot["id"],
                "text": lot["source"],
                "standard": base.source,
            },
        )
    return list(custom.values()), active


def sync_engine(db_path: str) -> None:
    """Load this database's studio materials into the engine if they changed."""
    conn = connect_db(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM studio_state WHERE key = 'materials_rev'"
        ).fetchone()
    finally:
        conn.close()
    rev = row["value"] if row else 0
    if _synced["db_path"] == db_path and _synced["rev"] == rev:
        return
    with _sync_lock:
        custom, active = _engine_materials(db_path)
        set_studio_materials(custom, active)
        _synced.update(db_path=db_path, rev=rev)


def reset_engine() -> None:
    """Back to the published library only (used by tests)."""
    with _sync_lock:
        set_studio_materials()
        _synced.update(db_path=None, rev=None)
