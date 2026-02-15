"""Real-time audio output via sounddevice.

Opens a low-latency OutputStream with a callback that pulls rendered audio
from the Mixer each block.
"""

import numpy as np
import sounddevice as sd
from engine.mixer import Mixer


SAMPLE_RATE = 44100
BLOCK_SIZE = 2048  # ~46ms latency — provides headroom for cathedral reverb + voicing


class AudioEngine:
    """Manages the sounddevice output stream."""

    def __init__(self, mixer: Mixer) -> None:
        self._mixer = mixer
        self._stream: sd.OutputStream | None = None

    def _callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            print(f"[audio] {status}")

        audio = self._mixer.render(frames)
        outdata[:, 0] = audio
        if outdata.shape[1] > 1:
            outdata[:, 1] = audio

    def start(self) -> None:
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=2,
            dtype="float32",
            callback=self._callback,
            latency="low",
        )
        self._stream.start()
        print(f"[audio] Stream started: {SAMPLE_RATE}Hz, {BLOCK_SIZE} frames/block")

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            print("[audio] Stream stopped")
