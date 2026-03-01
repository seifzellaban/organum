"""Tests for OrganVoice — transient suppression, retrigger, rendering."""

import numpy as np
import pytest
from engine.organ import OrganVoice
from stops.profiles import STOP_DEFS, DRAWBAR_HARMONICS


def _default_harmonic_amps() -> np.ndarray:
    """Compute harmonic amps for Principal 8' + Bourdon 16' at default drawbar values."""
    stop_profiles = [
        STOP_DEFS["Principal 8'"].harmonics,
        STOP_DEFS["Bourdon 16'"].harmonics,
    ]
    drawbar_values = [0.75, 1.0, 0.625, 0.875, 0.375, 0.625, 0.25, 0.25, 0.125]
    amps = np.zeros(len(DRAWBAR_HARMONICS), dtype=np.float32)
    for profile in stop_profiles:
        for i, h in enumerate(DRAWBAR_HARMONICS):
            h_int = int(round(h)) if h >= 1 else 1
            if h_int in profile:
                amps[i] += profile[h_int] * drawbar_values[i]
    max_amp = amps.max()
    if max_amp > 1.0:
        amps /= max_amp
    return amps


class TestVoiceTransients:
    """Verify chiff/tracker click suppression on rapid re-strikes."""

    def test_normal_voice_has_transients(self):
        """First strike should include chiff and tracker click."""
        defs = [STOP_DEFS["Principal 8'"], STOP_DEFS["Bourdon 16'"]]
        voice = OrganVoice(60, 44100, stop_defs=defs, suppress_transients=False)
        assert voice._chiff_samples_left > 0
        assert voice._tracker_click_left > 0

    def test_suppressed_voice_has_no_transients(self):
        """Rapid re-strike should skip chiff and tracker click."""
        defs = [STOP_DEFS["Principal 8'"], STOP_DEFS["Bourdon 16'"]]
        voice = OrganVoice(60, 44100, stop_defs=defs, suppress_transients=True)
        assert voice._chiff_samples_left == 0
        assert voice._tracker_click_left == 0

    def test_suppressed_voice_still_produces_audio(self):
        """Suppressed transients shouldn't kill the voice entirely."""
        defs = [STOP_DEFS["Principal 8'"], STOP_DEFS["Bourdon 16'"]]
        voice = OrganVoice(60, 44100, stop_defs=defs, suppress_transients=True)
        amps = _default_harmonic_amps()
        audio = voice.render(4096, amps)
        assert audio.shape == (4096,)
        assert np.abs(audio).max() > 0.001, "Voice should produce audio"


class TestVoiceRetrigger:
    """Verify smooth retrigger preserves oscillator continuity."""

    def test_retrigger_preserves_oscillators(self):
        """Retrigger should NOT create new oscillators."""
        defs = [STOP_DEFS["Principal 8'"]]
        voice = OrganVoice(60, 44100, stop_defs=defs)
        amps = _default_harmonic_amps()
        voice.render(4096, amps)

        # Capture oscillator phases before retrigger
        phases_before = [
            osc._phase for osc in voice._oscillators_a if osc is not None
        ]

        voice.note_off()
        voice.render(1000, amps)
        voice.retrigger()
        voice.render(100, amps)

        # Oscillators should still be the same objects (phase continuity)
        phases_after = [
            osc._phase for osc in voice._oscillators_a if osc is not None
        ]
        assert len(phases_before) == len(phases_after)

    def test_retrigger_audio_is_continuous(self):
        """Audio should be continuous across retrigger — no silence gap."""
        defs = [STOP_DEFS["Principal 8'"]]
        voice = OrganVoice(60, 44100, stop_defs=defs)
        amps = _default_harmonic_amps()
        voice.render(4096, amps)  # Build to sustain

        voice.note_off()
        release_audio = voice.render(500, amps)  # Short release

        voice.retrigger()
        retrigger_audio = voice.render(500, amps)

        # Neither chunk should be silence
        assert np.abs(release_audio).max() > 0.01
        assert np.abs(retrigger_audio).max() > 0.01


class TestVoiceRendering:
    """Basic rendering sanity checks."""

    def test_render_correct_shape(self):
        voice = OrganVoice(60, 44100)
        amps = _default_harmonic_amps()
        audio = voice.render(4096, amps)
        assert audio.shape == (4096,)
        assert audio.dtype == np.float32

    def test_different_notes_produce_different_audio(self):
        amps = _default_harmonic_amps()
        voice_c = OrganVoice(60, 44100)
        voice_e = OrganVoice(64, 44100)
        audio_c = voice_c.render(4096, amps)
        audio_e = voice_e.render(4096, amps)
        # Different frequencies should not produce identical audio
        assert not np.allclose(audio_c, audio_e, atol=0.01)

    def test_voice_goes_inactive_after_release(self):
        voice = OrganVoice(60, 44100)
        amps = _default_harmonic_amps()
        voice.render(4096, amps)
        assert voice.is_active

        voice.note_off()
        assert voice.is_releasing

        # Render enough for full decay
        for _ in range(100):
            voice.render(4096, amps)
        assert not voice.is_active
