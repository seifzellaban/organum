# Contributing to Organum

This guide explains how to work on the Organum pipe organ synthesizer project.

## Project Overview

Organum is a real-time pipe organ synthesizer using additive synthesis with physically-modeled pipe characteristics. It consists of:

- **Engine** (`engine/`): Audio processing, synthesis, effects, MIDI playback
- **GUI** (`gui/`): PyQt6-based user interface
- **Stops** (`stops/`): Pipe organ stop definitions and harmonic profiles

## Reading Order

When learning the codebase, read files in this order:

### 1. Entry Point
**`main.py`** - Application bootstrap
- Sets up the audio engine, mixer, MIDI player, and GUI
- Initializes PyQt6 application
- Handles clean shutdown

### 2. Engine Layer (Audio Core)

Read these in order to understand the audio pipeline:

**`engine/audio.py`** - Audio output interface
- `SAMPLE_RATE = 44100` - Global sample rate
- `BLOCK_SIZE = 4096` - Audio buffer size (~93ms latency)
- `AudioEngine` class: Manages sounddevice output stream
  - `__init__(mixer)` - Initialize with mixer instance
  - `start()` - Open and start audio stream
  - `stop()` - Stop and close audio stream
  - `_callback()` - Real-time audio callback (pulls from mixer)

**`engine/mixer.py`** - Polyphonic mixer with effects
- `EventType` enum - Queue event types (NOTE_ON, NOTE_OFF, etc.)
- `AudioEvent` dataclass - Event for audio thread communication
- `CombFilter` class - Vectorized comb filter for reverb
- `AllpassFilter` class - Vectorized allpass filter for reverb diffusion
- `CathedralReverb` class - Schroeder reverb implementation
- `StereoReverb` class - Dual reverb for stereo width
- `RoomResonance` class - Sub-bass room mode simulation
- `RoomPresetParams` dataclass - Room acoustic parameters
- `ROOM_PRESETS` dict - Predefined room configurations
- `Mixer` class - Main audio mixing engine
  - `__init__(sample_rate)` - Initialize voices, effects, and state
  - `note_on(note)` - Queue note on event
  - `note_off(note)` - Queue note off event
  - `set_drawbar(index, value)` - Queue drawbar change
  - `toggle_stop(name)` - Queue stop toggle
  - `set_room_preset(name)` - Queue room preset change
  - `render(num_frames)` - Render stereo audio (called by audio callback)
  - `_process_events()` - Drain event queue
  - `_saturate(signal)` - Soft-clipping with tanh

**`engine/organ.py`** - Single organ voice
- `midi_to_freq(note)` - Convert MIDI note to frequency
- `CHIFF_TABLE` - Pre-computed chiff noise
- `_WIND_NOISE_TABLE` - Pre-computed wind noise
- `OrganVoice` class - Renders one note
  - `__init__(note, sample_rate, stop_defs)` - Initialize oscillators and envelope
  - `note_off()` - Begin release phase
  - `retrigger()` - Re-attack while resonating
  - `render(num_frames, drawbar_values, stop_profiles)` - Generate audio
  - `is_active` property - Voice is sounding
  - `is_releasing` property - Voice is in release phase

**`engine/oscillator.py`** - Wavetable oscillator
- `TABLE_SIZE = 4096` - Wavetable size
- `_make_sine()` - Generate sine wavetable
- `_make_principal()` - Generate principal pipe waveform
- `_make_flute()` - Generate flute pipe waveform
- `_make_reed()` - Generate reed pipe waveform
- `_make_string()` - Generate string pipe waveform
- `_build_tiers()` - Create band-limited versions
- `_select_table()` - Choose appropriate wavetable for frequency
- `Oscillator` class - Band-limited wavetable oscillator
  - `__init__(freq, sample_rate, vibrato_depth, vibrato_rate, waveform)`
  - `set_frequency(freq)` - Update frequency
  - `render(num_frames)` - Generate samples with optional vibrato

**`engine/envelope.py`** - ADSR envelope
- `Stage` enum - Envelope stages (IDLE, ATTACK, DECAY, SUSTAIN, RELEASE)
- `Envelope` class - ADSR envelope generator
  - `__init__(sample_rate, attack_ms, decay_ms, sustain, release_ms, attack_curve)`
  - `note_on()` - Start attack phase
  - `note_off()` - Start release phase
  - `retrigger()` - Re-enter attack from current level
  - `render(num_frames)` - Vectorized envelope generation
  - `is_active` property - Envelope is active
  - `is_releasing` property - In release stage

**`engine/midi_player.py`** - MIDI file playback
- `PlayerState` enum - STOPPED, PLAYING, PAUSED
- `MidiPlayer` class - Background MIDI player
  - `__init__(mixer)` - Initialize player state
  - `load(file_path)` - Load MIDI file
  - `play()` - Start/resume playback
  - `pause()` - Pause playback
  - `stop()` - Stop and release all notes
  - `tempo_multiplier` property - Speed control (0.25x to 4x)
  - `active_notes` property - Currently sounding notes
  - `_playback_loop()` - Background thread for timing

### 3. Data Layer

**`stops/profiles.py`** - Stop definitions
- `HarmonicProfile` type alias - Dict[int, float]
- `StopDefinition` dataclass - Complete stop configuration
  - `harmonics` - Harmonic amplitudes
  - `waveform` - Oscillator waveform name
  - `chorus_detune` - Detuning amount in Hz
  - `vibrato_depth/rate` - Vibrato parameters
  - `chiff_amount/ms` - Attack transient settings
  - `wind_noise` - Continuous noise level
  - `attack_ms/release_ms` - Envelope times
  - `is_tremulant` - Effect flag
  - `pitch_shift` - Frequency multiplier
  - `is_mutation` - Fixed ratio flag
- `STOP_DEFS` dict - All stop definitions by name
- `STOP_REGISTRY` dict - Harmonic profiles only
- `DRAWBAR_HARMONICS` list - Drawbar frequency ratios
- `DRAWBAR_LABELS` list - Drawbar display names

### 4. GUI Layer

**`gui/main_window.py`** - Main application window
- `NOTE_NAMES` list - Note name strings
- `_note_name(midi)` - Format MIDI note as string
- `STOP_GROUPS` dict - Numpad preset registrations
- `_disable_focus_recursive(widget)` - Prevent keyboard focus stealing
- `MainWindow` class - Top-level window
  - `__init__(mixer, midi_player)` - Build UI and connect signals
  - `eventFilter()` - Intercept all key events for keyboard
  - `_on_note_on/off(note)` - Handle keyboard note events
  - `_on_drawbar_change(idx, value)` - Handle drawbar changes
  - `_on_stop_toggle(name, active)` - Handle stop button toggles
  - `_on_stop_group(group_id)` - Apply preset registration
  - `_on_room_selected(name)` - Apply room preset

**`gui/keyboard.py`** - Piano keyboard widget
- `LEFT_HAND_KEY_MAP` dict - Z-M row to semitone offsets
- `RIGHT_HAND_KEY_MAP` dict - Y-] row to semitone offsets
- `NUMPAD_KEYS` dict - Numpad digit mapping
- `PianoKeyboard` class - Visual keyboard with split-hand control
  - `__init__(base_note)` - Initialize keyboard layout
  - `set_base_note(note)` - Move both hands
  - `shift_octave(direction)` - Shift both hands
  - `shift_left_hand(direction)` - Shift left hand only
  - `shift_right_hand(direction)` - Shift right hand only
  - `set_highlighted_notes(notes)` - Show MIDI playback
  - `paintEvent()` - Draw keyboard with active/inactive octaves
  - `keyPressEvent()` - Handle key presses
  - `keyReleaseEvent()` - Handle key releases
  - Signals: `note_on`, `note_off`, `octave_changed`, `hands_changed`, `stop_group_selected`, `drawbar_selected`, `drawbar_adjust`

**`gui/stop_panel.py`** - Stop toggle buttons
- `STOP_FAMILIES` dict - Organize stops by family
- `StopPanel` class - Grid of stop buttons
  - `__init__(stop_names, active_stops)` - Build button grid
  - `update_stops(active_stops)` - Sync button states
  - `_on_toggle(name, checked)` - Emit toggle signal
  - `_button_style(active)` - CSS for stop buttons
  - `_tremulant_style(active)` - CSS for tremulant button
  - Signal: `stop_toggled(name, active)`

**`gui/drawbars.py`** - Hammond-style drawbars
- `DrawbarPanel` class - Nine vertical sliders
  - `__init__(labels, initial_values)` - Build slider panel
  - `highlight_drawbar(index)` - Visual selection highlight
  - `adjust_drawbar(index, delta)` - Change value by steps
  - `set_values(values)` - Set all drawbars at once
  - Signal: `drawbar_changed(index, value)`

**`gui/drawbar_presets.py`** - Drawbar preset buttons
- `DRAWBAR_PRESETS` dict - Classic registrations (Full Organ, Gospel, etc.)
- `DrawbarPresetPanel` class - Preset selection buttons
  - `__init__(initial_preset)` - Build preset buttons
  - `_on_select(name, values)` - Apply preset
  - Signal: `preset_selected(name, values)`

**`gui/room_panel.py`** - Room preset selector
- `ROOM_DESCRIPTIONS` dict - Room preset descriptions
- `RoomPresetPanel` class - Room selection buttons
  - `__init__(preset_names, current)` - Build room buttons
  - `_on_select(name)` - Apply room preset
  - Signal: `room_selected(name)`

**`gui/midi_panel.py`** - MIDI player controls
- `BTN_STYLE` / `BTN_ACTIVE` - Button CSS constants
- `MidiPlayerPanel` class - Transport controls
  - `__init__(midi_player)` - Build file/transport/tempo UI
  - `_on_open()` - File picker dialog
  - `_on_play/pause/stop()` - Transport controls
  - `_on_tempo_change(value)` - Adjust playback speed
  - `_update_status()` - Update playback status display

## Adding New Functions

### Audio Engine Functions

When adding audio processing functions:

1. **Prefer vectorized numpy operations** - Never use Python loops in the audio path
2. **Process by block, not sample** - Accept `num_frames` parameter
3. **Return float32 arrays** - Consistent with rest of engine
4. **Handle edge cases** - Empty input, zero frames, etc.

Example pattern:
```python
def process_audio(self, input_signal: np.ndarray) -> np.ndarray:
    n = len(input_signal)
    output = np.empty(n, dtype=np.float32)
    
    # Vectorized processing
    output[:] = input_signal * self._gain
    
    return output
```

### GUI Event Handlers

When adding GUI functionality:

1. **Use signals for cross-component communication** - Decouple widgets
2. **Queue events to audio thread** - Never call audio functions directly from GUI
3. **Update visual state immediately** - Provide instant feedback
4. **Handle focus carefully** - Set `NoFocus` on buttons to prevent keyboard conflicts

Example pattern:
```python
# In widget:
def _on_button_clicked(self, checked: bool) -> None:
    self.button.setStyleSheet(self._get_style(checked))
    self.signal.emit(self.name, checked)  # Emit signal

# In main window:
widget.signal.connect(self._handle_event)

def _handle_event(self, name: str, active: bool) -> None:
    self.mixer.toggle_stop(name)  # Queue to audio thread
```

### Stop Definitions

When adding new organ stops:

1. **Define in `stops/profiles.py`** - Add to `STOP_DEFS` dictionary
2. **Choose appropriate waveform** - principal/flute/reed/string
3. **Set harmonic content** - Dict mapping harmonic number to amplitude
4. **Configure voicing** - chiff, noise, envelope times
5. **Add to family in `gui/stop_panel.py`** - Include in `STOP_FAMILIES`
6. **Add tooltip description** - Document the stop's character

## Building and Running

### Prerequisites

- Python 3.13+
- Working audio output device
- `uv` (Python package manager)

### Setup

```bash
# Clone repository
git clone <repository-url>
cd organum

# Install dependencies (creates .venv/)
uv sync
```

### Run

```bash
# Run the application
uv run python main.py
```

### Development Workflow

```bash
# Run with hot reload (if using a file watcher)
uv run python main.py

# Type checking (optional)
uv run mypy engine/ gui/ stops/

# Linting (optional)
uv run ruff check .
```

## Architecture Guidelines

### Audio Thread Safety

- GUI thread sends events via `SimpleQueue`
- Audio callback (in `AudioEngine._callback`) drains queue and processes
- Never block in audio callback
- All audio processing is vectorized (no Python loops)

### Signal Flow

```
GUI Event → Mixer Queue → _process_events() → Voice.render() → Reverb → Output
                 ↑                                              ↓
            (async queue)                                 (real-time audio)
```

### Adding New Features

1. **Audio effect?** → Add class in `engine/mixer.py`, apply in `render()`
2. **New stop type?** → Define in `stops/profiles.py`, add to panel
3. **New GUI widget?** → Create in `gui/`, connect in `main_window.py`
4. **New keyboard control?** → Handle in `gui/keyboard.py`

## Testing Changes

1. **Test audio changes** - Verify no glitches/clicks at different polyphony levels
2. **Test GUI changes** - Verify keyboard controls still work
3. **Test presets** - Verify all stop groups and drawbar presets load correctly
4. **Test MIDI playback** - Load and play a MIDI file

## Code Style

- Use type hints throughout
- Document classes and public methods with docstrings
- Keep functions focused and small
- Use numpy vectorization for audio processing
- Prefer immutable data structures where possible
