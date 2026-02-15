"""On-screen keyboard with octave shifting and computer keyboard input.

Shows 2 octaves of piano keys. Arrow keys shift the octave range
across the full MIDI spectrum (C1–C7).
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QMouseEvent, QKeyEvent


# QWERTY → semitone offset mapping (relative to current octave base)
# Lower row: C – B (one octave)
# Upper row: C – B (next octave)
_LOWER_ROW = [
    (Qt.Key.Key_Z, 0),   # C
    (Qt.Key.Key_S, 1),   # C#
    (Qt.Key.Key_X, 2),   # D
    (Qt.Key.Key_D, 3),   # D#
    (Qt.Key.Key_C, 4),   # E
    (Qt.Key.Key_V, 5),   # F
    (Qt.Key.Key_G, 6),   # F#
    (Qt.Key.Key_B, 7),   # G
    (Qt.Key.Key_H, 8),   # G#
    (Qt.Key.Key_N, 9),   # A
    (Qt.Key.Key_J, 10),  # A#
    (Qt.Key.Key_M, 11),  # B
]

_UPPER_ROW = [
    (Qt.Key.Key_Q, 12),  # C+1
    (Qt.Key.Key_2, 13),  # C#+1
    (Qt.Key.Key_W, 14),  # D+1
    (Qt.Key.Key_3, 15),  # D#+1
    (Qt.Key.Key_E, 16),  # E+1
    (Qt.Key.Key_R, 17),  # F+1
    (Qt.Key.Key_5, 18),  # F#+1
    (Qt.Key.Key_T, 19),  # G+1
    (Qt.Key.Key_6, 20),  # G#+1
    (Qt.Key.Key_Y, 21),  # A+1
    (Qt.Key.Key_7, 22),  # A#+1
    (Qt.Key.Key_U, 23),  # B+1
]

# Key offset map: Qt key → semitone offset from octave base
KEY_OFFSET_MAP: dict[int, int] = {}
for key, offset in _LOWER_ROW + _UPPER_ROW:
    KEY_OFFSET_MAP[key] = offset

# Reverse: offset → key label
_QT_KEY_NAMES = {
    Qt.Key.Key_Z: "Z", Qt.Key.Key_S: "S", Qt.Key.Key_X: "X",
    Qt.Key.Key_D: "D", Qt.Key.Key_C: "C", Qt.Key.Key_V: "V",
    Qt.Key.Key_G: "G", Qt.Key.Key_B: "B", Qt.Key.Key_H: "H",
    Qt.Key.Key_N: "N", Qt.Key.Key_J: "J", Qt.Key.Key_M: "M",
    Qt.Key.Key_Q: "Q", Qt.Key.Key_2: "2", Qt.Key.Key_W: "W",
    Qt.Key.Key_3: "3", Qt.Key.Key_E: "E", Qt.Key.Key_R: "R",
    Qt.Key.Key_5: "5", Qt.Key.Key_T: "T", Qt.Key.Key_6: "6",
    Qt.Key.Key_Y: "Y", Qt.Key.Key_7: "7", Qt.Key.Key_U: "U",
}

OFFSET_TO_KEY_LABEL: dict[int, str] = {}
for key, offset in _LOWER_ROW + _UPPER_ROW:
    if key in _QT_KEY_NAMES:
        OFFSET_TO_KEY_LABEL[offset] = _QT_KEY_NAMES[key]

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


class PianoKeyboard(QWidget):
    """Visual piano keyboard with octave shifting."""

    note_on = pyqtSignal(int)
    note_off = pyqtSignal(int)
    octave_changed = pyqtSignal(int)  # new base note

    # Display 2 octaves
    NUM_DISPLAY_OCTAVES = 2

    # Key geometry
    WHITE_KEY_W = 42
    WHITE_KEY_H = 155
    BLACK_KEY_W = 26
    BLACK_KEY_H = 95

    # Octave range
    MIN_BASE_NOTE = 24   # C1
    MAX_BASE_NOTE = 84   # C6

    def __init__(self, base_note: int = 48) -> None:
        super().__init__()
        self._base_note = base_note  # MIDI note of the lowest displayed key
        self._pressed_notes: set[int] = set()
        self._pressed_keys: set[int] = set()
        self._active_midi_notes: set[int] = set()  # For MIDI playback highlighting

        self._compute_layout()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _compute_layout(self) -> None:
        first = self._base_note
        last = self._base_note + self.NUM_DISPLAY_OCTAVES * 12 - 1

        self._white_notes: list[int] = []
        self._black_notes: list[int] = []
        for note in range(first, last + 1):
            if self._is_black(note):
                self._black_notes.append(note)
            else:
                self._white_notes.append(note)

        total_w = len(self._white_notes) * self.WHITE_KEY_W + 2
        self.setFixedSize(total_w, self.WHITE_KEY_H + 10)

    @property
    def base_note(self) -> int:
        return self._base_note

    def set_base_note(self, note: int) -> None:
        """Shift the octave. Releases any currently pressed notes first."""
        note = max(self.MIN_BASE_NOTE, min(self.MAX_BASE_NOTE, note))
        if note == self._base_note:
            return

        # Release pressed notes at old octave
        for n in list(self._pressed_notes):
            self.note_off.emit(n)
        self._pressed_notes.clear()
        self._pressed_keys.clear()

        self._base_note = note
        self._compute_layout()
        self.octave_changed.emit(note)
        self.update()

    def shift_octave(self, direction: int) -> None:
        """Shift by one octave: +1 = up, -1 = down."""
        self.set_base_note(self._base_note + direction * 12)

    def set_highlighted_notes(self, notes: set[int]) -> None:
        """Highlight notes from MIDI playback."""
        self._active_midi_notes = notes
        self.update()

    @staticmethod
    def _is_black(note: int) -> bool:
        return (note % 12) in (1, 3, 6, 8, 10)

    def _white_key_rect(self, white_index: int) -> QRect:
        x = white_index * self.WHITE_KEY_W + 1
        return QRect(x, 1, self.WHITE_KEY_W - 1, self.WHITE_KEY_H)

    def _black_key_rect(self, note: int) -> QRect | None:
        if not self._is_black(note):
            return None
        semitone = note % 12
        whites_before_in_octave = {1: 1, 3: 2, 6: 4, 8: 5, 10: 6}
        octave_offset = (note - self._base_note) // 12
        whites_in_prev = octave_offset * 7
        white_idx = whites_in_prev + whites_before_in_octave[semitone]
        x = white_idx * self.WHITE_KEY_W - self.BLACK_KEY_W // 2 + 1
        return QRect(x, 1, self.BLACK_KEY_W, self.BLACK_KEY_H)

    def _note_at_pos(self, x: int, y: int) -> int | None:
        for note in self._black_notes:
            rect = self._black_key_rect(note)
            if rect and rect.contains(x, y):
                return note
        for i, note in enumerate(self._white_notes):
            rect = self._white_key_rect(i)
            if rect.contains(x, y):
                return note
        return None

    def _note_to_offset(self, note: int) -> int | None:
        offset = note - self._base_note
        if 0 <= offset < 24:
            return offset
        return None

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        key_font = QFont("Monospace", 9)
        note_font = QFont("Monospace", 8)

        # Draw white keys
        for i, note in enumerate(self._white_notes):
            rect = self._white_key_rect(i)
            is_pressed = note in self._pressed_notes
            is_midi = note in self._active_midi_notes

            if is_pressed:
                painter.setBrush(QColor("#d4a574"))
            elif is_midi:
                painter.setBrush(QColor("#b8d4a5"))
            else:
                painter.setBrush(QColor("#fff8e7"))

            painter.setPen(QPen(QColor("#2a1a0a"), 1))
            painter.drawRoundedRect(rect, 3, 3)

            # Note name
            note_name = NOTE_NAMES[note % 12] + str(note // 12 - 1)
            painter.setPen(QColor("#888"))
            painter.setFont(note_font)
            painter.drawText(
                rect.adjusted(0, 0, 0, -8),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                note_name,
            )

            # Key label
            offset = self._note_to_offset(note)
            if offset is not None and offset in OFFSET_TO_KEY_LABEL:
                painter.setPen(QColor("#555"))
                painter.setFont(key_font)
                painter.drawText(
                    rect.adjusted(0, 0, 0, -24),
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                    OFFSET_TO_KEY_LABEL[offset],
                )

        # Draw black keys
        for note in self._black_notes:
            rect = self._black_key_rect(note)
            if rect is None:
                continue
            is_pressed = note in self._pressed_notes
            is_midi = note in self._active_midi_notes

            if is_pressed:
                painter.setBrush(QColor("#8b4513"))
            elif is_midi:
                painter.setBrush(QColor("#4a7a3a"))
            else:
                painter.setBrush(QColor("#1a1a1a"))

            painter.setPen(QPen(QColor("#000"), 1))
            painter.drawRoundedRect(rect, 3, 3)

            offset = self._note_to_offset(note)
            if offset is not None and offset in OFFSET_TO_KEY_LABEL:
                painter.setPen(QColor("#aaa"))
                painter.setFont(key_font)
                painter.drawText(
                    rect.adjusted(0, 0, 0, -6),
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                    OFFSET_TO_KEY_LABEL[offset],
                )

        painter.end()

    # ── Mouse input ─────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        note = self._note_at_pos(int(event.position().x()), int(event.position().y()))
        if note is not None:
            self._pressed_notes.add(note)
            self.note_on.emit(note)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        note = self._note_at_pos(int(event.position().x()), int(event.position().y()))
        if note is not None and note in self._pressed_notes:
            self._pressed_notes.discard(note)
            self.note_off.emit(note)
            self.update()

    # ── Keyboard input ──────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return

        key = event.key()

        # Octave shifting with arrow keys
        if key == Qt.Key.Key_Left:
            self.shift_octave(-1)
            return
        elif key == Qt.Key.Key_Right:
            self.shift_octave(1)
            return

        if key in KEY_OFFSET_MAP:
            note = self._base_note + KEY_OFFSET_MAP[key]
            if 0 <= note <= 127:
                self._pressed_keys.add(key)
                self._pressed_notes.add(note)
                self.note_on.emit(note)
                self.update()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return

        key = event.key()

        if key in KEY_OFFSET_MAP:
            note = self._base_note + KEY_OFFSET_MAP[key]
            if 0 <= note <= 127:
                self._pressed_keys.discard(key)
                self._pressed_notes.discard(note)
                self.note_off.emit(note)
                self.update()
        else:
            super().keyReleaseEvent(event)
