"""Material database with oxide compositions and molecular weights for ceramic glaze chemistry."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .data_loader import load_material_data, load_oxide_data, load_thermal_expansion


@dataclass
class Material:
    """A ceramic raw material with its oxide composition."""

    name: str
    aliases: List[str] = field(default_factory=list)
    oxides: Dict[str, float] = field(default_factory=dict)  # oxide_name -> percentage
    loi: float = 0.0  # loss on ignition percentage
    category: str = "other"
    # Where the analysis came from: {"type": "supplier" | "theoretical" |
    # "unverified" | "custom" | "lot", ...}; see materials.json
    source: Dict = field(default_factory=dict)


# Hardcoded fallback molecular weights (g/mol) — used when ceramics-foundation data unavailable
_HARDCODED_OXIDE_MW: Dict[str, float] = {
    "SiO2": 60.084,
    "Al2O3": 101.961,
    "K2O": 94.196,
    "Na2O": 61.979,
    "CaO": 56.077,
    "MgO": 40.304,
    "Fe2O3": 159.688,
    "FeO": 71.844,
    "CuO": 79.545,
    "CoO": 74.933,
    "MnO": 70.937,
    "TiO2": 79.866,
    "ZnO": 81.379,
    "BaO": 153.326,
    "SrO": 103.619,
    "Li2O": 29.881,
    "B2O3": 69.620,
    "SnO2": 150.709,
    "ZrO2": 123.218,
    "Cr2O3": 151.990,
    "P2O5": 141.944,
    "NiO": 74.692,
    "V2O5": 181.88,
    "Nb2O5": 265.81,
}

# Load from ceramics-foundation if available, otherwise use hardcoded values
_oxide_data = load_oxide_data()
if _oxide_data:
    OXIDE_MOLECULAR_WEIGHTS: Dict[str, float] = {
        name: props["mw"] for name, props in _oxide_data.items() if "mw" in props
    }
    # Ensure all expected oxides are present (merge with fallback)
    for oxide, mw in _HARDCODED_OXIDE_MW.items():
        if oxide not in OXIDE_MOLECULAR_WEIGHTS:
            OXIDE_MOLECULAR_WEIGHTS[oxide] = mw
else:
    OXIDE_MOLECULAR_WEIGHTS = dict(_HARDCODED_OXIDE_MW)

# Oxides classified as fluxes (used for UMF normalization)
FLUX_OXIDES = {"K2O", "Na2O", "CaO", "MgO", "ZnO", "BaO", "SrO", "Li2O", "FeO"}

# Thermal expansion coefficients (Appen molar coefficients, x10^-6/K)
# Loaded from ceramics-foundation/data/thermal-expansion.json if available.
# Falls back to simplified relative values if data not found.
_HARDCODED_TE: Dict[str, float] = {
    "Na2O": 1.0,
    "K2O": 1.2,
    "CaO": 0.5,
    "MgO": 0.1,
    "BaO": 0.4,
    "ZnO": 0.2,
    "Li2O": 0.9,
    "SrO": 0.4,
    "FeO": 0.3,
    "Fe2O3": 0.2,
    "Al2O3": -0.2,
    "SiO2": -0.5,
    "B2O3": -0.1,
    "TiO2": 0.0,
    "ZrO2": 0.0,
}

_te_data = load_thermal_expansion()
if _te_data:
    THERMAL_EXPANSION_COEFFICIENTS: Dict[str, float] = {
        name: props["value"]
        for name, props in _te_data.items()
        if isinstance(props, dict) and "value" in props
    }
    # Ensure all expected oxides are present (merge with fallback)
    for oxide, val in _HARDCODED_TE.items():
        if oxide not in THERMAL_EXPANSION_COEFFICIENTS:
            THERMAL_EXPANSION_COEFFICIENTS[oxide] = val
else:
    THERMAL_EXPANSION_COEFFICIENTS = dict(_HARDCODED_TE)

# ---------------------------------------------------------------------------
# Material library
#
# The library comes from ceramics-foundation/data/materials.json, where every
# analysis records its source. A studio can add its own materials and mark a
# lot analysis as current; the web app passes those in with
# set_studio_materials(), and every lookup below sees them. Lookups read one
# immutable table snapshot per call, so swapping it is safe while requests run.
# ---------------------------------------------------------------------------


def _load_library() -> Dict[str, Material]:
    data = load_material_data()
    if not data:
        raise RuntimeError(
            "Material library not found: expected ceramics-foundation/data/materials.json"
        )
    return {
        key: Material(
            name=entry["name"],
            aliases=list(entry.get("aliases", [])),
            oxides=dict(entry.get("oxides", {})),
            loi=float(entry.get("loi", 0.0)),
            category=entry.get("category", "other"),
            source=dict(entry.get("source", {})),
        )
        for key, entry in data.items()
    }


# The published library, keyed by canonical (lowercase) name. Never modified.
LIBRARY: Dict[str, Material] = _load_library()


def _compact(text: str) -> str:
    """A name with spaces and punctuation removed: 'OM #4' and 'OM4' -> 'om4'."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


class _Tables:
    """An immutable snapshot of the effective materials and their aliases."""

    def __init__(self, materials: Dict[str, Material]):
        self.materials = materials
        self.aliases: Dict[str, str] = {}
        # Names and aliases with spaces and punctuation removed; a compact form
        # shared by two materials is left out rather than guessed.
        self.compact: Dict[str, str] = {}
        shared = set()
        for canonical, material in materials.items():
            for alias in material.aliases:
                self.aliases.setdefault(alias.lower(), canonical)
            for label in (canonical, *material.aliases):
                key = _compact(label)
                if key and self.compact.setdefault(key, canonical) != canonical:
                    shared.add(key)
        for key in shared:
            del self.compact[key]


_tables = _Tables(dict(LIBRARY))


def set_studio_materials(
    custom: Optional[List[Material]] = None,
    active_lots: Optional[Dict[str, Material]] = None,
) -> None:
    """Replace the studio's own materials and current lot analyses.

    ``custom`` materials are added to the library (their names must not clash
    with it). ``active_lots`` maps a canonical material name to the analysis
    that should be used for it instead of the standard one.
    """
    global _tables
    effective = dict(LIBRARY)
    for material in custom or []:
        effective[normalize_material_name(material.name)] = material
    for key, lot in (active_lots or {}).items():
        if key in effective:
            effective[key] = lot
    _tables = _Tables(effective)


def normalize_material_name(name: str) -> str:
    """Normalize a material name to its canonical form."""
    if not name:
        return name
    return name.strip().lower()


def resolve_material_key(name: str) -> Optional[str]:
    """Return the canonical key for a material name or alias, or None."""
    if not name:
        return None
    tables = _tables
    normalized = normalize_material_name(name)
    if normalized in tables.materials:
        return normalized
    if normalized in tables.aliases:
        return tables.aliases[normalized]
    # Fuzzy: try removing common suffixes
    for suffix in [" oxide", " carbonate", " clay", " feldspar", " carb"]:
        stripped = normalized.replace(suffix, "")
        if stripped in tables.materials:
            return stripped
        if stripped in tables.aliases:
            return tables.aliases[stripped]
    # Spelling variants: "OM#4" for "OM4", "Ferro Frit #3134", "F 12"
    return tables.compact.get(_compact(normalized))


def get_material(name: str) -> Optional[Material]:
    """Look up a material by name or alias. Returns None if not found."""
    tables = _tables
    key = resolve_material_key(name)
    return tables.materials.get(key) if key else None


def get_all_materials() -> Dict[str, Material]:
    """Return all effective materials keyed by canonical name."""
    return dict(_tables.materials)
