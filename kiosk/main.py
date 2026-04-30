#!/usr/bin/env python3
"""
main.py — ArtBridge Kiosk entry point.

Wires together:
  - DatabaseManager   (database.py)
  - VoiceEngine       (voice/engine.py)
  - FingerprintSensor (fingerprint/sensor.py)
  - KioskWindow       (this file)
  - All UI screens    (ui/)

Run:
    python3 main.py               # auto-detect sensor (falls back to mock)
    python3 main.py --mock        # force mock sensor (dev mode)
    python3 main.py --port /dev/ttyUSB1   # custom serial port
"""

import sys
import argparse

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QStackedWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QFontDatabase, QColor, QPalette

from config import PALETTE, GLOBAL_QSS, AppState

from database import DatabaseManager
from voice_engine import VoiceEngine
from sensor import get_sensor

from widgets import StatusBar
from screens_intro import LanguageSelectionScreen, WelcomeScreen
from screens_auth  import LoginScreen, RegisterScreen
from screens_main  import (
    DashboardScreen, AddProductFlow,
    MyProductsScreen, EarningsScreen, OrdersScreen,
)


# ──────────────────────────────────────────────────────────────────────────────
#  KioskWindow
# ──────────────────────────────────────────────────────────────────────────────
class KioskWindow(QMainWindow):
    """
    Top-level window.  Owns the screen stack and routes navigate() signals.
    Status bar is hidden on the language/welcome/login screens.
    """

    # Screens that should NOT show the top status bar
    _NO_STATUSBAR = {"language", "welcome", "login", "register"}

    def __init__(self):
        super().__init__()
        self._init_singletons()
        self._build_window()
        self._register_screens()
        self._navigate("language")
        self.showFullScreen()

    # ── Singletons ────────────────────────────────────────────────────────────
    def _init_singletons(self):
        AppState.db     = DatabaseManager()
        AppState.voice  = VoiceEngine()
        
        # Determine port, falling back to /dev/ttyUSB0 if not specified
        port = _ARGS.port if (_ARGS and _ARGS.port) else "/dev/ttyUSB0"
        mock = _ARGS.mock if _ARGS else False
        
        AppState.sensor = get_sensor(
            port="/dev/ttyUSB0",
            baud=57600,
            force_mock=mock,
        )

    # ── Window / layout ───────────────────────────────────────────────────────
    def _build_window(self):
        self.setWindowTitle("ArtBridge Kiosk")
        self.setStyleSheet(GLOBAL_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        self.status_bar = StatusBar(self._navigate, self)
        main_lay.addWidget(self.status_bar)

        self.stack = QStackedWidget()
        main_lay.addWidget(self.stack)

    # ── Screen registry ───────────────────────────────────────────────────────
    def _register_screens(self):
        self._screens = {}
        screen_map = [
            ("language",    LanguageSelectionScreen),
            ("welcome",     WelcomeScreen),
            ("login",       LoginScreen),
            ("register",    RegisterScreen),
            ("dashboard",   DashboardScreen),
            ("add_product", AddProductFlow),
            ("my_products", MyProductsScreen),
            ("earnings",    EarningsScreen),
            ("orders",      OrdersScreen),
        ]
        for name, cls in screen_map:
            screen = cls()
            screen.navigate.connect(self._navigate)
            self.stack.addWidget(screen)
            self._screens[name] = screen

    # ── Navigation ────────────────────────────────────────────────────────────
    def _navigate(self, name: str):
        print(f"[Nav] Navigating to: {name!r}")
        screen = self._screens.get(name)
        if not screen:
            print(f"[Nav] unknown screen: {name!r}")
            return

        # Notify departing screen — lets camera stop cleanly
        current = self.stack.currentWidget()
        if current and hasattr(current, "on_leave"):
            current.on_leave()

        hide_bar = name in self._NO_STATUSBAR
        self.status_bar.setVisible(not hide_bar)
        if not hide_bar:
            self.status_bar.refresh()

        self.stack.setCurrentWidget(screen)
        screen.on_enter()

    # ── Key events ────────────────────────────────────────────────────────────
    def keyPressEvent(self, e):
        """ESC → quit (development only).  F11 → toggle fullscreen."""
        if e.key() == Qt.Key_Escape:
            self.close()
        elif e.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        super().keyPressEvent(e)

    def closeEvent(self, e):
        if AppState.voice:
            AppState.voice.shutdown()
        super().closeEvent(e)


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────
_ARGS = None


def _parse_args():
    global _ARGS
    p = argparse.ArgumentParser(description="ArtBridge Kiosk")
    p.add_argument("--mock",  action="store_true",
                   help="Force mock fingerprint sensor (for development)")
    p.add_argument("--port",  default="/dev/ttyUSB0",
                   help="Serial port for fingerprint sensor (e.g. /dev/ttyUSB0)")
    p.add_argument("--windowed", action="store_true",
                   help="Run in a window instead of fullscreen")
    _ARGS = p.parse_args()


def main():
    _parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("ArtBridge")
    app.setOrganizationName("ArtBridge India")

    # Prefer Noto Sans for Indian script support
    db = QFontDatabase()
    for family in ["Noto Sans", "Noto Serif", "FreeSans", "Arial Unicode MS"]:
        if family in db.families():
            app.setFont(QFont(family, 14))
            break

    # Global colour palette
    palette = QPalette()
    palette.setColor(QPalette.Window,     QColor(PALETTE["bg"]))
    palette.setColor(QPalette.WindowText, QColor(PALETTE["text"]))
    palette.setColor(QPalette.Base,       QColor(PALETTE["card"]))
    palette.setColor(QPalette.Button,     QColor(PALETTE["primary"]))
    palette.setColor(QPalette.ButtonText, QColor(PALETTE["white"]))
    palette.setColor(QPalette.Highlight,  QColor(PALETTE["gold"]))
    app.setPalette(palette)

    win = KioskWindow()

    if _ARGS and _ARGS.windowed:
        win.showNormal()
        win.resize(800, 600)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
