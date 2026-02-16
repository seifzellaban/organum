"""Drawbar preset panel — classic organ registration presets.

Each preset defines all 9 drawbar positions (0–8) following traditional
Hammond/pipe organ registration conventions. Values represent the
drawbar pull-out amount from 0 (off) to 8 (full).

Drawbar order: 16' 8' 5⅓' 4' 2⅔' 2' 1⅗' 1⅓' 1'
"""

from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt


# Classic drawbar presets: name → 9 drawbar values (0–8)
# Format: [16', 8', 5⅓', 4', 2⅔', 2', 1⅗', 1⅓', 1']
DRAWBAR_PRESETS: dict[str, list[int]] = {
    "Full Organ":     [8, 8, 8, 8, 6, 6, 4, 4, 4],
    "Gospel":         [6, 8, 8, 6, 0, 0, 0, 0, 0],
    "Cathedral":      [6, 8, 5, 7, 3, 5, 2, 2, 1],
    "Flutes":         [8, 6, 0, 4, 0, 3, 0, 0, 0],
    "Theater":        [8, 0, 8, 0, 0, 0, 8, 0, 0],
    "Bach":           [4, 8, 6, 7, 4, 5, 3, 3, 2],
}


class DrawbarPresetPanel(QGroupBox):
    """Panel of drawbar preset buttons."""

    preset_selected = pyqtSignal(str, list)  # (name, values)

    def __init__(self, initial_preset: str = "Cathedral") -> None:
        super().__init__("Presets")
        self._buttons: dict[str, QPushButton] = {}
        self._current: str | None = initial_preset

        layout = QVBoxLayout()
        layout.setSpacing(5)

        for name, values in DRAWBAR_PRESETS.items():
            is_active = name == initial_preset
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(is_active)
            btn.setMinimumHeight(32)
            btn.setMinimumWidth(130)
            btn.setStyleSheet(self._button_style(is_active))
            # Compact drawbar preview as tooltip
            tip = "  ".join(str(v) for v in values)
            btn.setToolTip(f"{name}: {tip}")
            btn.clicked.connect(
                lambda checked, n=name, v=values: self._on_select(n, v)
            )
            self._buttons[name] = btn
            layout.addWidget(btn)

        layout.addStretch()

        self.setLayout(layout)
        self.setStyleSheet("""
            QGroupBox {
                font-size: 13px;
                font-weight: bold;
                color: #e0d4c0;
                border: 1px solid #5a4a3a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)

    def _button_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4a3218, stop:0.5 #6a4a28, stop:1 #4a3218
                    );
                    color: #ffd700;
                    border: 2px solid #cc8844;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 6px 8px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5a4228, stop:0.5 #7a5a38, stop:1 #5a4228
                    );
                }
            """
        return """
            QPushButton {
                background-color: #2a2218;
                color: #8a7a6a;
                border: 1px solid #4a3a2a;
                border-radius: 5px;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 8px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3a3228;
                color: #b0a090;
                border-color: #5a4a3a;
            }
        """

    def _on_select(self, name: str, values: list[int]) -> None:
        self._current = name
        for btn_name, btn in self._buttons.items():
            is_active = btn_name == name
            btn.setChecked(is_active)
            btn.setStyleSheet(self._button_style(is_active))
        self.preset_selected.emit(name, values)
