"""Theoretical analyses of pure compounds from their chemical formulas.

A pure compound such as whiting (CaCO3) needs no supplier data sheet: its
analysis follows from atomic weights. ``theoretical_analysis("CaCO3",
{"CaO": 1})`` gives CaO 56.03 % with the rest (CO2) as LOI.
"""

import re
from typing import Dict, Tuple

# IUPAC conventional atomic weights (g/mol)
ATOMIC_WEIGHTS: Dict[str, float] = {
    "H": 1.008,
    "Li": 6.94,
    "B": 10.81,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "Na": 22.990,
    "Mg": 24.305,
    "Al": 26.982,
    "Si": 28.085,
    "P": 30.974,
    "S": 32.06,
    "K": 39.098,
    "Ca": 40.078,
    "Ti": 47.867,
    "Cr": 51.996,
    "Mn": 54.938,
    "Fe": 55.845,
    "Co": 58.933,
    "Ni": 58.693,
    "Cu": 63.546,
    "Zn": 65.38,
    "Sr": 87.62,
    "Zr": 91.224,
    "Sn": 118.71,
    "Ba": 137.327,
}

# Elements that leave the glaze on firing (as H2O, CO2, O2, ...)
VOLATILE_ELEMENTS = {"H", "C", "N", "O", "F", "S"}

_TOKEN = re.compile(r"([A-Z][a-z]?|\(|\)|\d+(?:\.\d+)?)")


def element_counts(formula: str) -> Dict[str, float]:
    """Count atoms in a formula such as "Cu2(OH)2CO3" or "Na2B4O7·10H2O"."""
    totals: Dict[str, float] = {}
    for part in re.split(r"[·*]", formula.replace(" ", "")):
        multiplier = 1.0
        match = re.match(r"^(\d+(?:\.\d+)?)(.*)$", part)
        if match:
            multiplier, part = float(match.group(1)), match.group(2)
        for element, count in _parse_group(part).items():
            totals[element] = totals.get(element, 0.0) + count * multiplier
    return totals


def _parse_group(formula: str) -> Dict[str, float]:
    tokens = _TOKEN.findall(formula)
    if "".join(tokens) != formula:
        raise ValueError(f"Cannot parse formula: {formula!r}")
    pos = 0

    def parse() -> Dict[str, float]:
        nonlocal pos
        counts: Dict[str, float] = {}
        while pos < len(tokens) and tokens[pos] != ")":
            token = tokens[pos]
            pos += 1
            if token == "(":
                inner = parse()
                if pos >= len(tokens):
                    raise ValueError(f"Unbalanced parentheses in {formula!r}")
                pos += 1  # the closing ")"
            elif token in ATOMIC_WEIGHTS:
                inner = {token: 1.0}
            else:
                raise ValueError(f"Unexpected {token!r} in {formula!r}")
            multiplier = 1.0
            if pos < len(tokens) and tokens[pos][0].isdigit():
                multiplier = float(tokens[pos])
                pos += 1
            for element, n in inner.items():
                counts[element] = counts.get(element, 0.0) + n * multiplier
        return counts

    result = parse()
    if pos != len(tokens):
        raise ValueError(f"Unbalanced parentheses in {formula!r}")
    return result


def formula_weight(formula: str) -> float:
    """Molar mass of a formula in g/mol."""
    return sum(ATOMIC_WEIGHTS[el] * n for el, n in element_counts(formula).items())


def theoretical_analysis(
    formula: str, yields: Dict[str, float]
) -> Tuple[Dict[str, float], float]:
    """Return (oxide weight percents, LOI) for one formula unit of a compound.

    ``yields`` gives the moles of each oxide one formula unit leaves after
    firing, e.g. dolomite "CaMg(CO3)2" -> {"CaO": 1, "MgO": 1}. Every
    non-volatile element must be fully accounted for by the oxides.
    """
    source = element_counts(formula)
    produced: Dict[str, float] = {}
    for oxide, n in yields.items():
        for element, count in element_counts(oxide).items():
            produced[element] = produced.get(element, 0.0) + count * n
    for element in set(source) | set(produced):
        if element in VOLATILE_ELEMENTS:
            continue
        if abs(source.get(element, 0.0) - produced.get(element, 0.0)) > 1e-9:
            raise ValueError(f"{formula} -> {yields}: {element} does not balance")

    total = formula_weight(formula)
    oxides = {
        ox: round(n * formula_weight(ox) / total * 100, 2) for ox, n in yields.items()
    }
    loi = round(max(0.0, 100.0 - sum(oxides.values())), 2)
    return oxides, loi
