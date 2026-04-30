#!/usr/bin/env python3
"""
ui/widgets.py — Reusable UI helpers and shared widgets.

Exports:
  make_label()       — styled QLabel factory
  make_btn()         — styled QPushButton factory
  hline()            — horizontal divider widget
  StatusBar          — top bar with user/language/online status
  SpinnerWidget      — animated loading spinner
  FingerprintWidget  — animated fingerprint scan visualisation
  BaseScreen         — abstract base for all screens
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, pyqtProperty,
    QPropertyAnimation, QEasingCurve,
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen,
    QRadialGradient,
)

from config import PALETTE, BTN_PRIMARY_QSS, BTN_SECONDARY_QSS, AppState, t


# ──────────────────────────────────────────────────────────────────────────────
#  Simple factories
# ──────────────────────────────────────────────────────────────────────────────
def make_label(text: str = "", size: int = 18, bold: bool = False,
               color: str = None, align=Qt.AlignLeft) -> QLabel:
    lbl = QLabel(text)
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setAlignment(align)
    style = "background: transparent;"
    if color:
        style += f" color: {color};"
    lbl.setStyleSheet(style)
    return lbl


def make_btn(text: str = "", primary: bool = True, size: int = 20) -> QPushButton:
    btn = QPushButton(text)
    font = QFont()
    font.setPointSize(size)
    font.setBold(True)
    btn.setFont(font)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(BTN_PRIMARY_QSS if primary else BTN_SECONDARY_QSS)
    return btn


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"background:{PALETTE['border']}; max-height:1px;")
    return line


# ──────────────────────────────────────────────────────────────────────────────
#  StatusBar
# ──────────────────────────────────────────────────────────────────────────────
class StatusBar(QWidget):
    """Top bar: ArtBridge brand | logged-in user | language | online/offline."""

    def __init__(self, nav_cb, parent=None):
        super().__init__(parent)
        self._nav_cb = nav_cb
        self.setFixedHeight(52)
        self.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {PALETTE['primary']},stop:1 {PALETTE['accent2']});"
            f"border-bottom: 2px solid {PALETTE['gold']};"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)

        brand = QLabel("🏺 ArtBridge")
        brand.setStyleSheet(f"color:{PALETTE['white']};font-size:18px;font-weight:bold;background:transparent;")
        lay.addWidget(brand)
        lay.addStretch()

        self.user_lbl = QLabel()
        self.user_lbl.setStyleSheet(f"color:{PALETTE['gold_lt']};font-size:14px;background:transparent;")
        lay.addWidget(self.user_lbl)

        self.lang_lbl = QLabel()
        self.lang_lbl.setStyleSheet(f"color:{PALETTE['gold_lt']};font-size:14px;background:transparent;")
        lay.addWidget(self.lang_lbl)

        self.net_btn = QPushButton()
        self.net_btn.setFixedSize(QSize(110, 32))
        self.net_btn.setCursor(Qt.PointingHandCursor)
        self.net_btn.setStyleSheet(
            f"background:{PALETTE['card']};color:{PALETTE['primary']};"
            f"border-radius:8px;font-size:13px;font-weight:bold;border:none;"
        )
        self.net_btn.clicked.connect(self._toggle_online)
        lay.addWidget(self.net_btn)

        self.refresh()

    def refresh(self):
        user = AppState.current_user
        self.user_lbl.setText(f"👤 {user[1]}" if user else "")
        self.lang_lbl.setText(f"  🌐 {AppState.language}  ")
        self.net_btn.setText(t("online") if AppState.is_online else t("offline"))

    def _toggle_online(self):
        AppState.is_online = not AppState.is_online
        self.refresh()
        if AppState.is_online and AppState.db:
            AppState.db.mark_all_synced()


# ──────────────────────────────────────────────────────────────────────────────
#  SpinnerWidget
# ──────────────────────────────────────────────────────────────────────────────
class SpinnerWidget(QWidget):
    """Simple animated arc spinner."""

    def __init__(self, size: int = 80, parent=None):
        super().__init__(parent)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def _tick(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        pen = QPen(QColor(PALETTE["primary"]), 6, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(4, 4, s - 8, s - 8, self._angle * 16, 270 * 16)

    def stop(self):
        self._timer.stop()


# ──────────────────────────────────────────────────────────────────────────────
#  FingerprintWidget
# ──────────────────────────────────────────────────────────────────────────────
class FingerprintWidget(QWidget):
    """Animated fingerprint scan progress visualisation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0
        self._active   = False
        self.setFixedSize(200, 200)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def start_scan(self):
        self._progress = 0
        self._active   = True
        self._timer.start(40)

    def stop_scan(self):
        self._timer.stop()
        self._active   = False
        self.update()

    def reset(self):
        self._progress = 0
        self._active   = False
        self._timer.stop()
        self.update()

    def _advance(self):
        self._progress = min(self._progress + 2, 100)
        self.update()
        if self._progress >= 100:
            self._timer.stop()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = 200

        # Background radial gradient circle
        grad = QRadialGradient(s // 2, s // 2, s // 2)
        grad.setColorAt(0, QColor(PALETTE["gold_lt"] + "80"))
        grad.setColorAt(1, QColor(PALETTE["bg2"]))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(PALETTE["accent"]), 3))
        p.drawEllipse(10, 10, s - 20, s - 20)

        # Fingerprint emoji
        p.setFont(QFont("Arial", 60))
        p.setPen(QColor(PALETTE["primary"]))
        p.drawText(self.rect(), Qt.AlignCenter, "👆")

        # Progress arc
        if self._active and self._progress > 0:
            pen = QPen(QColor(PALETTE["success"]), 8, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            span = int(self._progress * 3.6 * 16)
            p.drawArc(6, 6, s - 12, s - 12, 90 * 16, -span)


# ──────────────────────────────────────────────────────────────────────────────
#  BaseScreen
# ──────────────────────────────────────────────────────────────────────────────
class BaseScreen(QWidget):
    """
    Abstract base for every kiosk screen.

    Subclasses must call `_build_ui()` from their `__init__`.
    Override `on_enter()` to refresh labels / trigger voice when screen
    becomes visible.
    """

    navigate = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {PALETTE['bg']};")

    # ── Lifecycle hook ────────────────────────────────────────────────────────
    def on_enter(self):
        """Called by KioskWindow when this screen becomes active."""
        pass

    # ── Convenience helpers ───────────────────────────────────────────────────
    def _speak(self, key_or_text: str):
        """Queue *key_or_text* for TTS (non-blocking)."""
        if AppState.voice:
            AppState.voice.speak(key_or_text)

    def _header(self, key: str, subtitle_key: str = None) -> QWidget:
        """Return a styled section header widget."""
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(4)
        title = make_label(t(key), size=24, bold=True,
                           color=PALETTE["primary"], align=Qt.AlignCenter)
        lay.addWidget(title)
        if subtitle_key:
            sub = make_label(t(subtitle_key), size=15,
                             color=PALETTE["text_sec"], align=Qt.AlignCenter)
            lay.addWidget(sub)
        lay.addWidget(hline())
        return w
