"""MIDI player panel — file picker, transport controls, tempo slider."""

from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QSlider, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from engine.midi_player import MidiPlayer, PlayerState


BTN_STYLE = """
    QPushButton {
        background-color: #3a2a1a;
        color: #e0d4c0;
        border: 1px solid #5a4a3a;
        border-radius: 4px;
        font-size: 13px;
        font-weight: bold;
        padding: 6px 14px;
    }
    QPushButton:hover { background-color: #4a3a2a; }
    QPushButton:pressed { background-color: #5a4a3a; }
"""

BTN_ACTIVE = """
    QPushButton {
        background-color: #6b8e23;
        color: #fff8e7;
        border: 1px solid #8fbc3a;
        border-radius: 4px;
        font-size: 13px;
        font-weight: bold;
        padding: 6px 14px;
    }
    QPushButton:hover { background-color: #7b9e33; }
"""


class MidiPlayerPanel(QGroupBox):
    """MIDI file transport controls and tempo slider."""

    def __init__(self, midi_player: MidiPlayer) -> None:
        super().__init__("MIDI Player")
        self._player = midi_player

        layout = QVBoxLayout()
        layout.setSpacing(8)

        # File row
        file_row = QHBoxLayout()
        self._file_label = QLabel("No file loaded")
        self._file_label.setStyleSheet("color: #a09080; font-size: 12px;")
        file_row.addWidget(self._file_label, 1)

        self._open_btn = QPushButton("📂 Open MIDI")
        self._open_btn.setStyleSheet(BTN_STYLE)
        self._open_btn.clicked.connect(self._on_open)
        file_row.addWidget(self._open_btn)
        layout.addLayout(file_row)

        # Transport row
        transport = QHBoxLayout()

        self._play_btn = QPushButton("▶ Play")
        self._play_btn.setStyleSheet(BTN_STYLE)
        self._play_btn.clicked.connect(self._on_play)
        transport.addWidget(self._play_btn)

        self._pause_btn = QPushButton("⏸ Pause")
        self._pause_btn.setStyleSheet(BTN_STYLE)
        self._pause_btn.clicked.connect(self._on_pause)
        transport.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setStyleSheet(BTN_STYLE)
        self._stop_btn.clicked.connect(self._on_stop)
        transport.addWidget(self._stop_btn)

        # Tempo
        transport.addSpacing(16)
        tempo_label = QLabel("Tempo:")
        tempo_label.setStyleSheet("color: #c0b0a0; font-size: 12px;")
        transport.addWidget(tempo_label)

        self._tempo_slider = QSlider(Qt.Orientation.Horizontal)
        self._tempo_slider.setMinimum(25)
        self._tempo_slider.setMaximum(200)
        self._tempo_slider.setValue(100)
        self._tempo_slider.setFixedWidth(120)
        self._tempo_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2a1a0a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #d4a574;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)
        self._tempo_slider.valueChanged.connect(self._on_tempo_change)
        transport.addWidget(self._tempo_slider)

        self._tempo_label = QLabel("1.0×")
        self._tempo_label.setStyleSheet("color: #ffd700; font-size: 12px; font-weight: bold;")
        self._tempo_label.setFixedWidth(40)
        transport.addWidget(self._tempo_label)

        layout.addLayout(transport)

        # Status row
        self._status_label = QLabel("Stopped")
        self._status_label.setStyleSheet("color: #8a7a6a; font-size: 11px;")
        layout.addWidget(self._status_label)

        self.setLayout(layout)
        self.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: #e0d4c0;
                border: 1px solid #5a4a3a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)

        # Status update timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_status)
        self._timer.start(200)

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MIDI File", "", "MIDI Files (*.mid *.midi);;All Files (*)"
        )
        if path:
            if self._player.load(path):
                self._file_label.setText(f"📄 {self._player.file_name}")
                self._status_label.setText(
                    f"Loaded — {self._player.duration:.1f}s"
                )
            else:
                self._file_label.setText("⚠ Failed to load")

    def _on_play(self) -> None:
        self._player.play()

    def _on_pause(self) -> None:
        self._player.pause()

    def _on_stop(self) -> None:
        self._player.stop()

    def _on_tempo_change(self, value: int) -> None:
        multiplier = value / 100.0
        self._player.tempo_multiplier = multiplier
        self._tempo_label.setText(f"{multiplier:.1f}×")

    def _update_status(self) -> None:
        state = self._player.state
        if state == PlayerState.PLAYING:
            pos = self._player.position
            dur = self._player.duration
            self._status_label.setText(
                f"▶ Playing — {pos:.1f}s / {dur:.1f}s"
            )
            self._play_btn.setStyleSheet(BTN_ACTIVE)
        elif state == PlayerState.PAUSED:
            self._status_label.setText("⏸ Paused")
            self._play_btn.setStyleSheet(BTN_STYLE)
        else:
            self._status_label.setText("⏹ Stopped")
            self._play_btn.setStyleSheet(BTN_STYLE)
