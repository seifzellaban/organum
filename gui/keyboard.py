"""Full-range visible keyboard with split-hand octave control.

Shows ALL octaves (C1–C7) simultaneously. The currently active octaves
(left hand + right hand ranges) are bright; inactive octaves have low
opacity. Keyboard shortcuts control hand positions independently.

Controls:
  ←/→         Move both hands (no modifier)
  LCtrl + ←/→ Move left hand only
  RCtrl + ←/→ Move right hand only
  Numpad 0–9  Stop group presets  (0 = all stops)
  Shift+Num1–9 Select drawbar, then ↑/↓ to adjust
"""

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QWidget

# QWERTY → semitone offset mapping (relative to current octave base)
# Lower row: C – B (one octave)  →  LEFT HAND
# Upper row: C – B (next octave) →  RIGHT HAND
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
    (Qt.Key.Key_Y, 0),            # C
    (Qt.Key.Key_7, 1),            # C#
    (Qt.Key.Key_U, 2),            # D
    (Qt.Key.Key_8, 3),            # D#
    (Qt.Key.Key_I, 4),            # E
    (Qt.Key.Key_O, 5),            # F
    (Qt.Key.Key_0, 6),            # F#
    (Qt.Key.Key_P, 7),            # G
    (Qt.Key.Key_Minus, 8),        # G#
    (Qt.Key.Key_BracketLeft, 9),  # A
    (Qt.Key.Key_Equal, 10),       # A#
    (Qt.Key.Key_BracketRight, 11), # B
]

# Separate maps for left hand (lower row) and right hand (upper row)
LEFT_HAND_KEY_MAP: dict[int, int] = {key: offset for key, offset in _LOWER_ROW}
RIGHT_HAND_KEY_MAP: dict[int, int] = {key: offset for key, offset in _UPPER_ROW}

# Combined for backward compat / general lookup
KEY_OFFSET_MAP: dict[int, int] = {}
for key, offset in _LOWER_ROW:
    KEY_OFFSET_MAP[key] = offset
for key, offset in _UPPER_ROW:
    KEY_OFFSET_MAP[key] = offset + 12  # Keep old behavior for non-split mode

# Reverse: offset → key label
_QT_KEY_NAMES = {
    Qt.Key.Key_Z: "Z", Qt.Key.Key_S: "S", Qt.Key.Key_X: "X",
    Qt.Key.Key_D: "D", Qt.Key.Key_C: "C", Qt.Key.Key_V: "V",
    Qt.Key.Key_G: "G", Qt.Key.Key_B: "B", Qt.Key.Key_H: "H",
    Qt.Key.Key_N: "N", Qt.Key.Key_J: "J", Qt.Key.Key_M: "M",
    Qt.Key.Key_Y: "Y", Qt.Key.Key_7: "7", Qt.Key.Key_U: "U",
    Qt.Key.Key_8: "8", Qt.Key.Key_I: "I", Qt.Key.Key_O: "O",
    Qt.Key.Key_0: "0", Qt.Key.Key_P: "P", Qt.Key.Key_Minus: "-",
    Qt.Key.Key_BracketLeft: "[", Qt.Key.Key_Equal: "=",
    Qt.Key.Key_BracketRight: "]",
}

# Create separate label maps per hand
LH_OFFSET_TO_LABEL: dict[int, str] = {}
for key, offset in _LOWER_ROW:
    if key in _QT_KEY_NAMES:
        LH_OFFSET_TO_LABEL[offset] = _QT_KEY_NAMES[key]

RH_OFFSET_TO_LABEL: dict[int, str] = {}
for key, offset in _UPPER_ROW:
    if key in _QT_KEY_NAMES:
        RH_OFFSET_TO_LABEL[offset] = _QT_KEY_NAMES[key]

# Legacy combined map
OFFSET_TO_KEY_LABEL: dict[int, str] = {}
for key, offset in _LOWER_ROW + _UPPER_ROW:
    if key in _QT_KEY_NAMES:
        OFFSET_TO_KEY_LABEL[offset if offset < 12 else offset] = _QT_KEY_NAMES[key]

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Numpad key mapping — covers BOTH NumLock-on (digits) and NumLock-off/Shift (nav keys)
# Qt reports different key codes depending on NumLock + Shift state,
# but the KeypadModifier flag is always set for numpad keys.
NUMPAD_KEYS: dict[int, int] = {
    # NumLock ON (digits)
    Qt.Key.Key_0: 0,
    Qt.Key.Key_1: 1,
    Qt.Key.Key_2: 2,
    Qt.Key.Key_3: 3,
    Qt.Key.Key_4: 4,
    Qt.Key.Key_5: 5,
    Qt.Key.Key_6: 6,
    Qt.Key.Key_7: 7,
    Qt.Key.Key_8: 8,
    Qt.Key.Key_9: 9,
    # NumLock OFF or Shift held (navigation keys from numpad)
    Qt.Key.Key_Insert: 0,    # Numpad 0
    Qt.Key.Key_End: 1,       # Numpad 1
    Qt.Key.Key_Down: 2,      # Numpad 2
    Qt.Key.Key_PageDown: 3,  # Numpad 3
    Qt.Key.Key_Left: 4,      # Numpad 4
    Qt.Key.Key_Clear: 5,     # Numpad 5
    Qt.Key.Key_Right: 6,     # Numpad 6
    Qt.Key.Key_Home: 7,      # Numpad 7
    Qt.Key.Key_Up: 8,        # Numpad 8
    Qt.Key.Key_PageUp: 9,    # Numpad 9
}


def _is_numpad_key(event: QKeyEvent) -> bool:
    """Check if a key event comes from the numpad using the KeypadModifier."""
    return bool(event.modifiers() & Qt.KeyboardModifier.KeypadModifier)


def _get_numpad_digit(event: QKeyEvent) -> int | None:
    """Get the numpad digit (0–9) from a key event, or None if not numpad."""
    if not _is_numpad_key(event):
        return None
    # Strip modifiers to get the base key
    key = event.key()
    return NUMPAD_KEYS.get(key)


class PianoKeyboard(QWidget):
    """Full-range visible piano keyboard with left/right hand split."""

    note_on = pyqtSignal(int)
    note_off = pyqtSignal(int)
    octave_changed = pyqtSignal(int)  # emits left-hand base note
    hands_changed = pyqtSignal(int, int)  # (left_base, right_base)
    stop_group_selected = pyqtSignal(int)  # numpad group 0–9
    drawbar_selected = pyqtSignal(int)     # drawbar index 0–8
    drawbar_adjust = pyqtSignal(int, int)  # (drawbar_index, delta: +1/-1)

    # Full MIDI range to display
    FULL_MIN_NOTE = 24   # C1
    FULL_MAX_NOTE = 96   # C7

    # Key geometry
    WHITE_KEY_W = 22
    WHITE_KEY_H = 150
    BLACK_KEY_W = 14
    BLACK_KEY_H = 90

    # Octave range
    MIN_BASE_NOTE = 24   # C1
    MAX_BASE_NOTE = 84   # C6

    def __init__(self, base_note: int = 48) -> None:
        super().__init__()
        # Left hand and right hand base notes (each covers 1 octave of keys)
        self._left_base = base_note        # Left hand: Z-M row
        self._right_base = base_note + 12  # Right hand: Y-] row

        self._pressed_notes: set[int] = set()
        self._pressed_keys: set[int] = set()
        self._active_midi_notes: set[int] = set()

        # Drawbar selection for Shift+Numpad mode
        self._selected_drawbar: int = -1   # -1 = none selected

        self._compute_layout()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _compute_layout(self) -> None:
        """Compute layout for the FULL visible range."""
        first = self.FULL_MIN_NOTE
        last = self.FULL_MAX_NOTE - 1  # Up to B6

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
        """Legacy — returns left hand base."""
        return self._left_base

    @property
    def left_base(self) -> int:
        return self._left_base

    @property
    def right_base(self) -> int:
        return self._right_base

    def set_base_note(self, note: int) -> None:
        """Legacy: shift both hands together."""
        note = max(self.MIN_BASE_NOTE, min(self.MAX_BASE_NOTE, note))
        if note == self._left_base:
            return
        self._release_all()
        self._left_base = note
        self._right_base = note + 12
        self.octave_changed.emit(note)
        self.hands_changed.emit(self._left_base, self._right_base)
        self.update()

    def shift_octave(self, direction: int) -> None:
        """Shift both hands by one octave."""
        new_left = self._left_base + direction * 12
        new_left = max(self.MIN_BASE_NOTE, min(self.MAX_BASE_NOTE, new_left))
        if new_left == self._left_base:
            return
        self._release_all()
        self._left_base = new_left
        self._right_base = new_left + 12
        self.octave_changed.emit(self._left_base)
        self.hands_changed.emit(self._left_base, self._right_base)
        self.update()

    def shift_left_hand(self, direction: int) -> None:
        """Shift left hand only by one octave."""
        new_base = self._left_base + direction * 12
        new_base = max(self.MIN_BASE_NOTE, min(self.MAX_BASE_NOTE, new_base))
        if new_base == self._left_base:
            return
        # Release left hand notes
        self._release_hand_notes("left")
        self._left_base = new_base
        self.octave_changed.emit(self._left_base)
        self.hands_changed.emit(self._left_base, self._right_base)
        self.update()

    def shift_right_hand(self, direction: int) -> None:
        """Shift right hand only by one octave."""
        new_base = self._right_base + direction * 12
        new_base = max(self.MIN_BASE_NOTE, min(self.MAX_BASE_NOTE + 12, new_base))
        if new_base == self._right_base:
            return
        # Release right hand notes
        self._release_hand_notes("right")
        self._right_base = new_base
        self.hands_changed.emit(self._left_base, self._right_base)
        self.update()

    def _release_all(self) -> None:
        """Release all currently pressed notes."""
        for n in list(self._pressed_notes):
            self.note_off.emit(n)
        self._pressed_notes.clear()
        self._pressed_keys.clear()

    def _release_hand_notes(self, hand: str) -> None:
        """Release notes belonging to one hand."""
        if hand == "left":
            key_map = LEFT_HAND_KEY_MAP
            base = self._left_base
        else:
            key_map = RIGHT_HAND_KEY_MAP
            base = self._right_base

        keys_to_remove = []
        for key in list(self._pressed_keys):
            if key in key_map:
                note = base + key_map[key]
                if note in self._pressed_notes:
                    self.note_off.emit(note)
                    self._pressed_notes.discard(note)
                keys_to_remove.append(key)
        for key in keys_to_remove:
            self._pressed_keys.discard(key)

    def set_highlighted_notes(self, notes: set[int]) -> None:
        """Highlight notes from MIDI playback."""
        self._active_midi_notes = notes
        self.update()

    @staticmethod
    def _is_black(note: int) -> bool:
        return (note % 12) in (1, 3, 6, 8, 10)

    def _is_in_left_hand(self, note: int) -> bool:
        """Is this note within the left hand's active range?"""
        return self._left_base <= note < self._left_base + 12

    def _is_in_right_hand(self, note: int) -> bool:
        """Is this note within the right hand's active range?"""
        return self._right_base <= note < self._right_base + 12

    def _is_active_note(self, note: int) -> bool:
        """Is this note in either hand's active range?"""
        return self._is_in_left_hand(note) or self._is_in_right_hand(note)

    def _white_key_rect(self, white_index: int) -> QRect:
        x = white_index * self.WHITE_KEY_W + 1
        return QRect(x, 1, self.WHITE_KEY_W - 1, self.WHITE_KEY_H)

    def _black_key_rect(self, note: int) -> QRect | None:
        if not self._is_black(note):
            return None
        # Count white keys before this note in the full range
        whites_before = 0
        for n in range(self.FULL_MIN_NOTE, note):
            if not self._is_black(n):
                whites_before += 1
        x = whites_before * self.WHITE_KEY_W + self.WHITE_KEY_W - self.BLACK_KEY_W // 2 + 1
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

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        key_font = QFont("Monospace", 8)
        note_font = QFont("Monospace", 7)

        # Draw white keys
        for i, note in enumerate(self._white_notes):
            rect = self._white_key_rect(i)
            is_pressed = note in self._pressed_notes
            is_midi = note in self._active_midi_notes
            is_active = self._is_active_note(note)
            is_left = self._is_in_left_hand(note)
            is_right = self._is_in_right_hand(note)

            if is_pressed:
                painter.setBrush(QColor("#d4a574"))
            elif is_midi:
                painter.setBrush(QColor("#b8d4a5"))
            elif is_active:
                painter.setBrush(QColor("#fff8e7"))
            else:
                # Inactive octaves — dim
                painter.setBrush(QColor(200, 195, 180, 100))

            painter.setPen(QPen(QColor("#2a1a0a"), 1))
            painter.drawRoundedRect(rect, 2, 2)

            # Note name (only for active range or every C)
            if is_active or (note % 12 == 0):
                note_name = NOTE_NAMES[note % 12] + str(note // 12 - 1)
                if is_active:
                    painter.setPen(QColor("#888"))
                else:
                    painter.setPen(QColor(100, 100, 100, 80))
                painter.setFont(note_font)
                painter.drawText(
                    rect.adjusted(0, 0, 0, -4),
                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                    note_name,
                )

            # Key label — left hand or right hand
            if is_left:
                offset = note - self._left_base
                if offset in LH_OFFSET_TO_LABEL:
                    painter.setPen(QColor("#3377cc"))
                    painter.setFont(key_font)
                    painter.drawText(
                        rect.adjusted(0, 0, 0, -16),
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                        LH_OFFSET_TO_LABEL[offset],
                    )
            if is_right:
                offset = note - self._right_base
                if offset in RH_OFFSET_TO_LABEL:
                    painter.setPen(QColor("#cc7733"))
                    painter.setFont(key_font)
                    painter.drawText(
                        rect.adjusted(0, 0, 0, -16),
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                        RH_OFFSET_TO_LABEL[offset],
                    )

            # Hand indicator bar at top of active keys
            if is_left and is_right:
                # Overlap — gradient
                painter.fillRect(rect.x(), rect.y(), rect.width(), 3, QColor("#9977aa"))
            elif is_left:
                painter.fillRect(rect.x(), rect.y(), rect.width(), 3, QColor("#3377cc"))
            elif is_right:
                painter.fillRect(rect.x(), rect.y(), rect.width(), 3, QColor("#cc7733"))

        # Draw black keys
        for note in self._black_notes:
            rect = self._black_key_rect(note)
            if rect is None:
                continue
            is_pressed = note in self._pressed_notes
            is_midi = note in self._active_midi_notes
            is_active = self._is_active_note(note)
            is_left = self._is_in_left_hand(note)
            is_right = self._is_in_right_hand(note)

            if is_pressed:
                painter.setBrush(QColor("#8b4513"))
            elif is_midi:
                painter.setBrush(QColor("#4a7a3a"))
            elif is_active:
                painter.setBrush(QColor("#1a1a1a"))
            else:
                # Inactive — dim
                painter.setBrush(QColor(30, 30, 30, 100))

            painter.setPen(QPen(QColor("#000"), 1))
            painter.drawRoundedRect(rect, 2, 2)

            # Key label
            if is_left:
                offset = note - self._left_base
                if offset in LH_OFFSET_TO_LABEL:
                    painter.setPen(QColor("#5599ee"))
                    painter.setFont(key_font)
                    painter.drawText(
                        rect.adjusted(0, 0, 0, -4),
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                        LH_OFFSET_TO_LABEL[offset],
                    )
            if is_right:
                offset = note - self._right_base
                if offset in RH_OFFSET_TO_LABEL:
                    painter.setPen(QColor("#ee9955"))
                    painter.setFont(key_font)
                    painter.drawText(
                        rect.adjusted(0, 0, 0, -4),
                        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                        RH_OFFSET_TO_LABEL[offset],
                    )

            # Hand indicator bar at top
            if is_left and is_right:
                painter.fillRect(rect.x(), rect.y(), rect.width(), 2, QColor("#9977aa"))
            elif is_left:
                painter.fillRect(rect.x(), rect.y(), rect.width(), 2, QColor("#3377cc"))
            elif is_right:
                painter.fillRect(rect.x(), rect.y(), rect.width(), 2, QColor("#cc7733"))

        # Draw octave bracket labels at the bottom
        painter.setFont(QFont("Sans", 7, QFont.Weight.Bold))
        for octave in range(1, 8):
            start_note = octave * 12 + 12  # C of that octave (MIDI)
            if start_note < self.FULL_MIN_NOTE or start_note >= self.FULL_MAX_NOTE:
                continue
            # Find x position of that C
            white_idx = 0
            for n in range(self.FULL_MIN_NOTE, start_note):
                if not self._is_black(n):
                    white_idx += 1
            x = white_idx * self.WHITE_KEY_W + 1
            painter.setPen(QColor("#5a4a3a"))
            painter.drawText(
                x, self.WHITE_KEY_H + 9, f"C{octave}"
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
        mods = event.modifiers()
        is_numpad = _is_numpad_key(event)
        is_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        # ── Numpad: stop groups & drawbar selection ──────────────
        # Must be checked FIRST — numpad arrows/nav keys have the same
        # key codes as regular arrows but carry KeypadModifier.
        numpad_digit = _get_numpad_digit(event)
        if numpad_digit is not None:
            if is_shift and 1 <= numpad_digit <= 9:
                # Shift + Numpad 1–9: select drawbar
                self._selected_drawbar = numpad_digit - 1  # 0-indexed
                self.drawbar_selected.emit(self._selected_drawbar)
            else:
                # Numpad 0–9: stop group selection
                self.stop_group_selected.emit(numpad_digit)
            return

        # ── Up/Down arrows: drawbar adjustment (non-numpad only) ─
        if self._selected_drawbar >= 0 and not is_numpad:
            if key == Qt.Key.Key_Up:
                self.drawbar_adjust.emit(self._selected_drawbar, 1)
                return
            elif key == Qt.Key.Key_Down:
                self.drawbar_adjust.emit(self._selected_drawbar, -1)
                return

        # ── Left/Right arrows: octave shifting (non-numpad only) ─
        if key == Qt.Key.Key_Left and not is_numpad:
            if bool(mods & Qt.KeyboardModifier.ControlModifier):
                if self._right_ctrl_held:
                    self.shift_right_hand(-1)
                else:
                    self.shift_left_hand(-1)
            else:
                self.shift_octave(-1)
            return
        elif key == Qt.Key.Key_Right and not is_numpad:
            if bool(mods & Qt.KeyboardModifier.ControlModifier):
                if self._right_ctrl_held:
                    self.shift_right_hand(1)
                else:
                    self.shift_left_hand(1)
            else:
                self.shift_octave(1)
            return

        # ── Track Control keys for L/R distinction ──────────────
        if key == Qt.Key.Key_Control:
            # Use native scan code to differentiate left/right
            # Linux: Left Ctrl = 37, Right Ctrl = 105
            native = event.nativeScanCode()
            if native == 105:  # Right Ctrl
                self._right_ctrl_held = True
            else:
                self._right_ctrl_held = False
            return

        # ── Note input: left hand (Z–M row) ────────────────────
        if key in LEFT_HAND_KEY_MAP:
            note = self._left_base + LEFT_HAND_KEY_MAP[key]
            if 0 <= note <= 127:
                self._pressed_keys.add(key)
                self._pressed_notes.add(note)
                self.note_on.emit(note)
                self.update()
            return

        # ── Note input: right hand (Y–] row) ───────────────────
        if key in RIGHT_HAND_KEY_MAP:
            note = self._right_base + RIGHT_HAND_KEY_MAP[key]
            if 0 <= note <= 127:
                self._pressed_keys.add(key)
                self._pressed_notes.add(note)
                self.note_on.emit(note)
                self.update()
            return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return

        key = event.key()

        # Control key release
        if key == Qt.Key.Key_Control:
            self._right_ctrl_held = False
            return

        # Left hand keys
        if key in LEFT_HAND_KEY_MAP:
            note = self._left_base + LEFT_HAND_KEY_MAP[key]
            if 0 <= note <= 127:
                self._pressed_keys.discard(key)
                self._pressed_notes.discard(note)
                self.note_off.emit(note)
                self.update()
            return

        # Right hand keys
        if key in RIGHT_HAND_KEY_MAP:
            note = self._right_base + RIGHT_HAND_KEY_MAP[key]
            if 0 <= note <= 127:
                self._pressed_keys.discard(key)
                self._pressed_notes.discard(note)
                self.note_off.emit(note)
                self.update()
            return

        super().keyReleaseEvent(event)

    # Internal state for distinguishing L/R Ctrl
    _right_ctrl_held: bool = False
