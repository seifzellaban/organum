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
from stops.profiles import STOP_DEFS, STOP_REGISTRY, HarmonicProfile, StopDefinition, DRAWBAR_HARMONICS


class EventType(Enum):
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    DRAWBAR_CHANGE = "drawbar_change"
    STOP_TOGGLE = "stop_toggle"
    ROOM_PRESET = "room_preset"


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

    Tuned for a grand cathedral acoustic: long RT60, dense diffusion,
    significant predelay for spaciousness.
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

        # 4 allpass stages for denser, more diffuse tail
        self._allpasses = [
            AllpassFilter(241, gain=0.6),
            AllpassFilter(557, gain=0.55),
            AllpassFilter(373, gain=0.5),
            AllpassFilter(829, gain=0.45),
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


# ── Room preset definitions ──────────────────────────────────────────
# Each preset is a dict of parameters for the StereoReverb constructor.

@dataclass
class RoomPresetParams:
    """Parameters defining a room acoustic."""
    name: str
    room_size_l: float
    room_size_r: float
    wet: float
    feedback: float
    damping_l: float
    damping_r: float
    predelay_l: float
    predelay_r: float
    resonance_level: float    # Room resonance intensity
    resonance_freqs: tuple[float, float, float]  # 3 standing wave frequencies


ROOM_PRESETS: dict[str, RoomPresetParams] = {
    "Grand Cathedral": RoomPresetParams(
        name="Grand Cathedral",
        room_size_l=1.05, room_size_r=1.10,
        wet=0.42, feedback=0.89,
        damping_l=0.25, damping_r=0.27,
        predelay_l=24.0, predelay_r=32.0,
        resonance_level=0.025,
        resonance_freqs=(24.0, 36.0, 52.0),
    ),
    "Stone Chapel": RoomPresetParams(
        name="Stone Chapel",
        room_size_l=0.72, room_size_r=0.76,
        wet=0.32, feedback=0.82,
        damping_l=0.32, damping_r=0.34,
        predelay_l=12.0, predelay_r=18.0,
        resonance_level=0.015,
        resonance_freqs=(32.0, 48.0, 68.0),
    ),
    "Concert Hall": RoomPresetParams(
        name="Concert Hall",
        room_size_l=0.92, room_size_r=0.96,
        wet=0.35, feedback=0.85,
        damping_l=0.30, damping_r=0.32,
        predelay_l=18.0, predelay_r=26.0,
        resonance_level=0.018,
        resonance_freqs=(28.0, 42.0, 58.0),
    ),
    "Gothic Basilica": RoomPresetParams(
        name="Gothic Basilica",
        room_size_l=1.20, room_size_r=1.28,
        wet=0.50, feedback=0.92,
        damping_l=0.20, damping_r=0.22,
        predelay_l=35.0, predelay_r=48.0,
        resonance_level=0.032,
        resonance_freqs=(20.0, 30.0, 44.0),
    ),
    "Intimate Room": RoomPresetParams(
        name="Intimate Room",
        room_size_l=0.50, room_size_r=0.52,
        wet=0.18, feedback=0.70,
        damping_l=0.45, damping_r=0.48,
        predelay_l=5.0, predelay_r=8.0,
        resonance_level=0.008,
        resonance_freqs=(45.0, 65.0, 90.0),
    ),
    "Dry Studio": RoomPresetParams(
        name="Dry Studio",
        room_size_l=0.35, room_size_r=0.37,
        wet=0.08, feedback=0.55,
        damping_l=0.55, damping_r=0.58,
        predelay_l=2.0, predelay_r=3.0,
        resonance_level=0.003,
        resonance_freqs=(55.0, 80.0, 110.0),
    ),
}

DEFAULT_ROOM_PRESET = "Grand Cathedral"


class StereoReverb:
    """Grand cathedral stereo reverb — two decorrelated reverb units.

    Asymmetric delay lines and different room sizes create a wide stereo
    image. High feedback + low damping = long, shimmering tail (~4-5s RT60).
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        preset: RoomPresetParams | None = None,
    ) -> None:
        if preset is None:
            preset = ROOM_PRESETS[DEFAULT_ROOM_PRESET]

        # Left channel
        self._left = CathedralReverb(
            sample_rate,
            room_size=preset.room_size_l,
            wet=preset.wet,
            base_delays=[1687, 1601, 2053, 1867, 1511, 1327, 2287],
            feedback=preset.feedback,
            damping=preset.damping_l,
            predelay_ms=preset.predelay_l,
        )
        # Right channel: slightly different for stereo width
        self._right = CathedralReverb(
            sample_rate,
            room_size=preset.room_size_r,
            wet=preset.wet,
            base_delays=[1747, 1663, 2111, 1931, 1559, 1381, 2393],
            feedback=preset.feedback,
            damping=preset.damping_r,
            predelay_ms=preset.predelay_r,
        )

    def process(self, mono_signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        left = self._left.process(mono_signal)
        right = self._right.process(mono_signal)
        return left, right


class RoomResonance:
    """Sub-bass cathedral room resonance — the chest-rumbling weight.

    Three resonant frequencies simulate the standing waves of a large
    stone building. This is what makes it feel GRAND.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        self._sample_rate = sample_rate
        self._phase1 = 0.0
        self._phase2 = 0.0
        self._phase3 = 0.0
        self._freq1 = 24.0       # Deep sub-bass — feel it in your chest
        self._freq2 = 36.0       # Low room mode
        self._freq3 = 52.0       # Upper room mode
        self._level_smooth = 0.0

    def process(self, signal: np.ndarray, has_active_voices: bool) -> np.ndarray:
        n = len(signal)

        target = 0.025 if has_active_voices else 0.0
        rate = 0.001 if target > self._level_smooth else 0.0002
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
        res3 = np.sin(
            2 * np.pi * self._freq3 * t / self._sample_rate + self._phase3
        ).astype(np.float32)

        self._phase1 = (
            self._phase1 + 2 * np.pi * self._freq1 * n / self._sample_rate
        ) % (2 * np.pi)
        self._phase2 = (
            self._phase2 + 2 * np.pi * self._freq2 * n / self._sample_rate
        ) % (2 * np.pi)
        self._phase3 = (
            self._phase3 + 2 * np.pi * self._freq3 * n / self._sample_rate
        ) % (2 * np.pi)

        return signal + (res1 * 0.45 + res2 * 0.35 + res3 * 0.20) * self._level_smooth


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
            0.75,
            1.0,
            0.625,
            0.875,
            0.375,
            0.625,
            0.25,
            0.25,
            0.125,
        ]

        self._active_stops: dict[str, HarmonicProfile] = {
            "Principal 8'": STOP_REGISTRY["Principal 8'"],
            "Bourdon 16'": STOP_REGISTRY["Bourdon 16'"],
        }

        self._active_stop_defs: dict[str, StopDefinition] = {
            "Principal 8'": STOP_DEFS["Principal 8'"],
            "Bourdon 16'": STOP_DEFS["Bourdon 16'"],
        }

        self._master_volume = 0.26
        self._current_room_preset = DEFAULT_ROOM_PRESET
        self._stereo_reverb = StereoReverb(sample_rate)
        self._room_resonance = RoomResonance(sample_rate)

        # Tremulant state — multi-component LFO for realistic wind regulator
        self._tremulant_active = False
        self._tremulant_phase = 0.0
        self._tremulant_depth = 0.12          # Default amplitude mod depth
        self._tremulant_rate = 6.5            # Default rate (Hz)
        self._tremulant_pitch_depth = 0.0     # Pitch modulation in cents
        self._tremulant_drift_phase = 0.0     # Slow wander for organic feel

        # Mutation voice tracking: maps base note -> list of mutation voice keys
        self._mutation_keys: dict[int, list[int]] = {}

        # Monotonic sample counter — avoids syscalls (time.monotonic) in RT thread
        self._sample_clock: int = 0

        # Smoothed normalization gain — avoids clicks when voice count changes
        self._norm_gain: float = 1.0

        # Track when each note was last released (sample clock value)
        # Used to suppress transients on rapid re-strikes (<500ms)
        self._note_release_samples: dict[int, int] = {}
        self._restrike_window_samples = int(0.5 * sample_rate)  # 500ms

    def _process_events(self) -> None:
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
            except Exception:
                break

            if event.type == EventType.NOTE_ON:
                note = event.data

                # ── Real wind physics: if the pipe is already speaking,
                #    pressing the key again does nothing. The valve is
                #    already open and wind is already flowing through the
                #    pipe. Only if the voice is in release (key was lifted
                #    but sound is still fading) do we retrigger smoothly
                #    WITHOUT creating a new voice (preserves phase continuity).
                existing = self._voices.get(note)
                if existing is not None and existing.is_active:
                    if existing.is_releasing:
                        # Pipe still resonating — re-open the valve smoothly
                        existing.retrigger()
                    # else: pipe already fully speaking — ignore the keypress
                    continue

                # Suppress chiff/tracker click on rapid re-strikes (<500ms)
                # so repeated keystrokes don't sound like a machine gun.
                # Uses sample clock instead of syscall for RT safety.
                last_release = self._note_release_samples.get(note, 0)
                rapid_restrike = (
                    (self._sample_clock - last_release)
                    < self._restrike_window_samples
                )

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
                    sd for sd in self._active_stop_defs.values() if not sd.is_mutation
                ]
                if normal_defs:
                    self._voices[note] = OrganVoice(
                        note, self.sample_rate, stop_defs=normal_defs,
                        suppress_transients=rapid_restrike,
                    )

                # Mutation stops get their own separate voices at shifted pitch
                for shift_id, (sname, sd) in enumerate(self._active_stop_defs.items()):
                    if sd.is_mutation:
                        semi_shift = round(12 * math.log2(sd.pitch_shift))
                        mutation_note = note + semi_shift

                        if 0 <= mutation_note <= 127:
                            mut_key = -(note * 1000 + shift_id + 1)
                            existing_mut = self._voices.get(mut_key)
                            if existing_mut is not None and existing_mut.is_active:
                                if existing_mut.is_releasing:
                                    existing_mut.retrigger()
                                continue
                            self._voices[mut_key] = OrganVoice(
                                mutation_note,
                                self.sample_rate,
                                stop_defs=[sd],
                                suppress_transients=rapid_restrike,
                            )
                            self._mutation_keys.setdefault(note, []).append(mut_key)

            elif event.type == EventType.NOTE_OFF:
                note = event.data
                self._note_release_samples[note] = self._sample_clock
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
                        self._tremulant_pitch_depth = stop_def.tremulant_pitch_cents
                    continue

                if stop_name in self._active_stops:
                    del self._active_stops[stop_name]
                    del self._active_stop_defs[stop_name]
                elif stop_name in STOP_REGISTRY:

                    self._active_stops[stop_name] = STOP_REGISTRY[stop_name]
                    self._active_stop_defs[stop_name] = STOP_DEFS[stop_name]

            elif event.type == EventType.ROOM_PRESET:
                preset_name = event.data
                preset = ROOM_PRESETS.get(preset_name)
                if preset:
                    self._current_room_preset = preset_name
                    self._stereo_reverb = StereoReverb(
                        self.sample_rate, preset=preset
                    )
                    # Update room resonance frequencies
                    self._room_resonance._freq1 = preset.resonance_freqs[0]
                    self._room_resonance._freq2 = preset.resonance_freqs[1]
                    self._room_resonance._freq3 = preset.resonance_freqs[2]

    def render(self, num_frames: int) -> np.ndarray:
        """Render stereo audio: returns (num_frames, 2) array."""
        self._process_events()
        self._sample_clock += num_frames

        mono = np.zeros(num_frames, dtype=np.float32)
        stop_profiles = list(self._active_stops.values())

        has_voices = False
        active_count = 0

        if stop_profiles:
            # Pre-compute harmonic amplitudes once per block (same for all voices)
            harmonic_amps = np.zeros(len(DRAWBAR_HARMONICS), dtype=np.float32)
            for profile in stop_profiles:
                for i, h in enumerate(DRAWBAR_HARMONICS):
                    h_int = int(round(h)) if h >= 1 else 1
                    if h_int in profile:
                        harmonic_amps[i] += profile[h_int] * self._drawbar_values[i]
            if len(stop_profiles) > 1:
                max_amp = harmonic_amps.max()
                if max_amp > 1.0:
                    harmonic_amps /= max_amp

            dead_notes: list[int] = []
            for note, voice in self._voices.items():
                if voice.is_active:
                    mono += voice.render(num_frames, harmonic_amps)
                    has_voices = True
                    active_count += 1
                else:
                    dead_notes.append(note)

            for note in dead_notes:
                del self._voices[note]

        # Voice normalization with smooth gain ramp (no clicks)
        # Hard 1/sqrt(n) causes a 30% pop when going from 1->2 voices.
        # Instead, smoothly ramp from previous gain to new target.
        target_gain = 1.0 / np.sqrt(max(active_count, 1))
        if abs(target_gain - self._norm_gain) > 0.001:
            ramp = np.linspace(
                self._norm_gain, target_gain, num_frames, dtype=np.float32
            )
            mono *= ramp
        else:
            mono *= target_gain
        self._norm_gain = target_gain

        # DC removal (vectorized — just subtract mean)
        mono -= np.mean(mono)

        # Sub-bass room resonance
        mono = self._room_resonance.process(mono, has_voices)

        # Tremulant: POWER MODE — wind pressure surge
        # Instead of cutting volume (choppy), the tremulant BOOSTS the signal
        # with a slow, smooth pulsation. Engaging it makes everything LOUDER
        # and more powerful, like opening a second wind reservoir.
        if self._tremulant_active and has_voices:
            t_frames = np.arange(num_frames, dtype=np.float32)
            rate = self._tremulant_rate
            base_angle = (
                2 * np.pi * rate * t_frames / self.sample_rate
                + self._tremulant_phase
            )

            # Smooth LFO — fundamental + gentle 2nd harmonic for organic swell
            # No harsh high harmonics (that's what made it choppy)
            lfo = (
                np.sin(base_angle) * 0.80                   # Smooth fundamental
                + np.sin(2.0 * base_angle + 0.6) * 0.15     # Slight asymmetry
                + np.sin(0.11 * base_angle                   # Very slow drift
                         + self._tremulant_drift_phase) * 0.05
            )

            # Shift LFO to [0, 1] range (always positive — always boosting)
            lfo_positive = (lfo + 1.0) * 0.5

            # Amplitude: constant boost + pulsating surge on top
            # Base boost: 20% louder just for engaging tremulant
            # Surge: additional 0-20% pulsating on top
            boost_base = 1.20
            surge_depth = self._tremulant_depth * 1.5   # e.g. 0.12 * 1.5 = 0.18
            trem_amp = boost_base + surge_depth * lfo_positive
            mono *= trem_amp.astype(np.float32)

            # Advance phases
            self._tremulant_phase += (
                2 * np.pi * rate * num_frames / self.sample_rate
            )
            self._tremulant_phase %= 2 * np.pi
            self._tremulant_drift_phase += (
                2 * np.pi * 0.11 * rate * num_frames / self.sample_rate
            )
            self._tremulant_drift_phase %= 2 * np.pi

        # Stereo cathedral reverb
        left, right = self._stereo_reverb.process(mono)

        # Warm saturation (fully vectorized)
        left = self._saturate(left)
        right = self._saturate(right)

        return np.column_stack((left, right))

    def _saturate(self, signal: np.ndarray) -> np.ndarray:
        """Smooth tanh soft-clipper — no discontinuities, no clicks.

        The old np.where approach had a threshold discontinuity that caused
        audible clicking. tanh is continuously differentiable everywhere.
        """
        scaled = signal * self._master_volume
        # Add a tiny bit of asymmetry for even harmonics (tube-like warmth)
        scaled += 0.03 * (scaled ** 2)
        return np.tanh(scaled * 2.0).astype(np.float32) * 0.55

    # ── Convenience methods for the GUI thread ──────────────────────

    def note_on(self, note: int) -> None:
        self.event_queue.put(AudioEvent(EventType.NOTE_ON, note))

    def note_off(self, note: int) -> None:
        self.event_queue.put(AudioEvent(EventType.NOTE_OFF, note))

    def set_drawbar(self, index: int, value: float) -> None:
        self.event_queue.put(AudioEvent(EventType.DRAWBAR_CHANGE, (index, value)))

    def toggle_stop(self, stop_name: str) -> None:
        self.event_queue.put(AudioEvent(EventType.STOP_TOGGLE, stop_name))

    def set_room_preset(self, preset_name: str) -> None:
        self.event_queue.put(AudioEvent(EventType.ROOM_PRESET, preset_name))

    @property
    def active_stop_names(self) -> set[str]:
        names = set(self._active_stops.keys())
        if self._tremulant_active:
            names.add("Tremulant")
        return names

    @property
    def drawbar_values(self) -> list[float]:
        return list(self._drawbar_values)

    @property
    def current_room_preset(self) -> str:
        return self._current_room_preset
