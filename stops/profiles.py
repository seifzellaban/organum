"""Organ stop profiles — harmonic recipes with pipe-type waveform selection.

Each profile maps harmonic number → relative amplitude, and includes a
preferred waveform to use for realistic pipe character. Different pipe
families (principal, flute, reed, string) have fundamentally different
waveshapes, not just different harmonic balances.
"""

from typing import TypeAlias
from dataclasses import dataclass

HarmonicProfile: TypeAlias = dict[int, float]


@dataclass
class StopDefinition:
    """Full stop definition with harmonics, waveform, and voicing parameters."""
    harmonics: HarmonicProfile
    waveform: str = "sine"          # Oscillator waveform name
    chorus_detune: float = 0.8      # Hz — chorus detuning amount
    vibrato_depth: float = 0.6      # Hz — vibrato/tremulant depth
    vibrato_rate: float = 5.8       # Hz — vibrato/tremulant rate
    chiff_amount: float = 0.015     # Attack chiff noise intensity
    chiff_ms: float = 15.0          # Chiff duration in ms
    wind_noise: float = 0.004       # Continuous wind noise level
    attack_ms: float = 35.0         # Envelope attack time
    release_ms: float = 350.0       # Envelope release time


# ──────────────────────────────────────────────────────────────────────
# Stop definitions — with waveform and voicing character
# ──────────────────────────────────────────────────────────────────────

PRINCIPAL_8_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.60, 3: 0.42, 4: 0.28,
        5: 0.18, 6: 0.12, 7: 0.06, 8: 0.08,
        9: 0.03, 10: 0.04, 12: 0.02,
    },
    waveform="principal",
    chorus_detune=0.7,
    vibrato_depth=0.5,
    chiff_amount=0.015,
    chiff_ms=12.0,
    wind_noise=0.004,
    attack_ms=25.0,
    release_ms=280.0,
)

FLUTE_8_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.06, 3: 0.12, 4: 0.02,
        5: 0.01, 6: 0.005,
    },
    waveform="flute",
    chorus_detune=0.4,
    vibrato_depth=0.3,
    chiff_amount=0.02,
    chiff_ms=20.0,
    wind_noise=0.006,
    attack_ms=30.0,
    release_ms=300.0,
)

GEDACKT_8_DEF = StopDefinition(
    harmonics={
        1: 1.0, 3: 0.25, 5: 0.10, 7: 0.04,
        9: 0.015, 11: 0.005,
    },
    waveform="flute",
    chorus_detune=0.5,
    vibrato_depth=0.35,
    chiff_amount=0.018,
    chiff_ms=18.0,
    wind_noise=0.005,
    attack_ms=28.0,
    release_ms=300.0,
)

OCTAVE_4_DEF = StopDefinition(
    harmonics={
        2: 1.0, 4: 0.50, 6: 0.32, 8: 0.18,
        10: 0.10, 12: 0.06, 14: 0.03,
    },
    waveform="principal",
    chorus_detune=0.9,
    vibrato_depth=0.6,
    chiff_amount=0.009, # Reduced from 0.012
    chiff_ms=10.0,
    wind_noise=0.003,
    attack_ms=25.0,     # Increased from 18.0
    release_ms=280.0,   # Increased from 250.0
)

REED_8_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.90, 3: 0.75, 4: 0.65,
        5: 0.55, 6: 0.45, 7: 0.38, 8: 0.30,
        9: 0.24, 10: 0.20, 11: 0.16, 12: 0.12,
        13: 0.09, 14: 0.07, 15: 0.05, 16: 0.03,
    },
    waveform="reed",
    chorus_detune=1.2,
    vibrato_depth=0.8,
    vibrato_rate=6.2,
    chiff_amount=0.010,
    chiff_ms=8.0,
    wind_noise=0.003,
    attack_ms=15.0,
    release_ms=180.0,
)

MIXTURE_DEF = StopDefinition(
    harmonics={
        4: 0.45, 5: 0.60, 6: 0.75, 8: 1.0,
        10: 0.65, 12: 0.35, 15: 0.15, 16: 0.08,
    },
    waveform="principal",
    chorus_detune=1.0,
    vibrato_depth=0.7,
    chiff_amount=0.012,
    chiff_ms=10.0,
    wind_noise=0.003,
    attack_ms=18.0,
    release_ms=250.0,
)

BOURDON_16_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.03, 3: 0.15, 4: 0.01,
        5: 0.06, 7: 0.02,
    },
    waveform="flute",
    chorus_detune=0.3,
    vibrato_depth=0.25,
    chiff_amount=0.025,
    chiff_ms=28.0,
    wind_noise=0.007,
    attack_ms=40.0,
    release_ms=400.0,
)

VOX_CELESTE_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.35, 3: 0.20, 4: 0.12,
        5: 0.08, 6: 0.05, 8: 0.03,
    },
    waveform="string",
    chorus_detune=1.8,
    vibrato_depth=0.9,
    vibrato_rate=5.2,
    chiff_amount=0.008,
    chiff_ms=10.0,
    wind_noise=0.003,
    attack_ms=35.0,
    release_ms=380.0,
)

# ──────────────────────────────────────────────────────────────────────
# Registries
# ──────────────────────────────────────────────────────────────────────

# Full stop definitions (new)
STOP_DEFS: dict[str, StopDefinition] = {
    "Principal 8'": PRINCIPAL_8_DEF,
    "Flute 8'": FLUTE_8_DEF,
    "Gedackt 8'": GEDACKT_8_DEF,
    "Octave 4'": OCTAVE_4_DEF,
    "Reed 8'": REED_8_DEF,
    "Mixture": MIXTURE_DEF,
    "Bourdon 16'": BOURDON_16_DEF,
    "Vox Celeste": VOX_CELESTE_DEF,
}

# Legacy harmonic-only registry (for backward compat)
STOP_REGISTRY: dict[str, HarmonicProfile] = {
    name: sdef.harmonics for name, sdef in STOP_DEFS.items()
}

# Drawbar harmonic numbers (Hammond convention)
DRAWBAR_HARMONICS = [0.5, 1, 1.5, 2, 3, 4, 5, 6, 8]

# Drawbar labels
DRAWBAR_LABELS = ["16'", "8'", "5⅓'", "4'", "2⅔'", "2'", "1⅗'", "1⅓'", "1'"]
