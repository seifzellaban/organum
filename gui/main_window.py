"""Main window — assembles all panels: stops, drawbars, MIDI player, and keyboard.

ALL keyboard input is intercepted at the window level via an event filter
and routed exclusively to the PianoKeyboard. No other widget ever receives
keyboard focus or key events. This prevents Qt's accessibility system
(Tab navigation, Space to toggle buttons, arrow keys on sliders) from
interfering with organ controls.

Controls:
  Numpad 0     All stops on
  Numpad 1–9   Stop group presets
  Shift+Num1–9 Select drawbar, then ↑/↓ to adjust
  ←/→          Move both hands
  LCtrl + ←/→  Move left hand only
  RCtrl + ←/→  Move right hand only
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QApplication,
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QFont, QKeyEvent

from engine.mixer import Mixer, ROOM_PRESETS, DEFAULT_ROOM_PRESET
from engine.midi_player import MidiPlayer
from stops.profiles import STOP_DEFS, DRAWBAR_LABELS
from gui.stop_panel import StopPanel
from gui.drawbars import DrawbarPanel
from gui.keyboard import PianoKeyboard
from gui.midi_panel import MidiPlayerPanel
from gui.room_panel import RoomPresetPanel
from gui.drawbar_presets import DrawbarPresetPanel


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _note_name(midi: int) -> str:
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


# ── Stop group presets ──────────────────────────────────────────────
# Each group is a set of stop names to activate (all others deactivated).
# These follow traditional organ registration patterns.
STOP_GROUPS: dict[int, tuple[str, list[str]]] = {
    0: ("All Stops", list(STOP_DEFS.keys())),
    1: ("Foundation", ["Principal 8'", "Bourdon 16'"]),
    2: ("Plenum", ["Principal 8'", "Octave 4'", "Super Oct 2'", "Mixture"]),
    3: ("Flutes", ["Flute 8'", "Gedackt 8'", "Bourdon 16'"]),
    4: ("Reeds", ["Reed 8'", "Trumpet 8'"]),
    5: ("Solo Reed", ["Trumpet 8'"]),
    6: ("Strings", ["Vox Celeste", "Voix Humaine"]),
    7: ("Full Swell", ["Principal 8'", "Flute 8'", "Octave 4'", "Reed 8'", "Vox Celeste", "Tremulant"]),
    8: ("Cathedral", ["Principal 8'", "Bourdon 16'", "Octave 4'", "Super Oct 2'", "Mixture", "Trumpet 8'"]),
    9: ("Ethereal", ["Flute 8'", "Gedackt 8'", "Vox Celeste", "Voix Humaine", "Tremulant"]),
}


def _disable_focus_recursive(widget: QWidget) -> None:
    """Set NoFocus on every child widget to prevent keyboard stealing."""
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    for child in widget.findChildren(QWidget):
        child.setFocusPolicy(Qt.FocusPolicy.NoFocus)


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

        subtitle = QLabel(
            "Keys: Z–M (left hand) / Y–] (right hand)  ·  "
            "← → Octave  ·  LCtrl/RCtrl + ← → per hand  ·  "
            "Numpad: stop groups  ·  Shift+Num: drawbars"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8a7a6a; font-size: 11px; margin-bottom: 4px;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # ── Stop panel ──────────────────────────────────────────────
        self._stop_panel = StopPanel(
            list(STOP_DEFS.keys()), mixer.active_stop_names
        )
        self._stop_panel.stop_toggled.connect(self._on_stop_toggle)
        layout.addWidget(self._stop_panel)

        # ── Drawbar presets + Drawbars + Room presets ────────────────
        drawbar_row = QHBoxLayout()
        drawbar_row.addStretch()

        # Drawbar presets — left of drawbars
        self._drawbar_preset_panel = DrawbarPresetPanel()
        self._drawbar_preset_panel.preset_selected.connect(self._on_drawbar_preset)
        drawbar_row.addWidget(self._drawbar_preset_panel)

        # Drawbars (center)
        self._drawbar_panel = DrawbarPanel(DRAWBAR_LABELS, mixer.drawbar_values)
        self._drawbar_panel.drawbar_changed.connect(self._on_drawbar_change)
        drawbar_row.addWidget(self._drawbar_panel)

        # Room presets — right of drawbars
        self._room_panel = RoomPresetPanel(
            list(ROOM_PRESETS.keys()),
            mixer.current_room_preset,
        )
        self._room_panel.room_selected.connect(self._on_room_selected)
        drawbar_row.addWidget(self._room_panel)

        drawbar_row.addStretch()
        layout.addLayout(drawbar_row)

        # ── MIDI Player ─────────────────────────────────────────────
        self._midi_panel = MidiPlayerPanel(midi_player)
        layout.addWidget(self._midi_panel)

        # ── Status row: octave + stop group + drawbar info ──────────
        status_row = QHBoxLayout()
        status_row.setSpacing(20)

        self._octave_label = QLabel("")
        self._octave_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._octave_label.setStyleSheet(
            "color: #ffd700; font-size: 13px; font-weight: bold;"
        )
        status_row.addWidget(self._octave_label, 1)

        self._group_label = QLabel("Group: —")
        self._group_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._group_label.setStyleSheet(
            "color: #77bbff; font-size: 12px; font-weight: bold;"
        )
        status_row.addWidget(self._group_label, 1)

        self._drawbar_select_label = QLabel("Drawbar: —")
        self._drawbar_select_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drawbar_select_label.setStyleSheet(
            "color: #ffaa55; font-size: 12px; font-weight: bold;"
        )
        status_row.addWidget(self._drawbar_select_label, 1)

        layout.addLayout(status_row)

        # ── Keyboard ───────────────────────────────────────────────
        kb_row = QHBoxLayout()
        kb_row.addStretch()
        self._keyboard = PianoKeyboard(base_note=48)
        self._keyboard.note_on.connect(self._on_note_on)
        self._keyboard.note_off.connect(self._on_note_off)
        self._keyboard.octave_changed.connect(self._update_octave_label)
        self._keyboard.hands_changed.connect(self._update_hands_label)
        self._keyboard.stop_group_selected.connect(self._on_stop_group)
        self._keyboard.drawbar_selected.connect(self._on_drawbar_selected)
        self._keyboard.drawbar_adjust.connect(self._on_drawbar_adjust)
        kb_row.addWidget(self._keyboard)
        kb_row.addStretch()
        layout.addLayout(kb_row)

        layout.addStretch()

        central.setLayout(layout)
        self.setCentralWidget(central)

        # ── Disable focus on ALL widgets except the keyboard ────────
        # This prevents buttons, sliders, etc. from stealing keyboard
        # input (Tab, Space, arrow keys, etc.)
        _disable_focus_recursive(central)
        self._keyboard.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._keyboard.setFocus()

        # ── Install application-wide event filter ───────────────────
        # Intercepts ALL key events before any widget sees them and
        # routes them directly to the piano keyboard.
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        # Initialize labels
        self._update_hands_label(self._keyboard.left_base, self._keyboard.right_base)

        # ── MIDI note visualization timer ───────────────────────────
        # Poll MIDI player's active notes and highlight them on keyboard
        from PyQt6.QtCore import QTimer
        self._midi_viz_timer = QTimer()
        self._midi_viz_timer.timeout.connect(self._update_midi_visualization)
        self._midi_viz_timer.start(50)  # 20fps — smooth enough for visual feedback

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Intercept ALL key events at the application level.

        Every KeyPress and KeyRelease is routed to the piano keyboard,
        bypassing Qt's normal focus/accessibility system entirely.
        """
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            key_event = event  # It's already a QKeyEvent
            if event.type() == QEvent.Type.KeyPress:
                self._keyboard.keyPressEvent(key_event)
            else:
                self._keyboard.keyReleaseEvent(key_event)
            return True  # Consumed — no widget sees it

        # For ShortcutOverride events (Qt trying to match shortcuts):
        # accept them to prevent Qt from consuming the key
        if event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True

        return super().eventFilter(obj, event)

    def _update_midi_visualization(self) -> None:
        """Poll MIDI player for active notes and highlight on keyboard."""
        notes = self._midi_player.active_notes
        self._keyboard.set_highlighted_notes(notes)

    def _update_octave_label(self, base_note: int) -> None:
        self._update_hands_label(self._keyboard.left_base, self._keyboard.right_base)

    def _update_hands_label(self, left_base: int, right_base: int) -> None:
        lh_low = _note_name(left_base)
        lh_high = _note_name(left_base + 11)
        rh_low = _note_name(right_base)
        rh_high = _note_name(right_base + 11)
        self._octave_label.setText(
            f"🎹  LH: {lh_low}–{lh_high}  |  RH: {rh_low}–{rh_high}"
        )

    def _on_note_on(self, note: int) -> None:
        self._mixer.note_on(note)

    def _on_note_off(self, note: int) -> None:
        self._mixer.note_off(note)

    def _on_drawbar_change(self, index: int, value: float) -> None:
        self._mixer.set_drawbar(index, value)

    def _on_stop_toggle(self, name: str, active: bool) -> None:
        self._mixer.toggle_stop(name)

    def _on_stop_group(self, group_id: int) -> None:
        """Apply a stop group preset from numpad."""
        if group_id not in STOP_GROUPS:
            return

        group_name, desired_stops = STOP_GROUPS[group_id]

        # Get current active stops
        current = self._mixer.active_stop_names

        # Turn off stops not in the desired group
        for name in list(current):
            if name not in desired_stops:
                self._mixer.toggle_stop(name)

        # Turn on stops that should be active
        # Re-read after toggling off
        current = self._mixer.active_stop_names
        for name in desired_stops:
            if name not in current and name in STOP_DEFS:
                self._mixer.toggle_stop(name)

        # Update stop panel buttons to reflect new state
        new_active = self._mixer.active_stop_names
        self._stop_panel.update_stops(new_active)

        self._group_label.setText(f"Group {group_id}: {group_name}")

    def _on_drawbar_selected(self, index: int) -> None:
        """Highlight the selected drawbar."""
        if 0 <= index < len(DRAWBAR_LABELS):
            self._drawbar_select_label.setText(
                f"Drawbar: {DRAWBAR_LABELS[index]} (↑/↓ to adjust)"
            )
            self._drawbar_panel.highlight_drawbar(index)

    def _on_drawbar_adjust(self, index: int, delta: int) -> None:
        """Adjust a drawbar value via keyboard."""
        self._drawbar_panel.adjust_drawbar(index, delta)

    def _on_drawbar_preset(self, name: str, values: list) -> None:
        """Apply a drawbar preset."""
        self._drawbar_panel.set_values(values)

    def _on_room_selected(self, preset_name: str) -> None:
        """Apply a room preset."""
        self._mixer.set_room_preset(preset_name)
