"""Room preset panel — select acoustic environments for the reverb engine.

Each preset configures the stereo reverb and room resonance to simulate
a different space, from intimate practice rooms to vast gothic basilicas.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QPushButton, QLabel,
)
from PyQt6.QtCore import pyqtSignal, Qt


# Descriptions for each room preset
ROOM_DESCRIPTIONS: dict[str, str] = {
    "Grand Cathedral": "Vast stone nave, ~4s reverb tail, deep sub-bass resonance",
    "Stone Chapel": "Warm mid-size stone room, intimate yet resonant",
    "Concert Hall": "Balanced concert acoustic, clear and present",
    "Gothic Basilica": "Enormous vaulted space, ~6s tail, massive resonance",
    "Intimate Room": "Small chamber with gentle reflections",
    "Dry Studio": "Minimal reverb, direct and focused sound",
}


class RoomPresetPanel(QGroupBox):
    """Panel of room preset buttons with visual feedback."""

    room_selected = pyqtSignal(str)  # preset name

    def __init__(self, preset_names: list[str], current_preset: str) -> None:
        super().__init__("Room")
        self._buttons: dict[str, QPushButton] = {}
        self._current = current_preset

        layout = QVBoxLayout()
        layout.setSpacing(5)

        for name in preset_names:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == current_preset)
            btn.setMinimumHeight(32)
            btn.setMinimumWidth(130)
            btn.setStyleSheet(self._button_style(name == current_preset))
            btn.setToolTip(ROOM_DESCRIPTIONS.get(name, name))
            btn.clicked.connect(
                lambda checked, n=name: self._on_select(n)
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
                        stop:0 #2a4a6a, stop:0.5 #3a6a9a, stop:1 #2a4a6a
                    );
                    color: #e8f0ff;
                    border: 2px solid #5599dd;
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 6px 8px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3a5a7a, stop:0.5 #4a7aaa, stop:1 #3a5a7a
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

    def _on_select(self, name: str) -> None:
        self._current = name
        # Update all button states
        for btn_name, btn in self._buttons.items():
            is_active = btn_name == name
            btn.setChecked(is_active)
            btn.setStyleSheet(self._button_style(is_active))
        self.room_selected.emit(name)
