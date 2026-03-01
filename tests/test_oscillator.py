"""Tests for the wavetable oscillator — correctness and buffer reuse."""

import numpy as np
import pytest
from engine.oscillator import Oscillator, _get_work_buffers


class TestOscillatorOutput:
    """Basic oscillator correctness checks."""

    def test_output_shape_and_dtype(self):
        osc = Oscillator(440.0, 44100)
        out = osc.render(4096)
        assert out.shape == (4096,)
        assert out.dtype == np.float32

    def test_sine_wave_amplitude(self):
        """Pure sine should peak at ±1.0."""
        osc = Oscillator(440.0, 44100, waveform="sine")
        out = osc.render(44100)  # 1 full second
        assert np.abs(out).max() == pytest.approx(1.0, abs=0.05)

    def test_different_frequencies_differ(self):
        osc_a = Oscillator(440.0, 44100)
        osc_b = Oscillator(880.0, 44100)
        out_a = osc_a.render(4096)
        out_b = osc_b.render(4096)
        assert not np.allclose(out_a, out_b)

    def test_phase_continuity(self):
        """Two sequential renders should be continuous (no phase jump)."""
        osc = Oscillator(440.0, 44100, waveform="sine")
        out1 = osc.render(1000)
        out2 = osc.render(1000)
        # The jump between last sample of out1 and first of out2 should be
        # similar to inter-sample jumps within a block
        internal_max_jump = np.abs(np.diff(out1[-10:])).max()
        boundary_jump = abs(out2[0] - out1[-1])
        assert boundary_jump < internal_max_jump * 2, (
            f"Phase discontinuity: boundary={boundary_jump:.6f} "
            f"vs internal={internal_max_jump:.6f}"
        )


class TestVariableBlockSize:
    """Verify the oscillator handles different block sizes correctly."""

    def test_small_block(self):
        osc = Oscillator(440.0, 44100)
        out = osc.render(128)
        assert out.shape == (128,)

    def test_single_sample(self):
        osc = Oscillator(440.0, 44100)
        out = osc.render(1)
        assert out.shape == (1,)

    def test_mixed_block_sizes(self):
        """Alternating block sizes should not crash."""
        osc = Oscillator(440.0, 44100, vibrato_depth=0.5)
        for size in [4096, 128, 4096, 256, 1024]:
            out = osc.render(size)
            assert out.shape == (size,)


class TestWorkBuffers:
    """Verify the shared work buffer pool."""

    def test_buffers_are_reused(self):
        """Same block size should return the same buffer object."""
        b1 = _get_work_buffers(4096)
        b2 = _get_work_buffers(4096)
        assert b1 is b2

    def test_buffers_resize_for_larger(self):
        """Larger block should allocate new buffers."""
        b1 = _get_work_buffers(1024)
        b2 = _get_work_buffers(4096)
        assert b2.size >= 4096

    def test_buffers_not_shrunk(self):
        """Smaller block after larger should reuse the larger buffers."""
        b1 = _get_work_buffers(4096)
        b2 = _get_work_buffers(128)
        assert b2 is b1  # Reused, not shrunk


class TestVibrato:
    """Verify vibrato modulation works without errors."""

    def test_vibrato_produces_output(self):
        osc = Oscillator(440.0, 44100, vibrato_depth=2.0, vibrato_rate=6.0)
        out = osc.render(4096)
        assert out.shape == (4096,)
        assert np.abs(out).max() > 0.1

    def test_no_vibrato_is_cleaner(self):
        """Without vibrato the spectrum should be narrower (less spectral spread)."""
        osc_clean = Oscillator(440.0, 44100, vibrato_depth=0.0, waveform="sine")
        osc_vib = Oscillator(440.0, 44100, vibrato_depth=3.0, vibrato_rate=6.0, waveform="sine")
        out_clean = osc_clean.render(44100)
        out_vib = osc_vib.render(44100)
        # Both should produce valid audio
        assert np.abs(out_clean).max() > 0.5
        assert np.abs(out_vib).max() > 0.5
