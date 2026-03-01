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
    attack_ms: float = 45.0         # Envelope attack time
    release_ms: float = 800.0       # Envelope release time
    is_tremulant: bool = False       # True = not a pipe rank, but an effect
    tremulant_depth: float = 0.0     # Amplitude modulation depth (0–1)
    tremulant_rate: float = 6.5      # Amplitude modulation rate (Hz)
    tremulant_pitch_cents: float = 0.0  # Pitch modulation depth in cents
    pitch_shift: float = 1.0         # Pitch multiplier (e.g. 2.0 = octave up)
    is_mutation: bool = False        # True = mutation rank (fixed pitch ratio)


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
    attack_ms=50.0,
    release_ms=750.0,
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
    attack_ms=65.0,
    release_ms=850.0,
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
    attack_ms=55.0,
    release_ms=800.0,
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
    attack_ms=42.0,
    release_ms=700.0,
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
    attack_ms=35.0,
    release_ms=550.0,
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
    attack_ms=40.0,
    release_ms=650.0,
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
    attack_ms=70.0,
    release_ms=1100.0,
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
    attack_ms=65.0,
    release_ms=1000.0,
)

# ── New stops — each fills a distinct sonic purpose ──────────────────

# TRUMPET 8' — Blazing solo reed. The afterburner.
# Extremely rich harmonic content with a biting, brassy attack.
# Use for solo melodies that need to cut through any registration.
TRUMPET_8_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.95, 3: 0.88, 4: 0.80,
        5: 0.72, 6: 0.63, 7: 0.55, 8: 0.48,
        9: 0.40, 10: 0.33, 11: 0.27, 12: 0.22,
        13: 0.17, 14: 0.13, 15: 0.10, 16: 0.07,
        17: 0.05, 18: 0.03, 19: 0.02,
    },
    waveform="reed",
    chorus_detune=1.5,
    vibrato_depth=0.4,
    vibrato_rate=5.5,
    chiff_amount=0.005,     # Reeds don't chiff — they bark
    chiff_ms=5.0,
    wind_noise=0.002,
    attack_ms=22.0,          # Fast but not instant — reeds bark, not click
    release_ms=450.0,        # Quick cutoff — valve snaps shut
)



# SUPER OCTAVE 2' — Brilliant high-pitched principal. Radar sweep.
# Adds sizzle, presence, and brilliance to any registration.
# Essential for building a full plenum (Principal + Octave + Super Octave).
SUPER_OCTAVE_2_DEF = StopDefinition(
    harmonics={
        4: 1.0, 8: 0.55, 12: 0.35, 16: 0.18,
        20: 0.08, 24: 0.04,
    },
    waveform="principal",
    chorus_detune=1.1,
    vibrato_depth=0.7,
    chiff_amount=0.007,
    chiff_ms=8.0,
    wind_noise=0.002,
    attack_ms=32.0,
    release_ms=600.0,
)

# VOIX HUMAINE 8' — Imitative reed that quivers like a human voice.
# Delicate, intimate, eerie. Comms channel.
# Traditionally always used WITH the Tremulant for the wavering effect.
VOIX_HUMAINE_DEF = StopDefinition(
    harmonics={
        1: 1.0, 2: 0.65, 3: 0.42, 4: 0.28,
        5: 0.18, 6: 0.12, 7: 0.08, 8: 0.05,
        9: 0.03, 10: 0.02,
    },
    waveform="reed",
    chorus_detune=2.2,        # Strong chorus for human-like wavering
    vibrato_depth=1.4,        # Deep vibrato — voice-like tremor
    vibrato_rate=5.8,
    chiff_amount=0.003,
    chiff_ms=4.0,
    wind_noise=0.002,
    attack_ms=42.0,
    release_ms=600.0,
)

# TREMULANT — Not a pipe rank. A mechanical wind regulator effect.
# Modulates amplitude + pitch of ALL active stops for a pulsating,
# breathing quality. Beast mode: deep asymmetric pulsation.
TREMULANT_DEF = StopDefinition(
    harmonics={},             # No harmonics — it's an effect, not a rank
    waveform="sine",
    is_tremulant=True,
    tremulant_depth=0.12,     # 35% amplitude modulation — DEEP
    tremulant_rate=5.8,       # ~5.8 Hz — slightly slower for dramatic sweep
    tremulant_pitch_cents=18.0,  # 18 cents pitch wobble — the "wow" factor
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
    "Trumpet 8'": TRUMPET_8_DEF,

    "Super Oct 2'": SUPER_OCTAVE_2_DEF,
    "Voix Humaine": VOIX_HUMAINE_DEF,
    "Tremulant": TREMULANT_DEF,
}

# Legacy harmonic-only registry (for backward compat)
# Exclude Tremulant since it has no harmonics
STOP_REGISTRY: dict[str, HarmonicProfile] = {
    name: sdef.harmonics for name, sdef in STOP_DEFS.items()
    if not sdef.is_tremulant
}

# Drawbar harmonic numbers (Hammond convention)
DRAWBAR_HARMONICS = [0.5, 1, 1.5, 2, 3, 4, 5, 6, 8]

# Drawbar labels
DRAWBAR_LABELS = ["16'", "8'", "5⅓'", "4'", "2⅔'", "2'", "1⅗'", "1⅓'", "1'"]
