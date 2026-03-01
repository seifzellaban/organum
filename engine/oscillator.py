"""Wavetable oscillator with band-limited waveforms, chorus detuning, and vibrato.

Pre-computes multiple versions of each waveform at different harmonic
counts (band-limited). The oscillator automatically selects the
appropriate table based on its frequency to prevent aliasing.
"""

import numpy as np

# Wavetable size — power of 2 for fast modulo via bitwise AND
TABLE_SIZE = 4096
TABLE_MASK = TABLE_SIZE - 1

_t = np.arange(TABLE_SIZE, dtype=np.float64) / TABLE_SIZE


# --------------------------------------------------------------------------
# Band-limited wavetable generation
# --------------------------------------------------------------------------


def _make_sine() -> np.ndarray:
    return np.sin(2.0 * np.pi * _t).astype(np.float32)


def _make_principal(max_harmonics: int = 8) -> np.ndarray:
    """Open diapason / principal — bright with strong even & odd harmonics."""
    amps = [0, 1.0, 0.50, 0.35, 0.20, 0.12, 0.07, 0.04, 0.02]
    w = np.zeros(TABLE_SIZE, dtype=np.float64)
    for k in range(1, min(max_harmonics + 1, len(amps))):
        w += amps[k] * np.sin(2 * np.pi * k * _t)
    if np.max(np.abs(w)) > 0:
        w /= np.max(np.abs(w))
    return w.astype(np.float32)


def _make_flute(max_harmonics: int = 7) -> np.ndarray:
    """Stopped flute — nearly pure fundamental with faint odd harmonics."""
    # Only odd harmonics
    odd_amps = {1: 1.0, 3: 0.08, 5: 0.03, 7: 0.01}
    w = np.zeros(TABLE_SIZE, dtype=np.float64)
    for k, amp in odd_amps.items():
        if k <= max_harmonics:
            w += amp * np.sin(2 * np.pi * k * _t)
    if np.max(np.abs(w)) > 0:
        w /= np.max(np.abs(w))
    return w.astype(np.float32)


def _make_reed(max_harmonics: int = 19) -> np.ndarray:
    """Reed / trumpet — very rich harmonics, almost sawtooth-like."""
    w = np.zeros(TABLE_SIZE, dtype=np.float64)
    for k in range(1, min(max_harmonics + 1, 20)):
        amp = 1.0 / k * (0.92**k)
        w += amp * np.sin(2 * np.pi * k * _t)
    if np.max(np.abs(w)) > 0:
        w /= np.max(np.abs(w))
    return w.astype(np.float32)


def _make_string(max_harmonics: int = 15) -> np.ndarray:
    """String / viol — moderate fundamental, strong upper partials."""
    w = np.zeros(TABLE_SIZE, dtype=np.float64)
    for k in range(1, min(max_harmonics + 1, 16)):
        amp = (k / 3.0) * np.exp(-0.3 * k)
        w += amp * np.sin(2 * np.pi * k * _t)
    if np.max(np.abs(w)) > 0:
        w /= np.max(np.abs(w))
    return w.astype(np.float32)


# --------------------------------------------------------------------------
# Pre-compute band-limited table tiers for each waveform
# Each tier has fewer harmonics for higher frequency playback
# --------------------------------------------------------------------------

# Tier boundaries: (max_frequency_for_this_tier, table)
# At a given oscillator frequency, pick the first tier whose max_freq > osc_freq.
# If osc_freq exceeds all tiers, fall back to sine.


def _build_tiers(make_fn, harmonic_counts: list[int], sample_rate: int = 44100) -> list:
    """Build band-limited tiers: (max_freq, table) pairs.

    For a table with N harmonics, the max safe frequency is nyquist / N.
    """
    nyquist = sample_rate / 2.0
    tiers = []
    for n_harmonics in sorted(harmonic_counts, reverse=True):
        max_freq = nyquist / max(n_harmonics, 1)
        table = make_fn(max_harmonics=n_harmonics)
        tiers.append((max_freq, table))
    # Sort by max_freq ascending so we can iterate and pick first match
    tiers.sort(key=lambda x: x[0])
    return tiers


_SINE_TABLE = _make_sine()

# Pre-build tiers for each waveform
_WAVEFORM_TIERS: dict[str, list[tuple[float, np.ndarray]]] = {
    "sine": [(99999.0, _SINE_TABLE)],
    "principal": _build_tiers(_make_principal, [8, 4, 2, 1]),
    "flute": _build_tiers(_make_flute, [7, 3, 1]),
    "reed": _build_tiers(_make_reed, [19, 8, 4, 2, 1]),
    "string": _build_tiers(_make_string, [15, 6, 3, 1]),
}


def _select_table(waveform: str, frequency: float) -> np.ndarray:
    """Select the band-limited table appropriate for the given frequency."""
    tiers = _WAVEFORM_TIERS.get(waveform)
    if not tiers:
        return _SINE_TABLE
    for max_freq, table in tiers:
        if frequency <= max_freq:
            return table
    # Frequency too high for any tier — use sine (no harmonics to alias)
    return _SINE_TABLE


class Oscillator:
    """Phase-accumulator oscillator with band-limited waveform, chorus, and vibrato."""

    __slots__ = (
        "_phase",
        "_phase_inc",
        "_sample_rate",
        "_frequency",
        "_vibrato_depth",
        "_vibrato_rate",
        "_vibrato_phase",
        "_table",
    )

    def __init__(
        self,
        frequency: float,
        sample_rate: int = 44100,
        vibrato_depth: float = 0.0,
        vibrato_rate: float = 5.5,
        waveform: str = "sine",
    ) -> None:
        self._sample_rate = sample_rate
        self._frequency = frequency
        self._phase = np.random.uniform(0, TABLE_SIZE)  # Random start for chorus
        self._phase_inc = frequency * TABLE_SIZE / sample_rate
        self._vibrato_depth = vibrato_depth  # In Hz
        self._vibrato_rate = vibrato_rate  # LFO rate in Hz
        self._vibrato_phase = np.random.uniform(0, 2 * np.pi)
        # Band-limited table selection based on frequency
        self._table = _select_table(waveform, frequency)

    def set_frequency(self, frequency: float) -> None:
        self._frequency = frequency
        self._phase_inc = frequency * TABLE_SIZE / self._sample_rate

    def render(self, num_frames: int) -> np.ndarray:
        """Generate num_frames samples with optional vibrato.

        Uses pre-allocated work buffers to avoid per-call numpy allocations.
        """
        # Get shared work buffers (resized only when block size changes)
        bufs = _get_work_buffers(num_frames)
        n = num_frames
        t = bufs.t[:n]

        if self._vibrato_depth > 0:
            # LFO modulates frequency — reuse sliced buffers
            lfo = bufs.lfo[:n]
            np.multiply(
                2 * np.pi * self._vibrato_rate / self._sample_rate, t, out=lfo
            )
            lfo += self._vibrato_phase
            np.sin(lfo, out=lfo)

            phases = bufs.phases[:n]
            np.multiply(lfo, self._vibrato_depth, out=phases)
            phases += self._frequency
            phases *= TABLE_SIZE / self._sample_rate
            np.cumsum(phases, out=phases)
            phases += self._phase

            self._vibrato_phase += (
                2 * np.pi * self._vibrato_rate * n / self._sample_rate
            )
            last_phase_inc = phases[n - 1] - (
                phases[n - 2] if n > 1 else self._phase
            )
        else:
            phases = bufs.phases[:n]
            np.multiply(self._phase_inc, t, out=phases)
            phases += self._phase
            last_phase_inc = self._phase_inc

        # Wrap phase
        np.mod(phases, TABLE_SIZE, out=phases)

        # Linear interpolation — reuse sliced index buffers
        idx = bufs.idx[:n]
        frac = bufs.frac[:n]
        np.floor(phases, out=frac)  # temp use of frac as floor
        np.copyto(idx, frac, casting='unsafe')  # float -> int

        np.subtract(phases, frac, out=frac)  # frac = phases - floor(phases)
        frac_f32 = frac.astype(np.float32)

        idx_next = bufs.idx_next[:n]
        np.add(idx, 1, out=idx_next)
        np.bitwise_and(idx_next, TABLE_MASK, out=idx_next)

        table = self._table
        samples = table[idx] * (1.0 - frac_f32) + table[idx_next] * frac_f32

        # Advance phase state
        self._phase = (phases[n - 1] + last_phase_inc) % TABLE_SIZE

        return samples


class _WorkBuffers:
    """Pre-allocated numpy buffers shared by all oscillators to avoid GC pressure."""
    __slots__ = ("size", "t", "lfo", "phases", "frac", "idx", "idx_next")

    def __init__(self, size: int) -> None:
        self.size = size
        self.t = np.arange(size, dtype=np.float64)
        self.lfo = np.empty(size, dtype=np.float64)
        self.phases = np.empty(size, dtype=np.float64)
        self.frac = np.empty(size, dtype=np.float64)
        self.idx = np.empty(size, dtype=np.int32)
        self.idx_next = np.empty(size, dtype=np.int32)


_work_bufs: _WorkBuffers | None = None


def _get_work_buffers(num_frames: int) -> _WorkBuffers:
    """Return shared work buffers, allocating/resizing only when needed."""
    global _work_bufs
    if _work_bufs is None or _work_bufs.size < num_frames:
        _work_bufs = _WorkBuffers(num_frames)
    return _work_bufs
