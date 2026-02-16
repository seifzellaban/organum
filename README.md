# Organum

A real-time pipe organ synthesizer built with Python. Organum generates sound from scratch using additive synthesis with physically-modeled pipe characteristics -- no samples, no soundfonts. Everything you hear is computed in real-time.

## Features

### Sound Engine

- **Additive synthesis** with per-stop harmonic profiles and waveform shaping (principal, flute, reed, string pipe types)
- **12 organ stops** across four families: Foundation, Brilliance, Reeds, and Color
- **9 drawbars** (Hammond-style) controlling harmonic amplitudes from 16' to 1'
- **Stereo cathedral reverb** with decorrelated delay networks and configurable room acoustics
- **Room resonance** simulating standing waves in stone buildings
- **Tremulant** with multi-component LFO for realistic wind regulator modulation
- **Pipe voicing details**: chiff (attack transient), tracker click, wind noise, chorus detune
- **Polyphonic** with voice management and smooth note stealing

### Interface

- **Full-range keyboard** (C1--C7) rendered on screen with active/inactive octave dimming
- **Split keyboard** with independent left hand (Z--M row) and right hand (Y--] row)
- **Stop group presets** via numpad (0--9) for instant registration changes
- **Drawbar presets** (Full Organ, Gospel, Cathedral, Flutes, Theater, Bach)
- **Room presets** (Grand Cathedral, Stone Chapel, Concert Hall, Gothic Basilica, Intimate Room, Dry Studio)
- **Keyboard drawbar control**: Shift+Numpad to select, arrow keys to adjust
- **MIDI file playback** with transport controls, tempo scaling, and live keyboard visualization
- **Independent hand octave shifting**: Left Ctrl or Right Ctrl + arrow keys

## Requirements

- Python 3.13+
- A working audio output device

## Installation

```bash
git clone https://github.com/youruser/organum.git
cd organum
uv sync
```

## Usage

```bash
uv run python main.py
```

## Keyboard Controls

### Playing Notes

| Keys | Action |
|------|--------|
| Z X C V B N M | Left hand (one octave) |
| Y U I O P [ ] | Right hand (one octave) |

### Navigation

| Keys | Action |
|------|--------|
| Left / Right arrow | Shift both hands by one octave |
| Left Ctrl + arrow | Shift left hand only |
| Right Ctrl + arrow | Shift right hand only |

### Stop Groups (Numpad)

| Key | Group |
|-----|-------|
| Numpad 0 | All stops on |
| Numpad 1 | Foundation (Principal 8', Bourdon 16') |
| Numpad 2 | Plenum (Principal, Octave, Super Octave, Mixture) |
| Numpad 3 | Flutes (Flute 8', Gedackt 8', Bourdon 16') |
| Numpad 4 | Reeds (Reed 8', Trumpet 8') |
| Numpad 5 | Solo Reed (Trumpet 8') |
| Numpad 6 | Strings (Vox Celeste, Voix Humaine) |
| Numpad 7 | Full Swell |
| Numpad 8 | Cathedral |
| Numpad 9 | Ethereal |

### Drawbar Control

| Keys | Action |
|------|--------|
| Shift + Numpad 1--9 | Select drawbar |
| Up / Down arrow | Adjust selected drawbar |

## Project Structure

```
organum/
  main.py                 Entry point
  engine/
    audio.py              Sounddevice output stream
    mixer.py              Polyphonic mixer, reverb, room resonance
    organ.py              Single-voice renderer (OrganVoice)
    oscillator.py         Wavetable oscillator with multiple waveforms
    envelope.py           ADSR envelope generator
    midi_player.py        Background-thread MIDI file player
  gui/
    main_window.py        Main application window and event routing
    keyboard.py           Full-range piano keyboard widget
    stop_panel.py         Organ stop toggle buttons
    drawbars.py           9-drawbar slider panel
    drawbar_presets.py     Drawbar registration presets
    room_panel.py         Room acoustic preset selector
    midi_panel.py         MIDI player transport controls
  stops/
    profiles.py           Stop definitions and harmonic profiles
```

## Dependencies

- **PyQt6** -- GUI framework
- **numpy** -- Audio signal processing
- **sounddevice** -- Real-time audio output (PortAudio)
- **mido** -- MIDI file parsing

## License

MIT
