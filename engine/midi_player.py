"""MIDI file player — loads and plays .mid files through the organ engine.

Runs playback in a background thread, sending note events to the mixer
at the correct timing. Supports play/pause/stop and tempo control.
"""

import time
import threading
from enum import Enum
from pathlib import Path

import mido

from engine.mixer import Mixer


class PlayerState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class MidiPlayer:
    """Background-thread MIDI file player."""

    def __init__(self, mixer: Mixer) -> None:
        self._mixer = mixer
        self._state = PlayerState.STOPPED
        self._thread: threading.Thread | None = None
        self._tempo_multiplier = 1.0
        self._midi_file: mido.MidiFile | None = None
        self._file_path: str = ""
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially

        # Progress tracking
        self._position = 0.0  # seconds
        self._duration = 0.0  # seconds

        # Active notes for keyboard visualization
        self._active_notes: set[int] = set()

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def position(self) -> float:
        return self._position

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def file_name(self) -> str:
        if self._file_path:
            return Path(self._file_path).name
        return ""

    @property
    def tempo_multiplier(self) -> float:
        return self._tempo_multiplier

    @tempo_multiplier.setter
    def tempo_multiplier(self, value: float) -> None:
        self._tempo_multiplier = max(0.25, min(4.0, value))

    @property
    def active_notes(self) -> set[int]:
        """Currently sounding MIDI notes (for keyboard visualization)."""
        return set(self._active_notes)  # Return copy for thread safety

    def load(self, file_path: str) -> bool:
        """Load a MIDI file. Returns True on success."""
        self.stop()
        try:
            self._midi_file = mido.MidiFile(file_path)
            self._file_path = file_path
            self._duration = self._midi_file.length
            self._position = 0.0
            return True
        except Exception as e:
            print(f"[midi] Error loading {file_path}: {e}")
            self._midi_file = None
            self._file_path = ""
            return False

    def play(self) -> None:
        """Start or resume playback."""
        if self._midi_file is None:
            return

        if self._state == PlayerState.PAUSED:
            self._pause_event.set()
            self._state = PlayerState.PLAYING
            return

        if self._state == PlayerState.PLAYING:
            return

        self._stop_event.clear()
        self._pause_event.set()
        self._state = PlayerState.PLAYING
        self._position = 0.0

        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Pause playback."""
        if self._state == PlayerState.PLAYING:
            self._pause_event.clear()
            self._state = PlayerState.PAUSED

    def stop(self) -> None:
        """Stop playback and release all notes."""
        if self._state == PlayerState.STOPPED:
            return

        self._stop_event.set()
        self._pause_event.set()  # Unpause so thread can exit

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._state = PlayerState.STOPPED
        self._position = 0.0
        self._active_notes.clear()

        # Release any lingering notes
        for note in range(128):
            self._mixer.note_off(note)

    def _playback_loop(self) -> None:
        """Background thread: iterate MIDI messages with timing."""
        if self._midi_file is None:
            return

        start_time = time.monotonic()

        try:
            for msg in self._midi_file:
                # Check stop
                if self._stop_event.is_set():
                    break

                # Wait for unpause
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                # Wait for message timing
                if msg.time > 0:
                    wait_time = msg.time / self._tempo_multiplier
                    target = time.monotonic() + wait_time
                    while time.monotonic() < target:
                        if self._stop_event.is_set():
                            break
                        # Sleep in small increments for responsive stop
                        remaining = target - time.monotonic()
                        if remaining > 0:
                            time.sleep(min(remaining, 0.01))

                if self._stop_event.is_set():
                    break

                # Update position
                self._position = time.monotonic() - start_time

                # Process MIDI messages
                if msg.type == "note_on":
                    if msg.velocity > 0:
                        self._mixer.note_on(msg.note)
                        self._active_notes.add(msg.note)
                    else:
                        self._mixer.note_off(msg.note)
                        self._active_notes.discard(msg.note)
                elif msg.type == "note_off":
                    self._mixer.note_off(msg.note)
                    self._active_notes.discard(msg.note)

        except Exception as e:
            print(f"[midi] Playback error: {e}")

        # Clean up
        for note in range(128):
            self._mixer.note_off(note)
        self._active_notes.clear()

        self._state = PlayerState.STOPPED
        self._position = 0.0
