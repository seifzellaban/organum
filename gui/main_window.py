"""Main window — assembles all panels: stops, drawbars, MIDI player, and keyboard."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QToolBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QAction, QIcon

from engine.mixer import Mixer
from engine.midi_player import MidiPlayer, PlayerState
from engine.recorder import Recorder
from stops.profiles import STOP_REGISTRY, DRAWBAR_LABELS
from gui.stop_panel import StopPanel
from gui.drawbars import DrawbarPanel
from gui.keyboard import PianoKeyboard
from gui.midi_panel import MidiPlayerPanel

import mido


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _note_name(midi: int) -> str:
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


class MainWindow(QMainWindow):
    """Top-level window for the Organum pipe organ synthesizer."""

    def __init__(self, mixer: Mixer, midi_player: MidiPlayer) -> None:
        super().__init__()
        self._mixer = mixer
        self._midi_player = midi_player
        self._midi_player.set_note_callback(self._on_playback_note)
        
        self._recorder = Recorder()
        self._current_sequence: mido.MidiFile | None = None
        self._playback_notes: set[int] = set()

        self.setWindowTitle("Organum — Pipe Organ Synthesizer")
        self.setMinimumWidth(850)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1208; }
            #CentralWidget { background-color: #1e1208; }
            QToolBar { background-color: #2a1a10; border-bottom: 1px solid #4a3a2a; spacing: 10px; padding: 4px; }
            QToolButton { background-color: #3a2a1a; color: #d4a574; border-radius: 4px; padding: 4px; font-weight: bold; }
            QToolButton:hover { background-color: #4a3a2a; }
            QToolButton:pressed { background-color: #5a4a3a; }
            QToolButton:checked { background-color: #5a4a3a; border: 1px solid #d4a574; }
        """)

        # ── Toolbar ─────────────────────────────────────────────────
        self._create_toolbar()

        central = QWidget()
        central.setObjectName("CentralWidget")
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
            list(STOP_REGISTRY.keys()), mixer.active_stop_names
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

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Recorder")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Record Action (Dynamic Toggle)
        self._record_action = QAction("● Record", self)
        self._record_action.triggered.connect(self._toggle_record)
        toolbar.addAction(self._record_action)

        # Play Action (Dynamic Toggle)
        self._play_action = QAction("▶ Play", self)
        self._play_action.triggered.connect(self._toggle_play)
        toolbar.addAction(self._play_action)

        # Loop Action
        self._loop_action = QAction("🔁 Loop", self)
        self._loop_action.setCheckable(True)
        self._loop_action.toggled.connect(self._on_loop_toggle)
        toolbar.addAction(self._loop_action)

        toolbar.addSeparator()

        # Save Action
        save_action = QAction("💾 Save", self)
        save_action.triggered.connect(self._on_save)
        toolbar.addAction(save_action)

        # Import Action
        import_action = QAction("📂 Import", self)
        import_action.triggered.connect(self._on_import)
        toolbar.addAction(import_action)
        
        # Status Label
        self._status_label = QLabel(" Ready ")
        self._status_label.setStyleSheet("color: #8a7a6a; margin-left: 10px;")
        toolbar.addWidget(self._status_label)

    def _toggle_record(self) -> None:
        if self._recorder.is_recording:
            self._finish_recording()
            self._record_action.setText("● Record")
        else:
            offset = 0.0
            if self._midi_player.state == PlayerState.PLAYING:
                 offset = self._midi_player.position
                 self._status_label.setText(" 🔴 Overdubbing... ")
                 self._status_label.setStyleSheet("color: #ff4444; margin-left: 10px; font-weight: bold;")
            else:
                 self._status_label.setText(" 🔴 Recording... ")
                 self._status_label.setStyleSheet("color: #ff4444; margin-left: 10px; font-weight: bold;")

            self._recorder.start(initial_offset=offset)
            self._record_action.setText("■ Stop Rec")

    def _toggle_play(self) -> None:
        if self._midi_player.state == PlayerState.PLAYING:
            # STOP PLAYBACK
            if self._recorder.is_recording:
                # If we stop playback while recording, we must stop recording too
                self._finish_recording()
                self._record_action.setText("● Record")
            
            self._midi_player.stop()
            self._play_action.setText("▶ Play")
            self._status_label.setText(" Stopped ")
            self._status_label.setStyleSheet("color: #8a7a6a; margin-left: 10px;")
        else:
            # START PLAYBACK
            if self._current_sequence:
                self._midi_player.play()
                self._play_action.setText("■ Stop")
                self._status_label.setText(" ▶ Playing Buffer ")
                self._status_label.setStyleSheet("color: #44ff44; margin-left: 10px;")
            elif self._midi_player.file_name: # Playing loaded file
                self._midi_player.play()
                self._play_action.setText("■ Stop")
                self._status_label.setText(f" ▶ Playing {self._midi_player.file_name} ")
                self._status_label.setStyleSheet("color: #44ff44; margin-left: 10px;")
            else:
                self._status_label.setText(" Nothing to play ")

    def _finish_recording(self) -> None:
        """Helper to stop recorder and merge sequences."""
        was_playing = (self._midi_player.state == PlayerState.PLAYING)
        self._recorder.stop()
        new_seq = self._recorder.get_midi_file()
        
        if new_seq:
            if was_playing and self._current_sequence:
                # Overdub: Add new track to existing sequence
                self._current_sequence.tracks.extend(new_seq.tracks)
                self._status_label.setText(" Added layer to Loop ")
            else:
                # New Recording: Replace sequence
                self._current_sequence = new_seq
                self._status_label.setText(" Recorded New Loop ")
            
            # Load the updated sequence into player (ready to play/loop)
            self._midi_player.load(self._current_sequence)
            self._status_label.setStyleSheet("color: #44ff44; margin-left: 10px;")
        else:
            self._status_label.setText(" Recording empty ")

    def _on_loop_toggle(self, checked: bool) -> None:
        self._midi_player.looping = checked
        state = "On" if checked else "Off"
        self._status_label.setText(f" Loop {state} ")

    def _on_save(self) -> None:
        # Support saving the CURRENT buffer (merged or not)
        if self._recorder.is_recording:
            self._finish_recording()
            self._record_action.setText("● Record")
            
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save MIDI Recording", "", "MIDI Files (*.mid)"
        )
        if filename:
            if not filename.endswith('.mid'):
                filename += '.mid'
            
            if self._current_sequence:
                try:
                    self._current_sequence.save(filename)
                    self._status_label.setText(f" Saved mix to {filename} ")
                    QMessageBox.information(self, "Saved", f"Recording saved to:\n{filename}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Error saving file: {e}")
            elif self._recorder.save(filename): # Fallback if no sequence but recorder has data?
                 self._status_label.setText(f" Saved to {filename} ")
                 QMessageBox.information(self, "Saved", f"Recording saved to:\n{filename}")
            else:
                 QMessageBox.warning(self, "Error", "No events to save.")

    def _on_import(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open MIDI File", "", "MIDI Files (*.mid *.midi)"
        )
        if filename:
            if self._midi_player.load(filename):
                self._current_sequence = self._midi_player._midi_file 
                self._status_label.setText(f" Loaded {filename} ")
                self._play_action.setText("▶ Play") 
            else:
                QMessageBox.warning(self, "Error", f"Failed to load {filename}")

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

    def _on_playback_note(self, note: int, state: bool) -> None:
        """Called by MidiPlayer when a note is played/stopped."""
        if state:
            self._playback_notes.add(note)
        else:
            self._playback_notes.discard(note)
        self._keyboard.set_highlighted_notes(self._playback_notes)

    def _on_note_on(self, note: int) -> None:
        self._mixer.note_on(note)
        if self._recorder.is_recording:
            self._recorder.record_event("note_on", note)

    def _on_note_off(self, note: int) -> None:
        self._mixer.note_off(note)
        if self._recorder.is_recording:
            self._recorder.record_event("note_off", note)

    def _on_drawbar_change(self, index: int, value: float) -> None:
        self._mixer.set_drawbar(index, value)

    def _on_stop_toggle(self, name: str, active: bool) -> None:
        self._mixer.toggle_stop(name)

    def keyPressEvent(self, event):
        self._keyboard.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self._keyboard.keyReleaseEvent(event)
