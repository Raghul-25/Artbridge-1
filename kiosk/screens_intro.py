#!/usr/bin/env python3
"""
ui/screens_intro.py — Language selection and Welcome screens.
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from config import PALETTE, BTN_LANG_QSS, TRANSLATIONS, AppState, t
from widgets import BaseScreen, make_label, make_btn


# ──────────────────────────────────────────────────────────────────────────────
#  1. LANGUAGE SELECTION SCREEN
# ──────────────────────────────────────────────────────────────────────────────
class LanguageSelectionScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 30, 30, 30)
        outer.setSpacing(20)

        # Banner
        banner = QWidget()
        banner.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {PALETTE['primary']},stop:1 {PALETTE['accent2']});"
            f"border-radius:20px;"
        )
        b_lay = QVBoxLayout(banner)
        b_lay.setContentsMargins(20, 20, 20, 20)
        b_lay.addWidget(make_label("🏺  ArtBridge", 28, True,
                                   PALETTE["white"], Qt.AlignCenter))
        b_lay.addWidget(make_label(
            "Select Your Language · अपनी भाषा चुनें · மொழி தேர்ந்தெடுக்கவும்",
            14, False, PALETTE["gold_lt"], Qt.AlignCenter))
        outer.addWidget(banner)

        # Language grid (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        grid_w = QWidget()
        grid_w.setStyleSheet(f"background: {PALETTE['bg']};")
        grid = QGridLayout(grid_w)
        grid.setSpacing(14)

        for i, (lang, info) in enumerate(TRANSLATIONS.items()):
            btn = QPushButton(f"{info['flag']}\n{info['name']}")
            btn.setStyleSheet(BTN_LANG_QSS)
            btn.setCheckable(True)
            btn.setFont(QFont("", 16, QFont.Bold))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, l=lang: self._select_lang(l))
            grid.addWidget(btn, i // 3, i % 3)

        scroll.setWidget(grid_w)
        outer.addWidget(scroll)

        # Continue button
        cont = make_btn("▶  Continue / जारी रखें / தொடர்க", primary=True, size=20)
        cont.clicked.connect(lambda: self.navigate.emit("welcome"))
        outer.addWidget(cont)

    def _select_lang(self, lang: str):
        AppState.language = lang
        if AppState.voice:
            AppState.voice.set_language(lang)
            AppState.voice.speak("select_language")

    def on_enter(self):
        pass   # No status bar on language screen


# ──────────────────────────────────────────────────────────────────────────────
#  2. WELCOME SCREEN
# ──────────────────────────────────────────────────────────────────────────────
class WelcomeScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 60, 40, 40)
        lay.setSpacing(30)
        lay.setAlignment(Qt.AlignCenter)

        deco = QLabel("🏺")
        deco.setFont(QFont("Arial", 80))
        deco.setAlignment(Qt.AlignCenter)
        deco.setStyleSheet("background:transparent;")
        lay.addWidget(deco)

        self.title_lbl = make_label("", 28, True, PALETTE["primary"], Qt.AlignCenter)
        lay.addWidget(self.title_lbl)

        self.tag_lbl = make_label("", 18, False, PALETTE["text_sec"], Qt.AlignCenter)
        lay.addWidget(self.tag_lbl)

        lay.addSpacing(10)
        div = QLabel("✦  ✦  ✦")
        div.setAlignment(Qt.AlignCenter)
        div.setStyleSheet(f"color:{PALETTE['gold']};font-size:20px;background:transparent;")
        lay.addWidget(div)
        lay.addSpacing(10)

        self.start_btn = make_btn("", primary=True, size=22)
        self.start_btn.setFixedHeight(80)
        self.start_btn.clicked.connect(lambda: self.navigate.emit("login"))
        lay.addWidget(self.start_btn)

        lang_btn = make_btn("🌐  Change Language", primary=False, size=16)
        lang_btn.setFixedHeight(60)
        lang_btn.clicked.connect(lambda: self.navigate.emit("language"))
        lay.addWidget(lang_btn)

    def on_enter(self):
        self.title_lbl.setText(t("welcome"))
        self.tag_lbl.setText(t("tagline"))
        self.start_btn.setText(t("start"))
        self._speak("welcome")
