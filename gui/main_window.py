"""Main window — assembles all panels: stops, drawbars, MIDI player, and keyboard."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from engine.mixer import Mixer
from engine.midi_player import MidiPlayer
from stops.profiles import STOP_DEFS, DRAWBAR_LABELS
from gui.stop_panel import StopPanel
from gui.drawbars import DrawbarPanel
from gui.keyboard import PianoKeyboard
from gui.midi_panel import MidiPlayerPanel


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _note_name(midi: int) -> str:
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


class MainWindow(QMainWindow):
    """Top-level window for the Organum pipe organ synthesizer."""

    def __init__(self, mixer: Mixer, midi_player: MidiPlayer) -> None:
        super().__init__()
        self._mixer = mixer
        self._midi_player = midi_player

        self.setWindowTitle("Organum — Pipe Organ Synthesizer")
        self.setMinimumWidth(960)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1208; }
            QWidget { background-color: #1e1208; }
        """)

        central = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(16, 10, 16, 14)

        # ── Title ───────────────────────────────────────────────────
        title = QLabel("𝕺𝖗𝖌𝖆𝖓𝖚𝖒")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Serif", 26, QFont.Weight.Bold))
        title.setStyleSheet("color: #d4a574; margin-bottom: 2px;")
        layout.addWidget(title)

        subtitle = QLabel("Pipe Organ Synthesizer  ·  Keys: Z–M / Y–]  ·  Octave: ← →")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8a7a6a; font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(subtitle)

        # ── Stop panel ──────────────────────────────────────────────
        self._stop_panel = StopPanel(
            list(STOP_DEFS.keys()), mixer.active_stop_names
        )
        self._stop_panel.stop_toggled.connect(self._on_stop_toggle)
        layout.addWidget(self._stop_panel)

        # ── Drawbars ────────────────────────────────────────────────
        drawbar_row = QHBoxLayout()
        drawbar_row.addStretch()
        self._drawbar_panel = DrawbarPanel(DRAWBAR_LABELS, mixer.drawbar_values)
        self._drawbar_panel.drawbar_changed.connect(self._on_drawbar_change)
        drawbar_row.addWidget(self._drawbar_panel)
        drawbar_row.addStretch()
        layout.addLayout(drawbar_row)

        # ── MIDI Player ─────────────────────────────────────────────
        self._midi_panel = MidiPlayerPanel(midi_player)
        layout.addWidget(self._midi_panel)

        # ── Octave controls + Keyboard ──────────────────────────────
        octave_row = QHBoxLayout()
        octave_row.addStretch()

        self._oct_down_btn = QPushButton("◀  Oct −")
        self._oct_down_btn.setFixedSize(90, 32)
        self._oct_down_btn.setStyleSheet(self._oct_btn_style())
        self._oct_down_btn.clicked.connect(lambda: self._keyboard.shift_octave(-1))
        octave_row.addWidget(self._oct_down_btn)

        self._octave_label = QLabel("")
        self._octave_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._octave_label.setFixedWidth(160)
        self._octave_label.setStyleSheet(
            "color: #ffd700; font-size: 14px; font-weight: bold;"
        )
        octave_row.addWidget(self._octave_label)

        self._oct_up_btn = QPushButton("Oct +  ▶")
        self._oct_up_btn.setFixedSize(90, 32)
        self._oct_up_btn.setStyleSheet(self._oct_btn_style())
        self._oct_up_btn.clicked.connect(lambda: self._keyboard.shift_octave(1))
        octave_row.addWidget(self._oct_up_btn)

        octave_row.addStretch()
        layout.addLayout(octave_row)

        # Keyboard
        kb_row = QHBoxLayout()
        kb_row.addStretch()
        self._keyboard = PianoKeyboard(base_note=48)
        self._keyboard.note_on.connect(self._on_note_on)
        self._keyboard.note_off.connect(self._on_note_off)
        self._keyboard.octave_changed.connect(self._update_octave_label)
        kb_row.addWidget(self._keyboard)
        kb_row.addStretch()
        layout.addLayout(kb_row)

        layout.addStretch()

        central.setLayout(layout)
        self.setCentralWidget(central)

        # Initialize octave label
        self._update_octave_label(self._keyboard.base_note)

        # Give keyboard focus
        self._keyboard.setFocus()

    def _oct_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #3a2a1a;
                color: #d4a574;
                border: 1px solid #5a4a3a;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #4a3a2a; border-color: #d4a574; }
            QPushButton:pressed { background-color: #5a4a3a; }
        """

    def _update_octave_label(self, base_note: int) -> None:
        low = _note_name(base_note)
        high = _note_name(base_note + 23)
        self._octave_label.setText(f"🎹  {low} — {high}")

    def _on_note_on(self, note: int) -> None:
        self._mixer.note_on(note)

    def _on_note_off(self, note: int) -> None:
        self._mixer.note_off(note)

    def _on_drawbar_change(self, index: int, value: float) -> None:
        self._mixer.set_drawbar(index, value)

    def _on_stop_toggle(self, name: str, active: bool) -> None:
        self._mixer.toggle_stop(name)

    def keyPressEvent(self, event):
        self._keyboard.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self._keyboard.keyReleaseEvent(event)
