"""Polyphonic mixer with stereo cathedral reverb and warm saturation.

Thread safety: GUI thread sends events via SimpleQueue. Audio callback
drains queue and renders voices. ALL processing is fully vectorized
with numpy — no per-sample Python loops in the audio path.
"""

import math

from dataclasses import dataclass
from enum import Enum
from queue import SimpleQueue
from typing import Any

import numpy as np

from engine.organ import OrganVoice
from stops.profiles import STOP_DEFS, STOP_REGISTRY, HarmonicProfile, StopDefinition


class EventType(Enum):
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    DRAWBAR_CHANGE = "drawbar_change"
    STOP_TOGGLE = "stop_toggle"


@dataclass
class AudioEvent:
    type: EventType
    data: Any = None


class CombFilter:
    """Fully vectorized comb filter with constant damping (no per-sample loop)."""

    __slots__ = ("_buffer", "_size", "_pos", "_feedback_damped")

    def __init__(
        self, delay_samples: int, feedback: float = 0.7, damping: float = 0.3
    ) -> None:
        self._buffer = np.zeros(delay_samples, dtype=np.float32)
        self._size = delay_samples
        self._pos = 0
        # Pre-combine feedback and damping into a single multiplier
        # This approximates the one-pole low-pass: constant attenuation
        # rather than per-sample IIR, but avoids the costly Python loop
        self._feedback_damped = feedback * (1.0 - damping * 0.5)

    def process(self, input_signal: np.ndarray) -> np.ndarray:
        n = len(input_signal)
        output = np.empty(n, dtype=np.float32)

        remaining = n
        in_pos = 0

        while remaining > 0:
            chunk = min(remaining, self._size - self._pos)
            buf_slice = slice(self._pos, self._pos + chunk)
            out_slice = slice(in_pos, in_pos + chunk)

            # Read delayed samples
            output[out_slice] = self._buffer[buf_slice]

            # Write new samples with damped feedback (fully vectorized)
            self._buffer[buf_slice] = (
                input_signal[out_slice]
                + self._buffer[buf_slice] * self._feedback_damped
            )

            self._pos = (self._pos + chunk) % self._size
            in_pos += chunk
            remaining -= chunk

        return output


class AllpassFilter:
    """Fully vectorized allpass filter for reverb diffusion."""

    __slots__ = ("_buffer", "_size", "_pos", "_gain")

    def __init__(self, delay_samples: int, gain: float = 0.5) -> None:
        self._buffer = np.zeros(delay_samples, dtype=np.float32)
        self._size = delay_samples
        self._pos = 0
        self._gain = gain

    def process(self, input_signal: np.ndarray) -> np.ndarray:
        n = len(input_signal)
        output = np.empty(n, dtype=np.float32)

        remaining = n
        in_pos = 0

        while remaining > 0:
            chunk = min(remaining, self._size - self._pos)
            buf_slice = slice(self._pos, self._pos + chunk)
            out_slice = slice(in_pos, in_pos + chunk)

            delayed = self._buffer[buf_slice].copy()
            v = input_signal[out_slice] - self._gain * delayed
            output[out_slice] = delayed + self._gain * v
            self._buffer[buf_slice] = v

            self._pos = (self._pos + chunk) % self._size
            in_pos += chunk
            remaining -= chunk

        return output


class CathedralReverb:
    """Schroeder reverb: parallel comb filters + series allpass filters.
    Fully vectorized — no per-sample Python loops.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        room_size: float = 0.85,
        wet: float = 0.22,
        base_delays: list[int] | None = None,
        feedback: float = 0.82,
        damping: float = 0.35,
        predelay_ms: float = 18.0,
    ) -> None:
        if base_delays is None:
            base_delays = [1687, 1601, 2053, 1867, 1511, 1327]
        scale = room_size

        self._combs = [
            CombFilter(int(d * scale), feedback=feedback, damping=damping)
            for d in base_delays
        ]

        self._allpasses = [
            AllpassFilter(241, gain=0.6),
            AllpassFilter(557, gain=0.55),
            AllpassFilter(373, gain=0.5),
        ]

        self._wet = wet
        self._dry = 1.0 - wet
        self._inv_comb_count = 1.0 / len(self._combs)

        # Pre-delay buffer
        self._predelay_samples = max(1, int(predelay_ms * sample_rate / 1000))
        self._predelay_buf = np.zeros(self._predelay_samples, dtype=np.float32)
        self._predelay_pos = 0

    def _predelay(self, signal: np.ndarray) -> np.ndarray:
        n = len(signal)
        output = np.empty(n, dtype=np.float32)
        remaining = n
        in_pos = 0

        while remaining > 0:
            chunk = min(remaining, self._predelay_samples - self._predelay_pos)
            buf_slice = slice(self._predelay_pos, self._predelay_pos + chunk)
            out_slice = slice(in_pos, in_pos + chunk)

            output[out_slice] = self._predelay_buf[buf_slice]
            self._predelay_buf[buf_slice] = signal[out_slice]

            self._predelay_pos = (self._predelay_pos + chunk) % self._predelay_samples
            in_pos += chunk
            remaining -= chunk

        return output

    def process(self, signal: np.ndarray) -> np.ndarray:
        delayed = self._predelay(signal)

        # Sum parallel comb outputs
        reverb = np.zeros_like(signal)
        for comb in self._combs:
            reverb += comb.process(delayed)
        reverb *= self._inv_comb_count

        # Series allpass for diffusion
        for ap in self._allpasses:
            reverb = ap.process(reverb)

        return signal * self._dry + reverb * self._wet


class StereoReverb:
    """Stereo cathedral reverb — two independent reverb units."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self._left = CathedralReverb(
            sample_rate,
            room_size=0.90,
            wet=0.28,
            base_delays=[1687, 1601, 2053, 1867, 1511, 1327],
            feedback=0.84,
            damping=0.32,
            predelay_ms=16.0,
        )
        self._right = CathedralReverb(
            sample_rate,
            room_size=0.93,
            wet=0.28,
            base_delays=[1747, 1663, 2111, 1931, 1559, 1381],
            feedback=0.84,
            damping=0.33,
            predelay_ms=22.0,
        )

    def process(self, mono_signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        left = self._left.process(mono_signal)
        right = self._right.process(mono_signal)
        return left, right


class RoomResonance:
    """Sub-bass cathedral room resonance."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self._sample_rate = sample_rate
        self._phase1 = 0.0
        self._phase2 = 0.0
        self._freq1 = 32.0
        self._freq2 = 48.0
        self._level_smooth = 0.0

    def process(self, signal: np.ndarray, has_active_voices: bool) -> np.ndarray:
        n = len(signal)

        target = 0.012 if has_active_voices else 0.0
        rate = 0.0005 if target > self._level_smooth else 0.0001
        self._level_smooth += (target - self._level_smooth) * rate

        if self._level_smooth < 0.0001:
            return signal

        t = np.arange(n, dtype=np.float64)
        res1 = np.sin(
            2 * np.pi * self._freq1 * t / self._sample_rate + self._phase1
        ).astype(np.float32)
        res2 = np.sin(
            2 * np.pi * self._freq2 * t / self._sample_rate + self._phase2
        ).astype(np.float32)

        self._phase1 = (
            self._phase1 + 2 * np.pi * self._freq1 * n / self._sample_rate
        ) % (2 * np.pi)
        self._phase2 = (
            self._phase2 + 2 * np.pi * self._freq2 * n / self._sample_rate
        ) % (2 * np.pi)

        return signal + (res1 * 0.6 + res2 * 0.4) * self._level_smooth


# Maximum simultaneous voices (prevents CPU overload with long releases)
MAX_VOICES = 24


class Mixer:
    """Polyphonic mixer with stereo cathedral reverb and room resonance."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.event_queue: SimpleQueue[AudioEvent] = SimpleQueue()

        self._voices: dict[int, OrganVoice] = {}

        # FULL CATHEDRAL REGISTRATION
        # self._drawbar_values: list[float] = [
        #     1.0,  # 16'
        #     1.0,  # 8'
        #     0.7,  # 5⅓'
        #     0.85, # 4'
        #     0.5,  # 2⅔'
        #     0.65, # 2'
        #     0.35, # 1⅗'
        #     0.3,  # 1⅓'
        #     0.25, # 1'
        # ]
        self._drawbar_values: list[float] = [
            1.0,
            1.0,
            0.75,
            1.0,
            0.625,
            0.875,
            0.5,
            0.375,
            0.25,
        ]

        self._active_stops: dict[str, HarmonicProfile] = {
            "Principal 8'": STOP_REGISTRY["Principal 8'"],
            "Bourdon 16'": STOP_REGISTRY["Bourdon 16'"],
        }

        self._active_stop_defs: dict[str, StopDefinition] = {
            "Principal 8'": STOP_DEFS["Principal 8'"],
            "Bourdon 16'": STOP_DEFS["Bourdon 16'"],
        }

        self._master_volume = 0.32
        self._stereo_reverb = StereoReverb(sample_rate)
        self._room_resonance = RoomResonance(sample_rate)

        # Tremulant state
        self._tremulant_active = False
        self._tremulant_phase = 0.0
        self._tremulant_depth = 0.12
        self._tremulant_rate = 6.5

        # Mutation voice tracking: maps base note -> list of mutation voice keys
        self._mutation_keys: dict[int, list[int]] = {}

    def _process_events(self) -> None:
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
            except Exception:
                break

            if event.type == EventType.NOTE_ON:
                note = event.data
                if note in self._voices:
                    self._voices[note].note_off()

                # Voice stealing: if at max, kill the quietest releasing voice
                if len(self._voices) >= MAX_VOICES:
                    # Find a releasing (not actively held) voice to steal
                    oldest_note = None
                    for vn, vv in self._voices.items():
                        if not vv.is_active:
                            oldest_note = vn
                            break
                    if oldest_note is None:
                        # All voices active — steal first one
                        oldest_note = next(iter(self._voices))
                    del self._voices[oldest_note]

                # Normal (non-mutation) stop defs for the primary voice
                normal_defs = [
                    sd for sd in self._active_stop_defs.values()
                    if not sd.is_mutation
                ]
                if normal_defs:
                    self._voices[note] = OrganVoice(
                        note, self.sample_rate, stop_defs=normal_defs
                    )

                # Mutation stops get their own separate voices at shifted pitch
                for shift_id, (sname, sd) in enumerate(
                    self._active_stop_defs.items()
                ):
                    if sd.is_mutation:
                        # Compute the MIDI note that corresponds to the shifted pitch
                        # pitch_shift=3 means 3rd harmonic (12+7 = 19 semitones up)
                        # pitch_shift=5 means 5th harmonic (12+12+4 = 28 semitones)
                        semi_shift = round(12 * math.log2(sd.pitch_shift))
                        mutation_note = note + semi_shift

                        # Only create if the resulting note is reasonable
                        if 0 <= mutation_note <= 127:
                            mut_key = -(note * 1000 + shift_id + 1)
                            if mut_key in self._voices:
                                self._voices[mut_key].note_off()
                            self._voices[mut_key] = OrganVoice(
                                mutation_note, self.sample_rate,
                                stop_defs=[sd],
                            )
                            # Track which mutation keys belong to this note
                            self._mutation_keys.setdefault(note, []).append(mut_key)

            elif event.type == EventType.NOTE_OFF:
                note = event.data
                if note in self._voices:
                    self._voices[note].note_off()
                # Also release any mutation voices for this note
                if note in self._mutation_keys:
                    for mk in self._mutation_keys[note]:
                        if mk in self._voices:
                            self._voices[mk].note_off()
                    del self._mutation_keys[note]

            elif event.type == EventType.DRAWBAR_CHANGE:
                idx, value = event.data
                if 0 <= idx < 9:
                    self._drawbar_values[idx] = value

            elif event.type == EventType.STOP_TOGGLE:
                stop_name = event.data
                stop_def = STOP_DEFS.get(stop_name)
                if not stop_def:
                    continue

                # Tremulant is a special case — it's an effect, not a rank
                if stop_def.is_tremulant:
                    self._tremulant_active = not self._tremulant_active
                    if self._tremulant_active:
                        self._tremulant_depth = stop_def.tremulant_depth
                        self._tremulant_rate = stop_def.tremulant_rate
                    continue

                if stop_name in self._active_stops:
                    del self._active_stops[stop_name]
                    del self._active_stop_defs[stop_name]
                elif stop_name in STOP_REGISTRY:
                    self._active_stops[stop_name] = STOP_REGISTRY[stop_name]
                    self._active_stop_defs[stop_name] = STOP_DEFS[stop_name]

    def render(self, num_frames: int) -> np.ndarray:
        """Render stereo audio: returns (num_frames, 2) array."""
        self._process_events()

        mono = np.zeros(num_frames, dtype=np.float32)
        stop_profiles = list(self._active_stops.values())

        has_voices = False
        active_count = 0

        if stop_profiles:
            dead_notes: list[int] = []
            for note, voice in self._voices.items():
                if voice.is_active:
                    mono += voice.render(
                        num_frames, self._drawbar_values, stop_profiles
                    )
                    has_voices = True
                    active_count += 1
                else:
                    dead_notes.append(note)

            for note in dead_notes:
                del self._voices[note]

        # Voice normalization
        if active_count > 1:
            mono *= 1.0 / np.sqrt(active_count)

        # DC removal (vectorized — just subtract mean)
        mono -= np.mean(mono)

        # Sub-bass room resonance
        mono = self._room_resonance.process(mono, has_voices)

        # Tremulant: sinusoidal amplitude modulation across all voices
        if self._tremulant_active and has_voices:
            t_frames = np.arange(num_frames, dtype=np.float32)
            trem_lfo = 1.0 - self._tremulant_depth * (
                0.5 + 0.5 * np.sin(
                    2 * np.pi * self._tremulant_rate * t_frames / self.sample_rate
                    + self._tremulant_phase
                )
            )
            self._tremulant_phase += (
                2 * np.pi * self._tremulant_rate * num_frames / self.sample_rate
            )
            self._tremulant_phase %= (2 * np.pi)
            mono *= trem_lfo

        # Stereo cathedral reverb
        left, right = self._stereo_reverb.process(mono)

        # Warm saturation (fully vectorized)
        left = self._saturate(left)
        right = self._saturate(right)

        return np.column_stack((left, right))

    def _saturate(self, signal: np.ndarray) -> np.ndarray:
        """Warm tube-style saturation."""
        scaled = signal * self._master_volume
        return np.where(
            np.abs(scaled) < 0.5,
            scaled,
            np.sign(scaled) * (1.0 - np.exp(-2.0 * np.abs(scaled))) * 0.7,
        ).astype(np.float32)

    # ── Convenience methods for the GUI thread ──────────────────────

    def note_on(self, note: int) -> None:
        self.event_queue.put(AudioEvent(EventType.NOTE_ON, note))

    def note_off(self, note: int) -> None:
        self.event_queue.put(AudioEvent(EventType.NOTE_OFF, note))

    def set_drawbar(self, index: int, value: float) -> None:
        self.event_queue.put(AudioEvent(EventType.DRAWBAR_CHANGE, (index, value)))

    def toggle_stop(self, stop_name: str) -> None:
        self.event_queue.put(AudioEvent(EventType.STOP_TOGGLE, stop_name))

    @property
    def active_stop_names(self) -> set[str]:
        names = set(self._active_stops.keys())
        if self._tremulant_active:
            names.add("Tremulant")
        return names

    @property
    def drawbar_values(self) -> list[float]:
        return list(self._drawbar_values)
