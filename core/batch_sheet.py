"""Batch sheets: a recipe scaled to a batch size, for weighing out.

Unlike the chemistry, a batch sheet keeps every material as the recipe writes
it, including ones the library doesn't know (a stain, a local clay): they
still have to be weighed. The base is scaled to the batch size and additions
by the same factor, so a 1000 g batch of a recipe with 15.7 of additions
weighs 1157 g in all. The running total is for weighing everything into one
bucket on a scale that isn't zeroed between materials.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from core.chemistry.materials import get_material
from core.chemistry.parser import match_material_key

BASIS_BASE = "base"  # the base materials weigh `size`; additions go on top
BASIS_TOTAL = "total"  # everything together weighs `size`
MAX_SIZE_GRAMS = 1_000_000
_LINE = re.compile(r"^(.+?)\s+([\d.]+)\s*%?\s*$")


class BatchSheetError(ValueError):
    """The recipe or batch size can't be made into a batch sheet."""


@dataclass
class RecipeLine:
    name: str
    amount: float
    addition: bool = False


def split_recipe(recipe: str) -> List[RecipeLine]:
    """Read a recipe string into lines, keeping names as written.

    Same format as the calculator: "Name amount" parts separated by commas,
    semicolons or new lines, a leading "+" for an addition, and text without
    a number (a title) skipped.
    """
    lines = []
    for part in re.split(r"[,\n;]", recipe or ""):
        part = part.strip()
        addition = part.startswith("+")
        if addition:
            part = part[1:].strip()
        if not part or not re.search(r"\d", part):
            continue
        match = _LINE.match(part)
        try:
            amount = float(match.group(2)) if match else None
        except ValueError:
            amount = None
        if amount is None:
            raise BatchSheetError(f'Couldn\'t read "{part}" as a material and amount.')
        if amount > 0:
            lines.append(RecipeLine(" ".join(match.group(1).split()), amount, addition))
    return lines


def _lot_of(name: str) -> Optional[str]:
    """The lot in use for a material, if the studio recorded one."""
    key, _partial = match_material_key(name)
    material = get_material(key) if key else None
    source = material.source if material else {}
    return source.get("lot") if source.get("type") == "lot" else None


def batch_sheet(recipe: str, size: float, basis: str = BASIS_BASE) -> dict:
    """Scale ``recipe`` so the base (or the whole batch) weighs ``size`` grams."""
    if basis not in (BASIS_BASE, BASIS_TOTAL):
        raise BatchSheetError(f"Unknown basis: {basis}")
    if not isinstance(size, (int, float)) or not 0 < size <= MAX_SIZE_GRAMS:
        raise BatchSheetError("The batch size must be more than 0 and at most 1000 kg.")
    lines = split_recipe(recipe)
    base = [line for line in lines if not line.addition]
    additions = [line for line in lines if line.addition]
    base_percent = sum(line.amount for line in base)
    additions_percent = sum(line.amount for line in additions)
    if not base_percent:
        raise BatchSheetError("The recipe has no base materials to weigh.")
    whole = base_percent + additions_percent
    factor = size / (base_percent if basis == BASIS_BASE else whole)

    rows, running = [], 0.0
    for line in base + additions:
        grams = round(line.amount * factor, 1)
        running = round(running + grams, 1)
        key, _partial = match_material_key(line.name)
        rows.append(
            {
                "name": line.name,
                "amount": line.amount,
                "addition": line.addition,
                "grams": grams,
                "running": running,
                "known": key is not None,
                "lot": _lot_of(line.name),
            }
        )
    base_grams = round(sum(r["grams"] for r in rows if not r["addition"]), 1)
    return {
        "basis": basis,
        "size": size,
        "base_percent": round(base_percent, 4),
        "additions_percent": round(additions_percent, 4),
        "base_grams": base_grams,
        "additions_grams": round(running - base_grams, 1),
        "total_grams": running,
        "rows": rows,
    }
