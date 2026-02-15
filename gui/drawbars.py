"""Drawbar panel — 9 vertical sliders (Hammond-style)."""

from PyQt6.QtWidgets import QGroupBox, QHBoxLayout, QVBoxLayout, QSlider, QLabel
from PyQt6.QtCore import Qt, pyqtSignal


class DrawbarPanel(QGroupBox):
    """Nine vertical drawbar sliders controlling harmonic amplitudes."""

    drawbar_changed = pyqtSignal(int, float)  # (index, value 0.0–1.0)

    def __init__(self, labels: list[str], initial_values: list[float]) -> None:
        super().__init__("Drawbars")
        self._sliders: list[QSlider] = []

        layout = QHBoxLayout()
        layout.setSpacing(10)

        for i, (label, value) in enumerate(zip(labels, initial_values)):
            col = QVBoxLayout()
            col.setSpacing(4)

            # Value label at top
            val_label = QLabel(str(int(value * 8)))
            val_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_label.setStyleSheet("color: #ffd700; font-size: 14px; font-weight: bold;")
            val_label.setFixedWidth(50)
            col.addWidget(val_label)

            # Vertical slider
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setMinimum(0)
            slider.setMaximum(8)
            slider.setValue(int(value * 8))
            slider.setMinimumHeight(150)
            slider.setFixedWidth(50)
            slider.setStyleSheet(self._slider_style(i))
            slider.valueChanged.connect(
                lambda v, idx=i, lbl=val_label: self._on_change(idx, v, lbl)
            )
            self._sliders.append(slider)
            col.addWidget(slider, alignment=Qt.AlignmentFlag.AlignCenter)

            # Footage label at bottom
            foot_label = QLabel(label)
            foot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            foot_label.setStyleSheet("color: #c0b0a0; font-size: 11px;")
            col.addWidget(foot_label)

            layout.addLayout(col)

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

    def _slider_style(self, index: int) -> str:
        # Alternate colors for visual variety (Hammond tradition: white/black drawbars)
        colors = [
            "#cc8844", "#cc8844",  # Brown (sub harmonics)
            "#dddddd",              # White
            "#cc8844",              # Brown
            "#222222",              # Black
            "#dddddd",              # White
            "#222222",              # Black
            "#222222",              # Black
            "#dddddd",              # White
        ]
        color = colors[index] if index < len(colors) else "#cc8844"
        return f"""
            QSlider::groove:vertical {{
                background: #2a1a0a;
                width: 18px;
                border-radius: 4px;
                border: 1px solid #5a4a3a;
            }}
            QSlider::handle:vertical {{
                background: {color};
                height: 20px;
                width: 30px;
                margin: -2px -8px;
                border-radius: 4px;
                border: 1px solid #888;
            }}
            QSlider::handle:vertical:hover {{
                border: 2px solid #ffd700;
            }}
        """

    def _on_change(self, index: int, value: int, label: QLabel) -> None:
        label.setText(str(value))
        self.drawbar_changed.emit(index, value / 8.0)
