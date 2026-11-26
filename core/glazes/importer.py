"""Import recipes from an Insight-Live export as glazes.

``preview`` reports what an import would do: each recipe with its materials
and additions, how each material name matched our library, and recipes that
were imported before. ``import_recipes`` writes the chosen recipes as new
glazes in one transaction, each with a first saved recipe version and a
``glaze_imports`` row recording its Insight-Live code and original amounts.

Material names that match keep the export's spelling in the recipe, since
the calculator reads them the same way. A name the user maps to a different
material is written as that material's name. Unmatched names are kept as
they are, so they calculate once a studio material with that name exists.
"""

import json
import re
from typing import Dict, Iterable, List, Optional

from core.chemistry.materials import get_material, resolve_material_key
from core.chemistry.parser import match_material_key
from core.db import connect_db
from core.glazes.manager import _slugify
from core.insight_live import (
    ExportFile,
    ExportRecipe,
    MaterialMatch,
    match_materials,
    notes_for,
    parse_export,
    recipe_string,
)

SOURCE = "insight-live"
VERSION_NOTE = "Imported from Insight-Live"
MAX_NAME_LENGTH = 200
_CONE = re.compile(r"0?\d{1,2}")


class RecipeImportError(ValueError):
    """The import request can't be carried out as given."""


def _scope(user_id: Optional[str], alias: str = "glazes"):
    """SQL filter for the glazes this user can see (GlazeManager's rule)."""
    if user_id:
        return f" AND ({alias}.user_id = ? OR {alias}.user_id IS NULL)", [user_id]
    return "", []


def _existing(db_path: str, user_id: Optional[str], recipes: List[ExportRecipe]):
    """Visible glazes each recipe would duplicate, keyed by row.

    A recipe whose Insight-Live code was imported before matches that glaze;
    otherwise a glaze with the same name (ignoring case) is reported.
    """
    conn = connect_db(db_path)
    try:
        clause, params = _scope(user_id, "g")
        imported = conn.execute(
            "SELECT gi.source_code, g.id, g.name FROM glaze_imports gi "
            "JOIN glazes g ON g.id = gi.glaze_id "
            "WHERE gi.source = ? AND gi.source_code IS NOT NULL" + clause,
            [SOURCE, *params],
        ).fetchall()
        named = conn.execute(
            "SELECT g.id, g.name FROM glazes g WHERE 1 = 1" + clause, params
        ).fetchall()
    finally:
        conn.close()
    by_code = {row["source_code"]: row for row in imported}
    by_name = {(row["name"] or "").strip().lower(): row for row in named}
    found = {}
    for recipe in recipes:
        if recipe.code and recipe.code in by_code:
            row = by_code[recipe.code]
            found[recipe.row] = {"id": row["id"], "name": row["name"], "reason": "code"}
        elif recipe.name.lower() in by_name:
            row = by_name[recipe.name.lower()]
            found[recipe.row] = {"id": row["id"], "name": row["name"], "reason": "name"}
    return found


def _match_dict(match: MaterialMatch, used_in: int) -> dict:
    material = match.material
    return {
        "name": match.name,
        "key": match.key,
        "material": material.name if material else None,
        "partial": match.partial,
        "source_type": (material.source or {}).get("type") if material else None,
        "recipes": used_in,
    }


def _recipe_dict(recipe: ExportRecipe, existing: Optional[dict]) -> dict:
    return {
        "row": recipe.row,
        "code": recipe.code,
        "name": recipe.name,
        "description": recipe.description,
        "date": recipe.date,
        "comments": recipe.comments,
        "materials": [
            {"name": m.name, "amount": m.amount, "addition": m.addition}
            for m in recipe.materials
        ],
        "additions": recipe.additions,
        "base_total": recipe.base_total,
        "additions_total": recipe.additions_total,
        "warnings": list(recipe.warnings),
        "existing": existing,
    }


def preview(db_path: str, user_id: Optional[str], text: str) -> dict:
    """What importing ``text`` would do, without writing anything."""
    export = parse_export(text)
    matches = match_materials(export.material_names)
    existing = _existing(db_path, user_id, export.recipes)
    used = {name: 0 for name in export.material_names}
    for recipe in export.recipes:
        for material in recipe.materials:
            used[material.name] += 1
    return {
        "recipes": [_recipe_dict(r, existing.get(r.row)) for r in export.recipes],
        "materials": [
            _match_dict(matches[name], used[name]) for name in export.material_names
        ],
        "unmatched": [name for name in export.material_names if not matches[name].key],
        "ignored_columns": export.ignored_columns,
    }


def written_names(export: ExportFile, mapping: Dict[str, str]) -> Dict[str, str]:
    """How each export material name will be written in recipes.

    ``mapping`` maps export names to material keys or names chosen by the
    user; names left out (or mapped to "") keep the export's spelling.
    """
    matches = match_materials(export.material_names)
    written = {}
    for name in export.material_names:
        choice = str(mapping.get(name) or "").strip()
        key = resolve_material_key(choice) if choice else None
        if choice and key is None:
            raise RecipeImportError(
                f'"{name}" is mapped to an unknown material: {choice}'
            )
        if key is None or key == matches[name].key:
            written[name] = name
        else:
            written[name] = get_material(key).name
    return written


def _clean_cone(cone) -> Optional[str]:
    text = re.sub(r"^cone[_ ]?", "", str(cone or "").strip(), flags=re.I)
    if not text:
        return None
    if not _CONE.fullmatch(text):
        raise RecipeImportError(f"Not a cone: {cone}")
    return text


def _unique_id(name: str, taken: set) -> str:
    base = _slugify(name) or "glaze"
    candidate, suffix = base, 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate


def _insert(conn, recipe: ExportRecipe, glaze_id: str, text: str, cone, user_id):
    original = [
        {"name": m.name, "amount": m.amount, "addition": m.addition}
        for m in recipe.materials
    ]
    note = f"{VERSION_NOTE} ({recipe.code})" if recipe.code else VERSION_NOTE
    conn.execute(
        "INSERT INTO glazes (id, name, recipe, notes, cone, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            glaze_id,
            recipe.name[:MAX_NAME_LENGTH],
            text,
            notes_for(recipe),
            cone,
            user_id,
        ),
    )
    conn.execute(
        "INSERT INTO recipe_versions (glaze_id, recipe, note, cone) VALUES (?, ?, ?, ?)",
        (glaze_id, text, note, cone),
    )
    conn.execute(
        "INSERT INTO glaze_imports (glaze_id, source, source_code, source_name, "
        "source_date, original) VALUES (?, ?, ?, ?, ?, ?)",
        (
            glaze_id,
            SOURCE,
            recipe.code or None,
            recipe.name,
            recipe.date or None,
            json.dumps(original),
        ),
    )


def import_recipes(
    db_path: str,
    user_id: Optional[str],
    text: str,
    rows: Iterable[int],
    mapping: Optional[Dict[str, str]] = None,
    cone=None,
) -> dict:
    """Create a glaze for each chosen recipe (by row) in one transaction."""
    export = parse_export(text)
    chosen = {int(row) for row in rows}
    selected = [r for r in export.recipes if r.row in chosen]
    if not selected:
        raise RecipeImportError("Choose at least one recipe to import.")
    if any(not r.materials for r in selected):
        raise RecipeImportError("A recipe with no materials can't be imported.")
    written = written_names(export, mapping or {})
    cone = _clean_cone(cone)
    imported = []
    conn = connect_db(db_path)
    try:
        with conn:
            taken = {row["id"] for row in conn.execute("SELECT id FROM glazes")}
            for recipe in selected:
                glaze_id = _unique_id(recipe.name, taken)
                text_recipe = recipe_string(recipe, written)
                _insert(conn, recipe, glaze_id, text_recipe, cone, user_id)
                missing = sorted(
                    {
                        written[m.name]
                        for m in recipe.materials
                        if match_material_key(written[m.name])[0] is None
                    }
                )
                imported.append(
                    {
                        "id": glaze_id,
                        "name": recipe.name[:MAX_NAME_LENGTH],
                        "code": recipe.code,
                        "recipe": text_recipe,
                        "missing": missing,
                    }
                )
    finally:
        conn.close()
    return {"imported": imported}
