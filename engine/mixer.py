"""Polyphonic mixer with simple reverb.

Thread safety: GUI thread sends events via SimpleQueue. Audio callback
drains queue and renders voices. Simple Schroeder reverb via comb filters.
"""

from dataclasses import dataclass
from enum import Enum
from queue import SimpleQueue
from typing import Any

import numpy as np

from engine.organ import OrganVoice
from stops.profiles import STOP_REGISTRY, HarmonicProfile


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
    """Vectorized comb filter for reverb."""

    __slots__ = ("_buffer", "_size", "_pos", "_feedback")

    def __init__(self, delay_samples: int, feedback: float = 0.7) -> None:
        self._buffer = np.zeros(delay_samples, dtype=np.float32)
        self._size = delay_samples
        self._pos = 0
        self._feedback = feedback

    def process(self, input_signal: np.ndarray) -> np.ndarray:
        n = len(input_signal)
        output = np.empty(n, dtype=np.float32)

        # Process in chunks to avoid modulo overhead
        remaining = n
        in_pos = 0

        while remaining > 0:
            # How many samples until we wrap?
            chunk = min(remaining, self._size - self._pos)

            # Read delayed samples
            output[in_pos : in_pos + chunk] = self._buffer[
                self._pos : self._pos + chunk
            ]

            # Write new samples with feedback
            self._buffer[self._pos : self._pos + chunk] = (
                input_signal[in_pos : in_pos + chunk]
                + output[in_pos : in_pos + chunk] * self._feedback
            )

            self._pos = (self._pos + chunk) % self._size
            in_pos += chunk
            remaining -= chunk

        return output


class AllpassFilter:
    """Vectorized allpass filter for reverb diffusion."""

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

            delayed = self._buffer[self._pos : self._pos + chunk]
            v = input_signal[in_pos : in_pos + chunk] - self._gain * delayed
            output[in_pos : in_pos + chunk] = delayed + self._gain * v
            self._buffer[self._pos : self._pos + chunk] = v

            self._pos = (self._pos + chunk) % self._size
            in_pos += chunk
            remaining -= chunk

        return output


class SimpleReverb:
    """Schroeder reverb: 4 parallel comb filters + 2 series allpass filters."""

    def __init__(
        self, sample_rate: int = 44100, room_size: float = 0.6, wet: float = 0.2
    ) -> None:
        # Prime number delays for reduced metallic artifacts
        base_delays = [1557, 1617, 1491, 1422]
        scale = room_size
        self._combs = [CombFilter(int(d * scale), feedback=0.75) for d in base_delays]
        self._allpasses = [
            AllpassFilter(225, gain=0.5),
            AllpassFilter(556, gain=0.5),
        ]
        self._wet = wet
        self._dry = 1.0 - wet

    def process(self, signal: np.ndarray) -> np.ndarray:
        # Sum parallel comb outputs
        reverb = np.zeros_like(signal)
        for comb in self._combs:
            reverb += comb.process(signal)
        reverb *= 0.25

        # Series allpass
        for ap in self._allpasses:
            reverb = ap.process(reverb)

        return signal * self._dry + reverb * self._wet


class Mixer:
    """Polyphonic mixer owning all active voices and current organ state."""

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self.event_queue: SimpleQueue[AudioEvent] = SimpleQueue()

        self._voices: dict[int, OrganVoice] = {}

        # 9 drawbar values (0.0–1.0), default: classic organ registration
        # self._drawbar_values: list[float] = [
        #     0.0,  # 16'
        #     1.0,  # 8'
        #     0.0,  # 5⅓'
        #     0.75,  # 4'
        #     0.0,  # 2⅔'
        #     0.5,  # 2'
        #     0.0,  # 1⅗'
        #     0.0,  # 1⅓'
        #     0.0,  # 1'
        # ]

        # GRAND CATHEDRAL REGISTRATION - Full, rich, majestic
        self._drawbar_values: list[float] = [
            0.8,  # 16' - Sub-octave foundation (THIS IS ESSENTIAL)
            1.0,  # 8'  - Fundamental (keep it)
            0.6,  # 5⅓' - Quint adds warmth and complexity
            0.8,  # 4'  - Octave reinforcement (bump this UP)
            0.4,  # 2⅔' - Second quint for richness
            0.6,  # 2'  - Upper octave for brilliance
            0.3,  # 1⅗' - Tierce adds COLOR
            0.25,  # 1⅓' - Larigot for shimmer
            0.2,  # 1'  - Top octave sparkle
        ]

        self._active_stops: dict[str, HarmonicProfile] = {
            "Principal 8'": STOP_REGISTRY["Principal 8'"],
        }

        self._master_volume = 0.35
        self._reverb = SimpleReverb(sample_rate, room_size=0.7, wet=0.18)

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
                self._voices[note] = OrganVoice(note, self.sample_rate)

            elif event.type == EventType.NOTE_OFF:
                note = event.data
                if note in self._voices:
                    self._voices[note].note_off()

            elif event.type == EventType.DRAWBAR_CHANGE:
                idx, value = event.data
                if 0 <= idx < 9:
                    self._drawbar_values[idx] = value

            elif event.type == EventType.STOP_TOGGLE:
                stop_name = event.data
                if stop_name in self._active_stops:
                    del self._active_stops[stop_name]
                elif stop_name in STOP_REGISTRY:
                    self._active_stops[stop_name] = STOP_REGISTRY[stop_name]

    def render(self, num_frames: int) -> np.ndarray:
        self._process_events()

        output = np.zeros(num_frames, dtype=np.float32)
        stop_profiles = list(self._active_stops.values())

        if not stop_profiles:
            return output

        dead_notes: list[int] = []
        for note, voice in self._voices.items():
            if voice.is_active:
                output += voice.render(num_frames, self._drawbar_values, stop_profiles)
            else:
                dead_notes.append(note)

        for note in dead_notes:
            del self._voices[note]

        # Apply reverb
        output = self._reverb.process(output)

        # Soft clipping
        output = np.tanh(output * self._master_volume) * 0.9

        return output

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
        return set(self._active_stops.keys())

    @property
    def drawbar_values(self) -> list[float]:
        return list(self._drawbar_values)
