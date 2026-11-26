"""Read recipe exports from DigitalFire Insight-Live.

Insight-Live's recipe list exports a CSV with one row per recipe::

    Code,Name,Description,Date,Batch,Location,<material columns...>,Batch total (g),Comments

There is one column per material used by any recipe in the export, holding
that recipe's amount (blank when the recipe doesn't use it). Columns appear in
the order materials first turn up across the recipes, oldest recipe first, so
only a one-recipe export keeps a recipe's own order. The export does not mark
additions or record a firing cone. Additions are worked out from the amounts
(the base adds up to 100) and, when several splits add up, the material types.

This module only reads and matches; ``core.glazes.importer`` writes glazes.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.chemistry.materials import get_material
from core.chemistry.parser import match_material_key

MAX_TEXT_LENGTH = 5_000_000
MAX_RECIPES = 5000

# Fixed (non-material) columns, matched case-insensitively.
METADATA_COLUMNS = {
    "code": "code",
    "name": "name",
    "description": "description",
    "date": "date",
    "batch": "batch",
    "location": "location",
    "batch total (g)": "batch_total",
    "comments": "comments",
}

TOLERANCE = 0.1  # how close to 100 a base total must be (matches the parser)
MAX_SEARCH_STEPS = 200_000  # per recipe, for the sets of materials adding to 100

ADDITIONS_NONE = "none"  # every material is part of the base
ADDITIONS_FOUND = "found"  # the amounts (and order) settle which are additions
ADDITIONS_GUESSED = "guessed"  # several splits add up; picked by material type
ADDITIONS_UNCLEAR = "unclear"  # imported as all base; check in the editor

# How a material usually appears in a recipe: in the base, or as an addition.
KIND_BASE = "base"
KIND_ADDITION = "addition"
BASE_CATEGORIES = {"feldspar", "silica", "flux", "frit", "clay"}
ADDITION_CATEGORIES = {"colorant", "opacifier"}
_EITHER = re.compile(r"bentonite|macaloid|veegum", re.I)  # suspenders: base or added
_BASE_WORDS = re.compile(
    r"kaolin|clay|feldspar|\bspar\b|frit|silica|flint|nepheline|whiting|"
    r"wollastonite|talc|dolomite",
    re.I,
)
_ADDITION_WORDS = re.compile(r"\bstain\b|pigment", re.I)


class ImportFormatError(ValueError):
    """The file isn't an Insight-Live recipe export this module can read."""


@dataclass
class ExportMaterial:
    name: str
    amount: float
    addition: bool = False


@dataclass
class ExportRecipe:
    row: int  # line number of the record in the file, header = 1
    code: str
    name: str
    description: str = ""
    date: str = ""
    location: str = ""
    comments: str = ""
    materials: List[ExportMaterial] = field(default_factory=list)
    additions: str = ADDITIONS_NONE
    warnings: List[str] = field(default_factory=list)

    @property
    def base_total(self) -> float:
        return round(sum(m.amount for m in self.materials if not m.addition), 4)

    @property
    def additions_total(self) -> float:
        return round(sum(m.amount for m in self.materials if m.addition), 4)


@dataclass
class ExportFile:
    recipes: List[ExportRecipe]
    material_names: List[str]  # material columns, in file order
    ignored_columns: List[str] = field(default_factory=list)


@dataclass
class MaterialMatch:
    name: str  # as written in the export
    key: Optional[str]  # our material key, None when unmatched
    partial: bool = False  # only a leading part of the name matched

    @property
    def material(self):
        return get_material(self.key) if self.key else None


def decode(data: bytes) -> str:
    """Decode an uploaded export: UTF-8 (with or without BOM), else Windows-1252."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _number(value: str) -> Optional[float]:
    """Parse an amount cell; None when it isn't a plain number."""
    try:
        number = float(value.replace(" ", ""))
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def clean_text(value: str) -> str:
    """Tidy a free-text cell: newlines, surrounding space, one wrapping quote pair.

    Insight-Live wraps comments in an extra pair of double quotes inside the
    CSV field, e.g. ``"Duplicated from T100.\\r\\n"``.
    """
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        text = text[1:-1].strip()
    return text


def _read_rows(text: str) -> List[List[str]]:
    if len(text) > MAX_TEXT_LENGTH:
        raise ImportFormatError("The file is too large to import (5 MB at most).")
    try:
        return list(csv.reader(io.StringIO(text.lstrip("﻿"), newline="")))
    except csv.Error as error:
        raise ImportFormatError(f"The file isn't a readable CSV: {error}") from error


def _columns(header: List[str], rows: List[List[str]]):
    """Split the header into metadata, material and ignored columns."""
    metadata: Dict[str, int] = {}
    candidates: List[int] = []
    for index, title in enumerate(header):
        field_name = METADATA_COLUMNS.get(title.strip().lower())
        if field_name and field_name not in metadata:
            metadata[field_name] = index
        elif title.strip():
            candidates.append(index)
    materials, ignored = [], []
    for index in candidates:
        values = [row[index].strip() for row in rows if index < len(row)]
        if all(_number(v) is not None for v in values if v):
            materials.append(index)
        else:
            ignored.append(index)
    return metadata, materials, ignored


def material_kind(name: str) -> Optional[str]:
    """KIND_BASE, KIND_ADDITION, or None when a material is commonly either.

    Uses the matched material's category; for a name that doesn't match,
    words in the name ("kaolin", "stain").
    """
    if _EITHER.search(name):
        return None
    key, _partial = match_material_key(name)
    material = get_material(key) if key else None
    if material is not None:
        if material.category in ADDITION_CATEGORIES:
            return KIND_ADDITION
        return KIND_BASE if material.category in BASE_CATEGORIES else None
    if _ADDITION_WORDS.search(name):
        return KIND_ADDITION
    return KIND_BASE if _BASE_WORDS.search(name) else None


class _SearchLimit(Exception):
    pass


def _bases(amounts: List[float]) -> Optional[List[frozenset]]:
    """Every set of materials (by index) whose amounts add up to 100.

    None when there are too many small amounts to try every combination.
    """
    order = sorted(range(len(amounts)), key=lambda i: -amounts[i])
    left = [0.0] * (len(order) + 1)  # total of the amounts not yet considered
    for pos in range(len(order) - 1, -1, -1):
        left[pos] = left[pos + 1] + amounts[order[pos]]
    found: List[frozenset] = []
    chosen: List[int] = []
    steps = 0

    def walk(pos: int, total: float) -> None:
        nonlocal steps
        steps += 1
        if steps > MAX_SEARCH_STEPS:
            raise _SearchLimit
        if total > 100 + TOLERANCE or total + left[pos] < 100 - TOLERANCE:
            return
        if pos == len(order):
            found.append(frozenset(chosen))
            return
        chosen.append(order[pos])
        walk(pos + 1, total + amounts[order[pos]])
        chosen.pop()
        walk(pos + 1, total)

    try:
        walk(0, 0.0)
    except _SearchLimit:
        return None
    return found


def split_additions(
    materials: List[ExportMaterial],
    kinds: Optional[List[Optional[str]]] = None,
    in_order: bool = True,
) -> str:
    """Mark which materials are additions; returns one of the ADDITIONS_* values.

    The base is a set of materials adding up to 100. When several sets do,
    the one that best fits ``kinds`` (see ``material_kind``) wins, then the
    one that leads the file order. ``in_order`` says the materials are in the
    recipe's own order (a one-recipe export), where a leading set is decisive.
    """
    if sum(m.amount for m in materials) <= 100 + TOLERANCE:
        return ADDITIONS_NONE
    kinds = kinds or [None] * len(materials)
    bases = _bases([m.amount for m in materials])
    if not bases:
        return ADDITIONS_UNCLEAR

    def misfits(base: frozenset) -> int:
        return sum(
            1
            for i, kind in enumerate(kinds)
            if (kind == KIND_ADDITION and i in base)
            or (kind == KIND_BASE and i not in base)
        )

    def rank(base: frozenset):
        return (misfits(base), base != frozenset(range(len(base))))

    ranked = sorted(bases, key=rank)
    best = ranked[0]
    if len(ranked) > 1 and rank(ranked[1]) == rank(best):
        return ADDITIONS_UNCLEAR
    for index, material in enumerate(materials):
        material.addition = index not in best
    leads = not rank(best)[1]
    settled = (
        len(ranked) == 1
        or (leads and in_order)
        or (leads and misfits(best) == 0 and misfits(ranked[1]) > 0)
    )
    return ADDITIONS_FOUND if settled else ADDITIONS_GUESSED


def _cell(row: List[str], index: Optional[int]) -> str:
    return row[index] if index is not None and index < len(row) else ""


def _recipe(row_number, row, header, metadata, material_columns, in_order):
    recipe = ExportRecipe(
        row=row_number,
        code=_cell(row, metadata.get("code")).strip(),
        name=" ".join(_cell(row, metadata.get("name")).split()),
        description=clean_text(_cell(row, metadata.get("description"))),
        date=_cell(row, metadata.get("date")).strip(),
        location=clean_text(_cell(row, metadata.get("location"))),
        comments=clean_text(_cell(row, metadata.get("comments"))),
    )
    for index in material_columns:
        amount = _number(_cell(row, index).strip() or "0")
        if amount and amount > 0:
            name = " ".join(header[index].replace(",", " ").split())
            recipe.materials.append(ExportMaterial(name, amount))
    if not recipe.name:
        recipe.name = recipe.code or f"Insight-Live recipe (row {row_number})"
        recipe.warnings.append("The recipe has no name in the export.")
    if not recipe.materials:
        recipe.warnings.append("The recipe has no materials in the export.")
        return recipe
    kinds = [material_kind(m.name) for m in recipe.materials]
    recipe.additions = split_additions(recipe.materials, kinds, in_order)
    total = sum(m.amount for m in recipe.materials)
    if recipe.additions == ADDITIONS_GUESSED:
        recipe.warnings.append(
            "More than one set of these materials adds up to 100. The additions "
            "shown were picked by material type (colorants and opacifiers as "
            "additions); check them."
        )
    elif recipe.additions == ADDITIONS_UNCLEAR:
        recipe.warnings.append(
            f"The amounts add up to {total:g} and the additions couldn't be worked "
            "out from them, so every material is imported as part of the base; mark "
            "the additions in the recipe editor."
        )
    elif total < 100 - TOLERANCE:
        recipe.warnings.append(
            f"The amounts add up to {total:g}, not 100; calculations scale them to 100."
        )
    batch_total = _number(_cell(row, metadata.get("batch_total")).strip() or "x")
    if batch_total is not None and abs(batch_total - total) > TOLERANCE:
        recipe.warnings.append(
            f"The export's batch total is {batch_total:g} but the materials read add "
            f"up to {total:g}."
        )
    return recipe


def _record_lines(text: str) -> List[int]:
    """Line number where each CSV record starts (records may span lines)."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿"), newline=""))
    starts, line = [], 1
    for _ in reader:
        starts.append(line)
        line = reader.line_num + 1
    return starts


def parse_export(text: str) -> ExportFile:
    """Read an Insight-Live recipe CSV into recipes with materials and additions."""
    rows = _read_rows(text)
    while rows and not any(cell.strip() for cell in rows[0]):
        rows.pop(0)
    if not rows:
        raise ImportFormatError("The file is empty.")
    header = rows[0]
    starts = _record_lines(text)
    offset = len(starts) - len(rows)  # blank lines skipped before the header
    records = [
        (starts[offset + i], row)
        for i, row in enumerate(rows)
        if i > 0 and any(cell.strip() for cell in row)
    ]
    metadata, material_columns, ignored = _columns(header, [r for _, r in records])
    if "name" not in metadata:
        raise ImportFormatError(
            "This doesn't look like an Insight-Live recipe export: there is no "
            "Name column."
        )
    if not material_columns:
        raise ImportFormatError("The file has no material columns.")
    if len(records) > MAX_RECIPES:
        raise ImportFormatError(f"The file has more than {MAX_RECIPES} recipes.")
    recipes = [
        _recipe(number, row, header, metadata, material_columns, len(records) == 1)
        for number, row in records
    ]
    names = [" ".join(header[i].replace(",", " ").split()) for i in material_columns]
    return ExportFile(
        recipes=recipes,
        material_names=names,
        ignored_columns=[header[i].strip() for i in ignored],
    )


def match_materials(names: List[str]) -> Dict[str, MaterialMatch]:
    """Match export material names to our materials (library and studio)."""
    matches = {}
    for name in names:
        key, partial = match_material_key(name)
        matches[name] = MaterialMatch(name=name, key=key, partial=partial)
    return matches


def _amount(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def recipe_string(recipe: ExportRecipe, written: Dict[str, str]) -> str:
    """Build our recipe string, writing each export name as ``written[name]``.

    Additions get a leading "+" and follow the base materials.
    """
    base = [m for m in recipe.materials if not m.addition]
    additions = [m for m in recipe.materials if m.addition]
    parts = [f"{written.get(m.name, m.name)} {_amount(m.amount)}" for m in base]
    parts += [f"+{written.get(m.name, m.name)} {_amount(m.amount)}" for m in additions]
    return ", ".join(parts)


def notes_for(recipe: ExportRecipe) -> str:
    """Glaze notes carrying the export's code, date, description and comments."""
    origin = "Imported from Insight-Live"
    if recipe.code:
        origin += f" recipe {recipe.code}"
    if recipe.date:
        origin += f", dated {recipe.date}"
    parts = [origin + "."]
    parts += [text for text in (recipe.description, recipe.comments) if text]
    if recipe.location:
        parts.append(f"Location: {recipe.location}")
    return "\n\n".join(parts)
