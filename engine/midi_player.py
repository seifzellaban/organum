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
        self._messages: list[mido.Message] = []
        self._file_path: str = ""
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        
        self._looping = False
        self._note_callback = None  # Function(note: int, state: bool)

        # Progress tracking
        self._position = 0.0  # seconds
        self._duration = 0.0  # seconds

    @property
    def looping(self) -> bool:
        return self._looping

    @looping.setter
    def looping(self, value: bool) -> None:
        self._looping = value

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
        return "Memory Sequence" if self._midi_file else ""

    @property
    def tempo_multiplier(self) -> float:
        return self._tempo_multiplier

    @tempo_multiplier.setter
    def tempo_multiplier(self, value: float) -> None:
        self._tempo_multiplier = max(0.25, min(4.0, value))
        
    def set_note_callback(self, callback) -> None:
        """Set a callback(note: int, state: bool) for visual feedback."""
        self._note_callback = callback

    def load(self, source: str | mido.MidiFile) -> bool:
        """Load a MIDI file from path or object. Returns True on success."""
        self.stop()
        try:
            if isinstance(source, str):
                self._midi_file = mido.MidiFile(source)
                self._file_path = source
            else:
                self._midi_file = source
                self._file_path = ""
            
            # Pre-calculate duration and messages for looping/seeking
            self._duration = self._midi_file.length
            self._messages = list(self._midi_file)
            self._position = 0.0
            return True
        except Exception as e:
            print(f"[midi] Error loading: {e}")
            self._midi_file = None
            self._messages = []
            self._file_path = ""
            return False

    def play(self) -> None:
        """Start or resume playback."""
        if not self._messages:
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
            for note in range(128):
                self._mixer.note_off(note)
                if self._note_callback:
                    self._note_callback(note, False)
            return

        self._stop_event.set()
        self._pause_event.set()  # Unpause so thread can exit

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        self._state = PlayerState.STOPPED
        self._position = 0.0

        # Release any lingering notes
        for note in range(128):
            self._mixer.note_off(note)
            if self._note_callback:
                self._note_callback(note, False)

    def _playback_loop(self) -> None:
        """Background thread: iterate MIDI messages with timing."""
        if not self._messages:
            return

        while True: # Looping wrapper
            start_time = time.monotonic()
            
            try:
                for msg in self._messages:
                    # Check stop
                    if self._stop_event.is_set():
                        return

                    # Wait for unpause
                    self._pause_event.wait()
                    if self._stop_event.is_set():
                        return

                    # Wait for message timing
                    if msg.time > 0:
                        wait_time = msg.time / self._tempo_multiplier
                        target = time.monotonic() + wait_time
                        while time.monotonic() < target:
                            if self._stop_event.is_set():
                                return
                            # Sleep in small increments
                            remaining = target - time.monotonic()
                            if remaining > 0:
                                time.sleep(min(remaining, 0.01))

                    if self._stop_event.is_set():
                        return

                    # Update position
                    self._position = time.monotonic() - start_time

                    # Process MIDI messages
                    if msg.type == "note_on":
                        if msg.velocity > 0:
                            self._mixer.note_on(msg.note)
                            if self._note_callback:
                                self._note_callback(msg.note, True)
                        else:
                            self._mixer.note_off(msg.note)
                            if self._note_callback:
                                self._note_callback(msg.note, False)
                    elif msg.type == "note_off":
                        self._mixer.note_off(msg.note)
                        if self._note_callback:
                            self._note_callback(msg.note, False)
                            
            except Exception as e:
                print(f"[midi] Playback error: {e}")
                break

            if not self._looping or self._stop_event.is_set():
                break
            
            # Reset for loop
            self._position = 0.0
            for note in range(128):
                self._mixer.note_off(note)
                if self._note_callback:
                    self._note_callback(note, False)

        # Clean up at end
        for note in range(128):
            self._mixer.note_off(note)
            if self._note_callback:
                self._note_callback(note, False)

        self._state = PlayerState.STOPPED
        self._position = 0.0
