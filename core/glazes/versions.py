"""Saved recipe versions for glazes.

Each save from the recipe editor appends a row to ``recipe_versions`` and
makes that recipe the glaze's current one, in a single transaction. The first
save of a glaze that already had a recipe records the earlier recipe first,
so editing never loses the original.
"""

from typing import Optional

from core.db import connect_db

ORIGINAL_NOTE = "Recipe before first edit"

_COLUMNS = "id, glaze_id, recipe, note, cone, created_at"


def list_versions(db_path: str, glaze_id: str) -> list[dict]:
    """Return a glaze's saved versions, newest first."""
    conn = connect_db(db_path)
    try:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM recipe_versions WHERE glaze_id = ? ORDER BY id DESC",
            (glaze_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_version(
    db_path: str,
    glaze_id: str,
    recipe: str,
    previous_recipe: Optional[str] = None,
    note: Optional[str] = None,
    cone: Optional[str] = None,
) -> dict:
    """Save ``recipe`` as the glaze's newest version and current recipe.

    The caller must already have checked that the glaze exists and is
    visible to the requester. ``previous_recipe`` is the glaze's recipe before
    this save; it is recorded as the first version when none exist yet.
    """
    conn = connect_db(db_path)
    try:
        with conn:
            has_versions = conn.execute(
                "SELECT 1 FROM recipe_versions WHERE glaze_id = ? LIMIT 1",
                (glaze_id,),
            ).fetchone()
            previous = (previous_recipe or "").strip()
            if not has_versions and previous and previous != recipe:
                conn.execute(
                    "INSERT INTO recipe_versions (glaze_id, recipe, note) VALUES (?, ?, ?)",
                    (glaze_id, previous, ORIGINAL_NOTE),
                )
            cursor = conn.execute(
                "INSERT INTO recipe_versions (glaze_id, recipe, note, cone) VALUES (?, ?, ?, ?)",
                (glaze_id, recipe, note, cone),
            )
            if cone:
                conn.execute(
                    "UPDATE glazes SET recipe = ?, cone = ? WHERE id = ?",
                    (recipe, cone, glaze_id),
                )
            else:
                conn.execute(
                    "UPDATE glazes SET recipe = ? WHERE id = ?", (recipe, glaze_id)
                )
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM recipe_versions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return dict(row)
    finally:
        conn.close()
