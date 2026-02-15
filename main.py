"""Organum — Pipe Organ Synthesizer

Entry point: creates audio engine, mixer, MIDI player, and GUI.
"""

import sys
from PyQt6.QtWidgets import QApplication
from engine.mixer import Mixer
from engine.audio import AudioEngine, SAMPLE_RATE
from engine.midi_player import MidiPlayer
from gui.main_window import MainWindow


def main() -> None:
    mixer = Mixer(sample_rate=SAMPLE_RATE)
    audio = AudioEngine(mixer)
    midi_player = MidiPlayer(mixer)

    audio.start()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(mixer, midi_player)
    window.show()

    try:
        exit_code = app.exec()
    finally:
        midi_player.stop()
        audio.stop()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
