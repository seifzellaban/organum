"""Organ stop profiles — extended harmonic recipes for realistic pipe sounds.

Each profile maps harmonic number → relative amplitude, with richer partial
content than the initial version for more realistic pipe character.
"""

from typing import TypeAlias

HarmonicProfile: TypeAlias = dict[int, float]

# ──────────────────────────────────────────────────────────────────────
# Stop definitions — richer harmonic content
# ──────────────────────────────────────────────────────────────────────

PRINCIPAL_8: HarmonicProfile = {
    1: 1.0,
    2: 0.60,
    3: 0.42,
    4: 0.28,
    5: 0.18,
    6: 0.12,
    7: 0.06,
    8: 0.08,
    9: 0.03,
    10: 0.04,
    12: 0.02,
}

FLUTE_8: HarmonicProfile = {
    1: 1.0,
    2: 0.06,
    3: 0.12,
    4: 0.02,
    5: 0.01,
    6: 0.005,
}

GEDACKT_8: HarmonicProfile = {
    1: 1.0,
    3: 0.25,
    5: 0.10,
    7: 0.04,
    9: 0.015,
    11: 0.005,
}

OCTAVE_4: HarmonicProfile = {
    2: 1.0,
    4: 0.50,
    6: 0.32,
    8: 0.18,
    10: 0.10,
    12: 0.06,
    14: 0.03,
}

REED_8: HarmonicProfile = {
    1: 1.0,
    2: 0.90,
    3: 0.75,
    4: 0.65,
    5: 0.55,
    6: 0.45,
    7: 0.38,
    8: 0.30,
    9: 0.24,
    10: 0.20,
    11: 0.16,
    12: 0.12,
    13: 0.09,
    14: 0.07,
    15: 0.05,
    16: 0.03,
}

MIXTURE: HarmonicProfile = {
    4: 0.45,
    5: 0.60,
    6: 0.75,
    8: 1.0,
    10: 0.65,
    12: 0.35,
    15: 0.15,
    16: 0.08,
}

BOURDON_16: HarmonicProfile = {
    1: 1.0,
    2: 0.03,
    3: 0.15,
    4: 0.01,
    5: 0.06,
    7: 0.02,
}

VOX_CELESTE: HarmonicProfile = {
    1: 1.0,
    2: 0.35,
    3: 0.20,
    4: 0.12,
    5: 0.08,
    6: 0.05,
    8: 0.03,
}

# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

STOP_REGISTRY: dict[str, HarmonicProfile] = {
    "Principal 8'": PRINCIPAL_8,
    "Flute 8'": FLUTE_8,
    "Gedackt 8'": GEDACKT_8,
    "Octave 4'": OCTAVE_4,
    "Reed 8'": REED_8,
    "Mixture": MIXTURE,
    "Bourdon 16'": BOURDON_16,
    "Vox Celeste": VOX_CELESTE,
}

# Drawbar harmonic numbers (Hammond convention)
DRAWBAR_HARMONICS = [0.5, 1, 1.5, 2, 3, 4, 5, 6, 8]

# Drawbar labels
DRAWBAR_LABELS = ["16'", "8'", "5⅓'", "4'", "2⅔'", "2'", "1⅗'", "1⅓'", "1'"]
