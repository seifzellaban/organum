"""Real-time audio output via sounddevice.

Opens a low-latency OutputStream with a callback that pulls rendered
stereo audio from the Mixer each block.
"""

import numpy as np
import sounddevice as sd
from engine.mixer import Mixer


SAMPLE_RATE = 44100
BLOCK_SIZE = 4096  # ~93ms latency — headroom for stereo cathedral reverb


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

        # Mixer now returns stereo (num_frames, 2)
        stereo = self._mixer.render(frames)

        if stereo.ndim == 2 and stereo.shape[1] == 2:
            outdata[:] = stereo
        else:
            # Fallback: mono signal
            outdata[:, 0] = stereo.ravel()[:frames]
            if outdata.shape[1] > 1:
                outdata[:, 1] = stereo.ravel()[:frames]

    def start(self) -> None:
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=2,
            dtype="float32",
            callback=self._callback,
            latency="high",
        )
        self._stream.start()
        print(f"[audio] Stream started: {SAMPLE_RATE}Hz, {BLOCK_SIZE} frames/block, stereo")

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            print("[audio] Stream stopped")
