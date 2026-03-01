"""Tests for the ADSR envelope — smoothstep attack, gentle release, click-free retrigger."""

import numpy as np
import pytest
from engine.envelope import Envelope, Stage


# ── Attack curve tests ──────────────────────────────────────────────


class TestAttackCurve:
    """Verify the smoothstep attack starts and ends with zero slope."""

    def test_attack_starts_at_zero(self):
        env = Envelope(attack_ms=50)
        env.note_on()
        out = env.render(10)
        assert out[0] == pytest.approx(0.0, abs=0.001)

    def test_attack_ends_at_one(self):
        env = Envelope(attack_ms=50)
        env.note_on()
        attack_samples = int(50 * 44100 / 1000)
        out = env.render(attack_samples + 100)
        # Last sample of attack should be very close to 1.0
        assert out[attack_samples - 1] == pytest.approx(1.0, abs=0.01)

    def test_attack_midpoint_is_half(self):
        """Smoothstep reaches 0.5 at t=0.5 — linear feel in the middle."""
        env = Envelope(attack_ms=50)
        env.note_on()
        attack_samples = int(50 * 44100 / 1000)
        out = env.render(attack_samples)
        mid = attack_samples // 2
        assert out[mid] == pytest.approx(0.5, abs=0.05)

    def test_attack_onset_is_gentle(self):
        """First 20 samples should have very small per-sample jumps."""
        env = Envelope(attack_ms=50)
        env.note_on()
        out = env.render(100)
        diffs = np.abs(np.diff(out[:20]))
        # Smoothstep has zero derivative at t=0, so initial jumps should be tiny
        assert diffs.max() < 0.001, f"Harsh onset: max jump = {diffs.max()}"

    def test_attack_arrival_is_gentle(self):
        """Last 20 samples of attack should ease into peak (zero derivative at t=1)."""
        env = Envelope(attack_ms=50)
        env.note_on()
        attack_samples = int(50 * 44100 / 1000)
        out = env.render(attack_samples)
        diffs = np.abs(np.diff(out[-20:]))
        assert diffs.max() < 0.001, f"Harsh arrival: max jump = {diffs.max()}"

    def test_attack_is_monotonically_increasing(self):
        env = Envelope(attack_ms=50)
        env.note_on()
        out = env.render(int(50 * 44100 / 1000))
        diffs = np.diff(out)
        assert np.all(diffs >= -1e-6), "Attack curve should be monotonically increasing"


# ── Release curve tests ─────────────────────────────────────────────


class TestReleaseCurve:
    """Verify the exponential release is gentle and lingering."""

    def test_release_starts_at_sustain_level(self):
        env = Envelope(attack_ms=10, release_ms=750)
        env.note_on()
        env.render(5000)  # Get past attack+decay to sustain
        env.note_off()
        release = env.render(100)
        # First sample should be very close to sustain level
        assert release[0] == pytest.approx(env._sustain_level, abs=0.02)

    def test_release_onset_is_smooth(self):
        """No click at the moment of note-off."""
        env = Envelope(attack_ms=10, release_ms=750)
        env.note_on()
        sustain = env.render(5000)
        env.note_off()
        release = env.render(100)
        # Check transition between sustain and release
        boundary_jump = abs(release[0] - sustain[-1])
        assert boundary_jump < 0.005, f"Click at note-off: jump = {boundary_jump}"

    def test_release_reaches_50_pct_slowly(self):
        """50% decay should take at least 300ms — not a sudden cutoff."""
        env = Envelope(attack_ms=10, release_ms=750)
        env.note_on()
        env.render(5000)
        start_level = env._level
        env.note_off()
        release = env.render(44100)  # 1 second
        half_idx = np.argmax(release < start_level * 0.5)
        half_ms = half_idx / 44100 * 1000
        assert half_ms > 300, f"50% decay too fast: {half_ms:.0f}ms (want >300ms)"

    def test_release_is_monotonically_decreasing(self):
        env = Envelope(attack_ms=10, release_ms=750)
        env.note_on()
        env.render(5000)
        env.note_off()
        release = env.render(20000)
        diffs = np.diff(release)
        assert np.all(diffs <= 1e-6), "Release should be monotonically decreasing"

    def test_release_eventually_goes_idle(self):
        env = Envelope(attack_ms=10, release_ms=750)
        env.note_on()
        env.render(5000)
        env.note_off()
        # Render enough to fully decay
        env.render(44100 * 5)  # 5 seconds
        assert env._stage == Stage.IDLE
        assert env._level == 0.0


# ── Retrigger tests ─────────────────────────────────────────────────


class TestRetrigger:
    """Verify click-free retrigger via smooth crossfade to sustain."""

    def test_retrigger_during_release_is_smooth(self):
        """Re-striking while releasing should not click."""
        env = Envelope(attack_ms=30, release_ms=750)
        env.note_on()
        env.render(5000)
        env.note_off()
        release_tail = env.render(200)  # Short release

        env.retrigger()
        retrigger_start = env.render(1000)

        # Check transition smoothness
        transition = np.concatenate([release_tail[-5:], retrigger_start[:5]])
        diffs = np.abs(np.diff(transition))
        assert diffs.max() < 0.01, f"Click at retrigger: max jump = {diffs.max()}"

    def test_retrigger_reaches_sustain(self):
        """After retrigger, envelope should reach sustain level."""
        env = Envelope(attack_ms=30, release_ms=750)
        env.note_on()
        env.render(5000)
        env.note_off()
        env.render(200)
        env.retrigger()
        env.render(2000)  # 15ms retrigger ramp + some sustain
        assert env._stage == Stage.SUSTAIN
        assert env._level == pytest.approx(0.92, abs=0.01)

    def test_retrigger_uses_retrigger_stage(self):
        """Retrigger should enter RETRIGGER stage, not ATTACK."""
        env = Envelope(attack_ms=30, release_ms=750)
        env.note_on()
        env.render(5000)
        env.note_off()
        env.render(200)
        env.retrigger()
        assert env._stage == Stage.RETRIGGER

    def test_retrigger_from_idle_is_smooth(self):
        """Retriggering a fully dead envelope should also be smooth."""
        env = Envelope(attack_ms=30, release_ms=750)
        env.note_on()
        env.render(5000)
        env.note_off()
        env.render(44100 * 5)  # Fully decay
        assert env._stage == Stage.IDLE

        env.retrigger()
        out = env.render(1000)
        # Should ramp from 0 to sustain smoothly
        diffs = np.abs(np.diff(out[:50]))
        assert diffs.max() < 0.01


# ── Stage transition tests ──────────────────────────────────────────


class TestStageTransitions:
    """Verify the full ADSR lifecycle."""

    def test_full_lifecycle(self):
        env = Envelope(attack_ms=20, decay_ms=30, sustain=0.85, release_ms=500)
        assert env._stage == Stage.IDLE

        env.note_on()
        assert env._stage == Stage.ATTACK

        # Through attack
        env.render(int(20 * 44.1) + 50)
        assert env._stage in (Stage.DECAY, Stage.SUSTAIN)

        # Through decay to sustain
        env.render(int(30 * 44.1) + 50)
        assert env._stage == Stage.SUSTAIN
        assert env._level == pytest.approx(0.85, abs=0.02)

        # Release
        env.note_off()
        assert env._stage == Stage.RELEASE

        # Full decay
        env.render(44100 * 5)
        assert env._stage == Stage.IDLE

    def test_note_off_during_attack(self):
        """Releasing during attack should immediately enter release."""
        env = Envelope(attack_ms=100)
        env.note_on()
        env.render(1000)  # Partway through attack
        assert env._stage == Stage.ATTACK
        env.note_off()
        assert env._stage == Stage.RELEASE
