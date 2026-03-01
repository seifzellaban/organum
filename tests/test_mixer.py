"""Tests for the Mixer — normalization, rapid re-strikes, voice management."""

import numpy as np
import pytest
from engine.mixer import Mixer


class TestSmoothNormalization:
    """Verify gain ramp prevents clicks when voice count changes."""

    def test_single_voice_no_normalization(self):
        """One voice should play at full gain (1.0)."""
        m = Mixer(44100)
        m.note_on(60)
        m.render(4096)
        assert m._norm_gain == pytest.approx(1.0)

    def test_two_voices_normalized(self):
        """Two voices should target 1/sqrt(2) gain."""
        m = Mixer(44100)
        m.note_on(60)
        m.render(4096)
        m.note_on(64)
        m.render(4096)
        assert m._norm_gain == pytest.approx(1.0 / np.sqrt(2), abs=0.01)

    def test_normalization_transition_is_smooth(self):
        """Going from 1 to 2 voices should NOT cause a pop at the block boundary."""
        m = Mixer(44100)
        m.note_on(60)

        # Build to sustain over several blocks
        for _ in range(5):
            block_before = m.render(4096)

        # Press second note
        m.note_on(64)
        block_transition = m.render(4096)

        # Check boundary between blocks
        last_left = block_before[-1, 0]
        first_left = block_transition[0, 0]
        jump = abs(first_left - last_left)
        signal = max(abs(last_left), abs(first_left), 0.001)
        relative_jump = jump / signal

        # Should not have a >20% jump (old code had ~30%)
        assert relative_jump < 0.20, (
            f"Pop at boundary: {relative_jump*100:.1f}% jump "
            f"(last={last_left:.4f}, first={first_left:.4f})"
        )


class TestRapidRestrikes:
    """Verify transient suppression on same-key rapid re-strikes."""

    def test_rapid_restrike_suppresses_transients(self):
        """Re-striking within 500ms should suppress chiff/tracker click."""
        m = Mixer(44100)
        m.note_on(60)
        m.render(4096)

        m.note_off(60)
        m.render(4096)  # Short release

        # Re-strike — should be within restrike window
        m.note_on(60)
        m.render(128)  # Process the event

        # The new voice should exist and have suppressed transients
        voice = m._voices.get(60)
        assert voice is not None
        assert voice._chiff_samples_left == 0, "Chiff should be suppressed"
        assert voice._tracker_click_left == 0, "Tracker click should be suppressed"

    def test_slow_restrike_has_transients(self):
        """Re-striking after >500ms should include normal transients."""
        m = Mixer(44100)
        m.note_on(60)
        m.render(4096)
        m.note_off(60)

        # Advance past the 500ms window AND let the voice fully decay + cleanup
        for _ in range(50):
            m.render(4096)  # ~4.6 seconds total — voice fully dead and cleaned up

        assert 60 not in m._voices, "Voice should be cleaned up by now"

        m.note_on(60)
        m.render(128)

        voice = m._voices.get(60)
        assert voice is not None
        assert voice._chiff_samples_left > 0, "Fresh strike should have chiff"

    def test_retrigger_during_release(self):
        """Re-striking while voice is still releasing should retrigger, not create new."""
        m = Mixer(44100)
        m.note_on(60)
        m.render(4096)
        m.note_off(60)
        m.render(500)  # Very short release — voice still active

        voice_before = m._voices.get(60)
        assert voice_before is not None
        assert voice_before.is_releasing

        m.note_on(60)
        m.render(128)

        # Should be the SAME voice object (retriggered, not recreated)
        voice_after = m._voices.get(60)
        assert voice_after is voice_before


class TestVoiceManagement:
    """Verify voice lifecycle in the mixer."""

    def test_note_on_creates_voice(self):
        m = Mixer(44100)
        assert len(m._voices) == 0
        m.note_on(60)
        m.render(128)
        assert 60 in m._voices

    def test_note_off_starts_release(self):
        m = Mixer(44100)
        m.note_on(60)
        m.render(128)
        m.note_off(60)
        m.render(128)
        voice = m._voices.get(60)
        assert voice is not None
        assert voice.is_releasing

    def test_dead_voices_cleaned_up(self):
        m = Mixer(44100)
        m.note_on(60)
        m.render(128)
        m.note_off(60)
        # Render enough for full decay
        for _ in range(200):
            m.render(4096)
        assert 60 not in m._voices

    def test_stereo_output_shape(self):
        m = Mixer(44100)
        m.note_on(60)
        stereo = m.render(4096)
        assert stereo.shape == (4096, 2)
        assert stereo.dtype == np.float32

    def test_silence_when_no_voices(self):
        m = Mixer(44100)
        stereo = m.render(4096)
        assert stereo.shape == (4096, 2)
        # Should be near-silent (room resonance may add tiny sub-bass)
        assert np.abs(stereo).max() < 0.01
