"""Stop panel — toggle buttons for organ stops."""

from PyQt6.QtWidgets import QGroupBox, QGridLayout, QPushButton
from PyQt6.QtCore import pyqtSignal


class StopPanel(QGroupBox):
    """Grid of toggle buttons for organ stops."""

    stop_toggled = pyqtSignal(str, bool)

    def __init__(self, stop_names: list[str], active_stops: set[str]) -> None:
        super().__init__("Organ Stops")
        self._buttons: dict[str, QPushButton] = {}

        layout = QGridLayout()
        layout.setSpacing(6)

        cols = 4  # 2 rows of 4 for 8 stops
        for idx, name in enumerate(stop_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name in active_stops)
            btn.setMinimumHeight(44)
            btn.setMinimumWidth(110)
            btn.setStyleSheet(self._button_style(name in active_stops))
            btn.clicked.connect(lambda checked, n=name: self._on_toggle(n, checked))
            self._buttons[name] = btn
            layout.addWidget(btn, idx // cols, idx % cols)

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

    def _button_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background-color: #8b4513;
                    color: #fff8e7;
                    border: 2px solid #d4a574;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px;
                }
                QPushButton:hover { background-color: #a0522d; }
            """
        return """
            QPushButton {
                background-color: #3a2a1a;
                color: #a09080;
                border: 2px solid #5a4a3a;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:hover { background-color: #4a3a2a; }
        """

    def _on_toggle(self, name: str, checked: bool) -> None:
        self._buttons[name].setStyleSheet(self._button_style(checked))
        self.stop_toggled.emit(name, checked)
