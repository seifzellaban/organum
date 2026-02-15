"""Stop panel — toggle buttons for organ stops with fighter-jet aesthetics.

Stops are organized into functional groups (families). The Tremulant
gets a distinct visual treatment as it's an effect, not a pipe rank.
"""

from PyQt6.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt
from stops.profiles import STOP_DEFS


# ── Stop organization by family ─────────────────────────────────────
# Order matters: this is the display order in each section.
STOP_FAMILIES: dict[str, list[str]] = {
    "Foundation": [
        "Bourdon 16'",
        "Principal 8'",
        "Flute 8'",
        "Gedackt 8'",
    ],
    "Brilliance": [
        "Octave 4'",
        "Super Oct 2'",
        "Mixture",
    ],
    "Reeds & Color": [
        "Reed 8'",
        "Trumpet 8'",
        "Voix Humaine",
        "Vox Celeste",
    ],
}


class StopPanel(QGroupBox):
    """Grid of toggle buttons for organ stops, grouped by family."""

    stop_toggled = pyqtSignal(str, bool)

    def __init__(self, stop_names: list[str], active_stops: set[str]) -> None:
        super().__init__("Organ Stops")
        self._buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout()
        outer.setSpacing(8)

        # ── Family sections ──────────────────────────────────────────
        families_row = QHBoxLayout()
        families_row.setSpacing(12)

        for family_name, family_stops in STOP_FAMILIES.items():
            section = self._build_family_section(
                family_name, family_stops, active_stops
            )
            families_row.addWidget(section)

        outer.addLayout(families_row)

        # ── Separator ────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #5a4a3a; max-height: 1px;")
        outer.addWidget(sep)

        # ── Tremulant — special effect, distinct visual ──────────────
        trem_row = QHBoxLayout()
        trem_row.addStretch()

        trem_btn = QPushButton("⚡  TREMULANT  ⚡")
        trem_btn.setCheckable(True)
        trem_btn.setChecked("Tremulant" in active_stops)
        trem_btn.setMinimumHeight(38)
        trem_btn.setMinimumWidth(220)
        trem_btn.setStyleSheet(
            self._tremulant_style("Tremulant" in active_stops)
        )
        trem_btn.clicked.connect(
            lambda checked: self._on_toggle("Tremulant", checked)
        )
        self._buttons["Tremulant"] = trem_btn
        trem_row.addWidget(trem_btn)

        trem_row.addStretch()
        outer.addLayout(trem_row)

        self.setLayout(outer)
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

    def _build_family_section(
        self,
        family_name: str,
        stop_names: list[str],
        active_stops: set[str],
    ) -> QGroupBox:
        """Build a bordered sub-section for a stop family."""
        group = QGroupBox(family_name)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 11px;
                font-weight: bold;
                color: #a09080;
                border: 1px solid #3a2a1a;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 14px;
                padding-bottom: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)

        grid = QGridLayout()
        grid.setSpacing(5)
        cols = 2

        for idx, name in enumerate(stop_names):
            stop_def = STOP_DEFS.get(name)
            if stop_def is None:
                continue

            # Build label: show pitch info for mutations
            label = name
            if stop_def.is_mutation:
                label = f"◆ {name}"

            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(name in active_stops)
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(110)
            btn.setStyleSheet(self._button_style(name in active_stops))
            btn.setToolTip(self._stop_tooltip(name, stop_def))
            btn.clicked.connect(
                lambda checked, n=name: self._on_toggle(n, checked)
            )
            self._buttons[name] = btn
            grid.addWidget(btn, idx // cols, idx % cols)

        group.setLayout(grid)
        return group

    def _stop_tooltip(self, name: str, stop_def) -> str:
        """Generate a helpful tooltip describing the stop's purpose."""
        tips = {
            "Principal 8'": "Foundation tone — the backbone of the organ.",
            "Flute 8'": "Soft, pure tone — gentle and warm.",
            "Gedackt 8'": "Covered flute — hollow, woody character.",
            "Octave 4'": "Bright principal, one octave higher.",
            "Reed 8'": "Buzzy reed tone — rich and colorful.",
            "Mixture": "Multiple upper harmonics — adds brilliance.",
            "Bourdon 16'": "Deep sub-bass pedal tone — foundation.",
            "Vox Celeste": "Ethereal string with chorus — celestial shimmer.",
            "Trumpet 8'": "⚡ Blazing solo reed — cuts through everything.",
            "Super Oct 2'": "High principal — sizzle and brilliance.",
            "Voix Humaine": "Quivering imitative reed — eerie, voice-like. Try with Tremulant!",
        }
        return tips.get(name, name)

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

    def _tremulant_style(self, active: bool) -> str:
        """Distinct visual for the Tremulant — fighter-jet switch feel."""
        if active:
            return """
                QPushButton {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #b22222, stop:0.5 #ff4500, stop:1 #b22222
                    );
                    color: #ffffff;
                    border: 2px solid #ff6347;
                    border-radius: 6px;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 8px 16px;
                    letter-spacing: 2px;
                }
                QPushButton:hover {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #cc3333, stop:0.5 #ff5722, stop:1 #cc3333
                    );
                }
            """
        return """
            QPushButton {
                background-color: #2a1a1a;
                color: #884040;
                border: 2px solid #5a2a2a;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                letter-spacing: 2px;
            }
            QPushButton:hover {
                background-color: #3a2020;
                color: #aa5050;
                border-color: #7a3a3a;
            }
        """

    def _on_toggle(self, name: str, checked: bool) -> None:
        btn = self._buttons[name]
        if name == "Tremulant":
            btn.setStyleSheet(self._tremulant_style(checked))
        else:
            btn.setStyleSheet(self._button_style(checked))
        self.stop_toggled.emit(name, checked)
