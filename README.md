# Organum

A real-time pipe organ synthesizer built with Python. Organum generates sound entirely from scratch using additive synthesis with physically-modeled pipe characteristics — no samples, no soundfonts. Every note you hear is computed in real-time from sine waves, harmonic profiles, and acoustic simulation.

---

## Features

### Sound Engine

- **Additive synthesis** with per-stop harmonic profiles and realistic waveform shaping across four pipe families: principal, flute, reed, and string
- **11 organ stops** spanning Foundation, Brilliance, Reed, and Color families
- **9 drawbars** (Hammond-style) giving individual control over harmonic amplitudes from 16′ sub-bass to 1′ brilliance
- **Stereo cathedral reverb** using a pair of decorrelated Schroeder reverb networks (parallel comb filters + series allpass stages) with a configurable predelay for room size
- **6 room presets** from Dry Studio to Gothic Basilica, each tuning reverb decay, damping, predelay, and sub-bass resonance
- **Room resonance** — three tuned sine oscillators simulating stone-building standing waves for physical chest-level weight
- **Tremulant** — multi-component LFO modulating wind pressure for a pulsating, breathing feel
- **Per-pipe voicing details**: chiff (wind-rush attack transient), tracker action click (mechanical valve impulse), wind noise, per-note detuning randomization, chorus detuning, and vibrato
- **Smooth ADSR envelopes** — smoothstep attack (zero slope at onset and peak) and gentle exponential release; no clicks at note-on, note-off, or retrigger
- **Voice retrigger**: re-pressing a held or recently-released note crossfades back to sustain (15 ms Hermite S-curve) instead of restarting the attack, preserving oscillator phase continuity
- **Transient suppression**: re-striking a key within 500 ms suppresses chiff and tracker click to avoid machine-gun percussive artifacts
- **Smooth voice normalization**: gain scales with `1/√N` voices but ramps linearly across each buffer, eliminating the amplitude pop when new notes are added
- **Polyphonic** up to 24 simultaneous voices with automatic release-voice stealing
- **Mutation stops** rendered at shifted pitch ratios as independent voices

### Interface

- **Full-range keyboard display** (C1–C7) with active octave highlighting, pressed-note coloring, key label overlays, and left/right hand color coding
- **Split keyboard**: independent left hand (Z–M row) and right hand (Y–] row) with separate octave ranges
- **Mouse playable**: click keys directly on the on-screen keyboard
- **Stop group presets** via numpad (0–9) for instant registration changes
- **6 drawbar presets** (Full Organ, Gospel, Cathedral, Flutes, Theater, Bach) for one-key registration
- **6 room acoustic presets** switchable at any time
- **Keyboard drawbar control**: Shift+Numpad to select a drawbar, then arrow keys to adjust
- **MIDI file playback** with transport controls (play/pause/stop), tempo scaling (50%–200%), and live keyboard visualization showing active MIDI notes

---

## Requirements

- Python 3.13+
- A working audio output device (PortAudio)

---

## Installation

```bash
git clone https://github.com/youruser/organum.git
cd organum
uv sync
```

---

## Running

```bash
uv run python main.py
```

---

## Keyboard Controls

### Playing Notes

The keyboard is split into two independent hands. Each row covers one chromatic octave. Black keys (sharps/flats) are on the row above each white key.

#### Left Hand (lower octave)

| White keys | Z · X · C · V · B · N · M |
|------------|---------------------------|
| Black keys | S · D · &nbsp; · G · H · J |

#### Right Hand (upper octave)

| White keys | Y · U · I · O · P · \[ · \] |
|------------|------------------------------|
| Black keys | 7 · 8 · &nbsp; · 0 · - · = |

### Octave Navigation

| Keys | Action |
|------|--------|
| `←` / `→` | Shift **both** hands one octave |
| `Left Ctrl` + `←` / `→` | Shift **left hand** only |
| `Right Ctrl` + `←` / `→` | Shift **right hand** only |

### Stop Group Presets (Numpad)

| Key | Registration |
|-----|-------------|
| `Num 0` | All stops on |
| `Num 1` | **Foundation** — Principal 8′, Bourdon 16′ |
| `Num 2` | **Plenum** — Principal 8′, Octave 4′, Super Oct 2′, Mixture |
| `Num 3` | **Flutes** — Flute 8′, Gedackt 8′, Bourdon 16′ |
| `Num 4` | **Reeds** — Reed 8′, Trumpet 8′ |
| `Num 5` | **Solo Reed** — Trumpet 8′ |
| `Num 6` | **Strings** — Vox Celeste, Voix Humaine |
| `Num 7` | **Full Swell** — Principal, Flute, Octave, Reed, Vox Celeste, Tremulant |
| `Num 8` | **Cathedral** — Principal, Bourdon, Octave, Super Oct, Mixture, Trumpet |
| `Num 9` | **Ethereal** — Flute, Gedackt, Vox Celeste, Voix Humaine, Tremulant |

### Drawbar Control

| Keys | Action |
|------|--------|
| `Shift` + `Num 1`–`9` | Select drawbar (highlights it) |
| `↑` / `↓` | Adjust selected drawbar value |

Drawbars represent harmonics in Hammond organ convention:

| Position | Footage | Harmonic |
|----------|---------|----------|
| 1 | 16′ | Sub-octave (½×) |
| 2 | 8′ | Fundamental (1×) |
| 3 | 5⅓′ | Quint (1.5×) |
| 4 | 4′ | Octave (2×) |
| 5 | 2⅔′ | Nazard (3×) |
| 6 | 2′ | Super octave (4×) |
| 7 | 1⅗′ | Tierce (5×) |
| 8 | 1⅓′ | Larigot (6×) |
| 9 | 1′ | Sifflöte (8×) |

---

## Stops Reference

### Foundation

| Stop | Character |
|------|-----------|
| **Principal 8′** | Bright open diapason — the backbone of any registration |
| **Bourdon 16′** | Deep stopped flute — sub-bass weight, mostly odd harmonics |

### Brilliance

| Stop | Character |
|------|-----------|
| **Octave 4′** | Bright principal one octave up — adds presence |
| **Super Oct 2′** | High-pitched sizzle — brilliance and radar sweep |
| **Mixture** | Multi-rank compound stop — dense upper partials, shimmers |

### Reeds

| Stop | Character |
|------|-----------|
| **Reed 8′** | Rich, buzzy reed pipe — harmonics like a sawtooth |
| **Trumpet 8′** | Blazing solo reed — biting attack, cuts through everything |

### Color

| Stop | Character |
|------|-----------|
| **Flute 8′** | Pure, round stopped flute — nearly sine, very gentle |
| **Gedackt 8′** | Soft stopped flute — darker than Flute 8′, woody |
| **Vox Celeste** | String celeste — strong chorus detuning for undulating beats |
| **Voix Humaine** | Imitative reed — quivering, voice-like. Use with Tremulant |
| **Tremulant** | Not a pipe rank — activates a wind-pressure LFO over all active stops |

---

## Room Presets

| Preset | Character |
|--------|-----------|
| **Grand Cathedral** | Long shimmer, wide stereo, deep sub-bass resonance (~4–5 s RT60) |
| **Stone Chapel** | Medium church, stone reflections |
| **Concert Hall** | Balanced reverb, natural warmth |
| **Gothic Basilica** | Extreme decay, cavernous — almost unplayable at fast tempos |
| **Intimate Room** | Small hall, close and present |
| **Dry Studio** | Minimal reverb — useful for checking raw stop tone |

---

## Project Structure

```
organum/
├── main.py                   Entry point — wires up engine, audio, MIDI, GUI
├── engine/
│   ├── audio.py              sounddevice OutputStream wrapper (44100 Hz, 4096 frames/block)
│   ├── mixer.py              Polyphonic mixer: voice pool, reverb, tremulant, normalization
│   ├── organ.py              OrganVoice — single note with chorus, chiff, envelope
│   ├── oscillator.py         Wavetable oscillator with band-limited waveforms and vibrato
│   ├── envelope.py           Smoothstep ADSR with RETRIGGER crossfade stage
│   └── midi_player.py        Background-thread MIDI file player with tempo control
├── gui/
│   ├── main_window.py        Main window, event filter, stop groups, keyboard routing
│   ├── keyboard.py           Full-range piano keyboard widget (C1–C7), split hands
│   ├── stop_panel.py         Stop toggle button grid
│   ├── drawbars.py           9-drawbar vertical slider panel
│   ├── drawbar_presets.py    Drawbar registration preset buttons
│   ├── room_panel.py         Room acoustic preset selector
│   └── midi_panel.py         MIDI transport controls (play/pause/stop, tempo)
├── stops/
│   └── profiles.py           Stop definitions: harmonic profiles, waveform, voicing parameters
└── tests/
    ├── test_envelope.py      Envelope curve correctness, retrigger smoothness
    ├── test_voice.py         Voice transient suppression, retrigger continuity
    ├── test_mixer.py         Normalization, rapid re-strikes, voice lifecycle
    ├── test_oscillator.py    Output correctness, variable block sizes, buffer reuse
    └── test_performance.py   Render budget assertions, clipping, stereo separation
```

---

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run with benchmark output (shows timing numbers)
uv run pytest tests/ -v -s

# Run a specific file
uv run pytest tests/test_envelope.py -v
```

Tests cover:

- **Envelope** — smoothstep attack shape, release decay rate, click-free retrigger, full ADSR lifecycle
- **Voice** — transient suppression on rapid re-strikes, retrigger phase continuity, rendering correctness
- **Mixer** — smooth gain normalization at voice count transitions, 500 ms re-strike window, voice cleanup
- **Oscillator** — output shape and dtype, phase continuity across blocks, variable block sizes, work buffer reuse
- **Performance** — 4-voice and 8-voice renders must stay within the ~93 ms audio budget at P95

---

## Dependencies

| Package | Purpose |
|---------|---------|
| **PyQt6** | GUI framework |
| **numpy** | All audio signal processing (fully vectorized) |
| **sounddevice** | Real-time audio output (PortAudio) |
| **mido** | MIDI file parsing |

---

## How It Works

### The Synthesis Chain

When you press a key, the following happens from input to speaker:

```
Key/MIDI event
      │
      ▼
  Mixer.note_on()  ─── puts AudioEvent on a SimpleQueue
      │
      ▼  (audio callback thread, every ~93ms)
  Mixer._process_events()
      │   creates an OrganVoice for the note
      ▼
  OrganVoice.render()
      │   ├── oscillator pairs (wavetable × harmonic amps)
      │   ├── + chiff noise burst
      │   ├── + tracker click impulse
      │   ├── + wind noise (pre-computed table)
      │   └── × ADSR envelope
      ▼
  mono sum of all active voices
      │
      ▼
  smooth gain normalization (1/√N voices, linear ramp)
      │
      ▼
  DC removal
      │
      ▼
  Room resonance (3 tuned sub-bass sine oscillators)
      │
      ▼
  Tremulant (amplitude LFO, if active)
      │
      ▼
  StereoReverb.process()  ─── left + right decorrelated reverb
      │
      ▼
  tanh soft saturation (tube-like warm clipping)
      │
      ▼
  sounddevice output buffer  ─► speakers
```

---

### Wavetable Oscillator

Each harmonic in a voice is rendered by a `Oscillator` — a phase-accumulating wavetable lookup with linear interpolation. Four waveform families are pre-computed at startup:

- **Principal** — bright with balanced even and odd harmonics (up to 8 at lowest pitches, fewer at high frequencies to prevent aliasing)
- **Flute** — near-pure fundamental, mostly odd harmonics (1st, 3rd, 5th, 7th)
- **Reed** — rich harmonic series approaching a sawtooth, with 1/k·0.92^k rolloff
- **String** — peaked mid-range, boosted around the 3rd harmonic

Each waveform is stored in multiple **band-limited tiers** — tables with progressively fewer harmonics for higher pitches. At note creation the oscillator selects the tier where all harmonics stay below the Nyquist frequency, eliminating aliasing without filters.

The oscillator uses **pre-allocated work buffers** (`_work_bufs`): a single set of `float64` arrays shared across all oscillator calls in a render block. This drops ~1,000 numpy allocations per audio callback to near-zero, halving GC pressure in the hot path.

Optional **vibrato** modulates the instantaneous phase increment each sample using a sine LFO — producing FM-style pitch wobble.

---

### Additive Synthesis and Drawbars

Each `OrganVoice` holds up to 18 oscillators: two per drawbar position (9 positions × 2 chorus partners). The harmonic amplitudes are:

```
harmonic_amp[i] = Σ(stop_profiles) profile[h] × drawbar_value[i]
```

This sum is computed **once per audio block** in the mixer (not per voice), so 8 simultaneous voices all read the same pre-computed amplitude array — avoiding 7 redundant nested-loop calculations.

The **chorus partner** oscillator is tuned slightly sharp (by `chorus_detune` Hz, with extra widening below 130 Hz for massive bass). Lower-amplitude harmonics skip their chorus partner entirely — the detuning is inaudible below 15% amplitude, and skipping it saves a full wavetable render.

---

### Envelope (ADSR + Retrigger)

The envelope has six stages:

| Stage | Description |
|-------|-------------|
| `IDLE` | Silent. Voice can be cleaned up. |
| `ATTACK` | Smoothstep curve `3t²−2t³` from 0→1. Zero slope at both ends — note **blooms** in without punching or slamming. |
| `DECAY` | Exponential approach from peak (1.0) down to sustain level. |
| `SUSTAIN` | Constant at sustain level (0.92) for as long as the key is held. |
| `RELEASE` | Exponential `exp(−1.2t)` decay — reaches 50% in ~430 ms, lingers naturally. |
| `RETRIGGER` | Hermite S-curve crossfade from current level back to sustain over 15 ms. Used when re-pressing a key that is still releasing. |

The `RETRIGGER` stage exists specifically to avoid clicks. Re-entering `ATTACK` from mid-release causes a curve-shape discontinuity — the derivative changes abruptly. The Hermite blend (`3t²−2t³`) has zero derivative at both endpoints, so level and slope are continuous across the transition.

---

### Voice Lifecycle and Retrigger Logic

The mixer tracks voices in a `dict[note → OrganVoice]`. When a `NOTE_ON` arrives:

1. **Voice already sustaining** → ignore (the valve is already open)
2. **Voice in release** → call `retrigger()` on the existing voice (preserves oscillator phases)
3. **Voice fully dead or absent** → create a new `OrganVoice`
   - If re-struck within **500 ms** of its last release → `suppress_transients=True` (no chiff, no tracker click)
   - Otherwise → full transients on the new voice

Timing uses a **sample clock** (integer counter incremented each render call) rather than `time.monotonic()`, avoiding syscalls inside the real-time audio callback.

---

### Polyphonic Mixer and Normalization

The mixer sums all active voice outputs into a mono buffer. Raw summing causes clipping when many notes play simultaneously, so a **gain normalization** of `1/√N` is applied (equal-power mixing).

A naive implementation applies this as a hard scalar per block — causing an audible amplitude pop the instant a new note is pressed (going from `1/√1 = 1.0` to `1/√2 ≈ 0.707` is a 30% jump in one sample). Instead, the gain is **linearly ramped** from the previous value to the new target across the entire block (~93 ms), making voice count transitions completely inaudible.

---

### Cathedral Reverb

The reverb is a stereo pair of **Schroeder reverb** networks, one per channel, with different room sizes and delay line lengths to create a wide stereo image.

Each channel is a `CathedralReverb`:
- **Pre-delay buffer** — adds 18–48 ms of initial silence before the reverb tail, creating the perceptual impression of room depth
- **7 parallel comb filters** — each a delay line with damped feedback, simulating distinct reflections; their outputs are summed
- **4 series allpass filters** — diffuse the comb outputs into a smooth, dense tail

The two channels use prime-offset delay times so their reflections never coincide, which would collapse the stereo image to mono. Feedback coefficients of 0.82–0.92 produce RT60s of 2–5+ seconds depending on the preset.

---

### Real-Time Architecture

The audio is produced in a `sounddevice` callback running on a dedicated OS audio thread. The callback asks the `Mixer` to render exactly `N` frames (default 4096 at 44100 Hz — a ~93 ms budget) before the sound card needs them.

All communication between the GUI thread and the audio thread goes through a `SimpleQueue` of `AudioEvent` objects (note-on/off, drawbar changes, stop toggles, room preset changes). The queue is drained at the start of each render call — zero locks, zero blocking.

All signal processing is **fully vectorized with numpy**: no per-sample Python loops anywhere in the audio path. Profiling shows the render fits in ~45 ms average for 8 voices (49% of the 93 ms budget), leaving ample headroom for GUI activity.

---

## License

MIT
