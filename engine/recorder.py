"""MIDI Recorder — captures real-time events and saves to standard MIDI files."""

import time
import mido
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class RecordedEvent:
    event_type: str  # 'note_on', 'note_off'
    note: int
    velocity: int
    timestamp: float  # seconds relative to start

class Recorder:
    """Records note events and saves them to a MIDI file."""
    
    def __init__(self) -> None:
        self._events: List[RecordedEvent] = []
        self._start_time: float = 0.0
        self._is_recording: bool = False
        
    @property
    def is_recording(self) -> bool:
        return self._is_recording
        
    def start(self, initial_offset: float = 0.0) -> None:
        """Start recording. Clears previous data.
        
        Args:
            initial_offset: Time in seconds to start recording from. 
                           (e.g. if overdubbing starting at 2.0s marks)
        """
        self._events.clear()
        self._start_time = time.monotonic() - initial_offset
        self._is_recording = True
        print(f"[Recorder] Started recording at offset {initial_offset:.2f}s")
        
    def stop(self) -> None:
        """Stop recording."""
        if self._is_recording:
            self._is_recording = False
            print(f"[Recorder] Stopped. Captured {len(self._events)} events.")
            
    def record_event(self, event_type: str, note: int, velocity: int = 64) -> None:
        """Record a note event if currently recording."""
        if not self._is_recording:
            return
            
        timestamp = time.monotonic() - self._start_time
        self._events.append(RecordedEvent(event_type, note, velocity, timestamp))
        
    def get_midi_file(self) -> mido.MidiFile | None:
        """Convert captured events to a mido.MidiFile object."""
        if not self._events:
            return None
            
        try:
            mid = mido.MidiFile()
            track = mido.MidiTrack()
            mid.tracks.append(track)
            
            # Sort events by timestamp just in case
            sorted_events = sorted(self._events, key=lambda e: e.timestamp)
            
            last_time = 0.0
            ticks_per_beat = mid.ticks_per_beat
            tempo = 500000 # microseconds
            
            for event in sorted_events:
                # Ensure delta is non-negative (timestamps might be slightly off if offset used?)
                delta_seconds = max(0.0, event.timestamp - last_time)
                delta_ticks = mido.second2tick(delta_seconds, ticks_per_beat, tempo)
                
                msg = mido.Message(
                    event.event_type,
                    note=event.note,
                    velocity=event.velocity,
                    time=int(delta_ticks)
                )
                track.append(msg)
                last_time = max(last_time, event.timestamp)
                
            return mid
        except Exception as e:
            print(f"[Recorder] Error creating MIDI file: {e}")
            return None

    def save(self, filename: str) -> bool:
        """Save captured events to a MIDI file."""
        mid = self.get_midi_file()
        if not mid:
            print("[Recorder] No events to save.")
            return False
            
        try:    
            mid.save(filename)
            print(f"[Recorder] Saved to {filename}")
            return True
            
        except Exception as e:
            print(f"[Recorder] Error saving file: {e}")
            return False
