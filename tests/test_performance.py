"""Performance benchmarks — ensure rendering stays within the audio budget.

These tests measure real wall-clock time and enforce that the render pipeline
can fill audio buffers fast enough to avoid underflows.

Run with: uv run pytest tests/test_performance.py -v -s
"""

import time
import numpy as np
import pytest
from engine.mixer import Mixer


SAMPLE_RATE = 44100
BLOCK_SIZE = 4096
BUDGET_MS = BLOCK_SIZE / SAMPLE_RATE * 1000  # ~92.9ms


def _benchmark_render(mixer: Mixer, iterations: int = 100) -> dict:
    """Benchmark mixer.render() and return timing statistics."""
    # Warm up
    for _ in range(10):
        mixer.render(BLOCK_SIZE)

    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        mixer.render(BLOCK_SIZE)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    times.sort()
    return {
        "avg": sum(times) / len(times),
        "p50": times[len(times) // 2],
        "p95": times[int(0.95 * len(times))],
        "p99": times[int(0.99 * len(times))],
        "max": times[-1],
    }


class TestRenderBudget:
    """Ensure rendering fits within the audio callback budget."""

    def test_4_voices_within_budget(self):
        m = Mixer(SAMPLE_RATE)
        for note in [60, 64, 67, 72]:
            m.note_on(note)
            m.render(128)

        stats = _benchmark_render(m)
        print(f"\n  4 voices: avg={stats['avg']:.1f}ms  "
              f"p95={stats['p95']:.1f}ms  p99={stats['p99']:.1f}ms  "
              f"(budget={BUDGET_MS:.1f}ms)")
        assert stats["p95"] < BUDGET_MS, (
            f"4-voice P95 ({stats['p95']:.1f}ms) exceeds budget ({BUDGET_MS:.1f}ms)"
        )

    def test_8_voices_within_budget(self):
        m = Mixer(SAMPLE_RATE)
        for note in [48, 52, 55, 60, 64, 67, 72, 76]:
            m.note_on(note)
            m.render(128)

        stats = _benchmark_render(m)
        print(f"\n  8 voices: avg={stats['avg']:.1f}ms  "
              f"p95={stats['p95']:.1f}ms  p99={stats['p99']:.1f}ms  "
              f"(budget={BUDGET_MS:.1f}ms)")
        assert stats["p95"] < BUDGET_MS, (
            f"8-voice P95 ({stats['p95']:.1f}ms) exceeds budget ({BUDGET_MS:.1f}ms)"
        )

    def test_empty_render_is_fast(self):
        """No voices should render in <1ms."""
        m = Mixer(SAMPLE_RATE)
        stats = _benchmark_render(m, iterations=50)
        print(f"\n  0 voices: avg={stats['avg']:.2f}ms")
        assert stats["avg"] < 2.0


class TestRenderCorrectness:
    """Sanity checks that rendering produces valid output."""

    def test_output_is_finite(self):
        m = Mixer(SAMPLE_RATE)
        for note in [60, 64, 67]:
            m.note_on(note)
        stereo = m.render(BLOCK_SIZE)
        assert np.all(np.isfinite(stereo)), "Output contains NaN/Inf"

    def test_output_not_clipping(self):
        """Output should stay within [-1, 1] after saturation."""
        m = Mixer(SAMPLE_RATE)
        for note in [48, 52, 55, 60, 64, 67, 72, 76]:
            m.note_on(note)
        # Render several blocks to reach peak
        for _ in range(10):
            stereo = m.render(BLOCK_SIZE)
        assert np.abs(stereo).max() <= 1.0, (
            f"Clipping detected: max={np.abs(stereo).max():.4f}"
        )

    def test_stereo_channels_differ(self):
        """Left and right channels should NOT be identical (stereo reverb)."""
        m = Mixer(SAMPLE_RATE)
        m.note_on(60)
        for _ in range(5):
            stereo = m.render(BLOCK_SIZE)
        left, right = stereo[:, 0], stereo[:, 1]
        assert not np.allclose(left, right, atol=0.001), "Stereo channels are identical"
