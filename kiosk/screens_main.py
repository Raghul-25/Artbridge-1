#!/usr/bin/env python3
"""
screens_main.py  —  Post-login screens.

Based on the original version (warm terracotta theme, original layouts).
Changes from original:
  • Real ML model integrated (ml_service.py / model.h5)
  • AddProductFlow bug-fixes (correct step indices, editable name+desc fields,
    fixed camera size, on_leave camera stop, description saved to DB)
  • MyProductsScreen  —  replaced list with 2-column image-card grid
    (image on top, product name + description below — as requested)
  • Demo-mode skip button on Login kept
"""

import os
import threading

# ── ML model ──────────────────────────────────────────────────────────────────
try:
    from ml_service import detector as _ml_detector
    print("[App] ✅ ML model ready.")
except Exception as _e:
    print(f"[App] ⚠️  ML model unavailable ({_e}) — using placeholder.")
    _ml_detector = None

try:
    from camera_service import CameraService
    _CAMERA_SERVICE_AVAILABLE = True
except Exception as _ce:
    print(f"[App] ⚠️  camera_service unavailable ({_ce})")
    _CAMERA_SERVICE_AVAILABLE = False

# ── Cloud Sync ──────────────────────────────────────────────────────────────
try:
    from s3_uploader import upload_product_images
    from sync import sync_products_to_dynamo
    _CLOUD_SYNC_AVAILABLE = True
except Exception as _se:
    print(f"[App] ⚠️  Cloud sync modules unavailable ({_se})")
    _CLOUD_SYNC_AVAILABLE = False

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QLineEdit, QWidget,
    QProgressBar, QFrame, QStackedWidget, QTextEdit, QSizePolicy,
    QSlider,
)
from PyQt5.QtGui import QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QMetaObject, Q_ARG

from config import PALETTE, AppState, t
from widgets import BaseScreen, SpinnerWidget, make_label, make_btn, hline


def detect_product(image_path: str) -> tuple:
    if _ml_detector is not None:
        return _ml_detector.predict(image_path)
    return (
        "Handcrafted Artisan Product",
        "A unique handcrafted product made by a skilled rural artisan "
        "using traditional techniques and natural materials.",
    )


# ──────────────────────────────────────────────────────────────────────────────
#  4. DASHBOARD  (original)
# ──────────────────────────────────────────────────────────────────────────────
class DashboardScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setSpacing(16)

        self.hello_lbl = make_label("", 22, True, PALETTE["primary"], Qt.AlignCenter)
        lay.addWidget(self.hello_lbl)
        lay.addWidget(hline())

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self.rev_card  = self._stat_card("💰", "₹0", "Revenue")
        self.ord_card  = self._stat_card("📋", "0",  "Orders")
        self.pend_card = self._stat_card("⏳", "0",  "Pending")
        for c in (self.rev_card, self.ord_card, self.pend_card):
            stats_row.addWidget(c)
        lay.addLayout(stats_row)
        lay.addWidget(hline())

        nav_grid = QGridLayout()
        nav_grid.setSpacing(14)
        nav_items = [
            ("➕  Add Product",  "add_product", True),
            ("📦  My Products",  "my_products", True),
            ("📋  Orders",       "orders",      False),
            ("💰  Earnings",     "earnings",    False),
        ]
        for i, (label, route, primary) in enumerate(nav_items):
            btn = make_btn(label, primary=primary, size=18)
            btn.setFixedHeight(90)
            btn.clicked.connect(lambda _, r=route: self.navigate.emit(r))
            nav_grid.addWidget(btn, i // 2, i % 2)
        lay.addLayout(nav_grid)

        # ── Logout button ────────────────────────────────────────────────────
        logout_btn = QPushButton("🔒  Logout")
        logout_btn.setFixedHeight(58)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setFont(QFont("", 16, QFont.Bold))
        logout_btn.setStyleSheet(
            f"QPushButton{{background:{PALETTE['card']};color:{PALETTE['error']};"
            f"border:2px solid {PALETTE['error']};border-radius:12px;"
            f"font-size:16px;font-weight:bold;}}"
            f"QPushButton:pressed{{background:#FDECEA;}}"
        )
        logout_btn.clicked.connect(self._logout)
        lay.addWidget(logout_btn)

    def _stat_card(self, icon, value, label) -> QWidget:
        card = QWidget()
        card.setStyleSheet(
            f"background:{PALETTE['card']};border-radius:14px;"
            f"border:1px solid {PALETTE['border']};"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(4)
        ico = QLabel(icon)
        ico.setFont(QFont("Arial", 26))
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        cl.addWidget(ico)
        val = make_label(value, 20, True, PALETTE["primary"], Qt.AlignCenter)
        val.setObjectName("val")
        cl.addWidget(val)
        cl.addWidget(make_label(label, 13, False, PALETTE["text_sec"], Qt.AlignCenter))
        return card

    def on_enter(self):
        user = AppState.current_user
        name = user[1] if user else "Artisan"
        self.hello_lbl.setText(f"{t('hello')}, {name}! 👋")
        self._speak("hello")
        self._refresh_stats()

    def _logout(self):
        """Clear current user session and navigate back to login screen."""
        AppState.current_user = None
        self.navigate.emit("login")

    def _refresh_stats(self):
        if not AppState.db:
            return
        rev, total, pending, _ = AppState.db.get_earnings()
        for card, text in zip(
            (self.rev_card, self.ord_card, self.pend_card),
            (f"₹{rev:,.0f}", str(total), str(pending)),
        ):
            card.findChild(QLabel, "val").setText(text)


# ──────────────────────────────────────────────────────────────────────────────
#  5. ADD PRODUCT FLOW  (fixed version with ML)
# ──────────────────────────────────────────────────────────────────────────────
class AddProductFlow(BaseScreen):
    """
    4-step wizard:
      Step 0 — Capture photo
      Step 1 — AI detection (real model, editable name + description)
      Step 2 — Set price
      Step 3 — Confirm & save
    """

    STEPS = 4
    _STEP_META = [
        ("📷  Step 1 / 4 — Capture Photo",        "photo_hint"),
        ("🤖  Step 2 / 4 — AI Product Detection",  "ml_hint"),
        ("💰  Step 3 / 4 — Set Price",             "price_hint"),
        ("✅  Step 4 / 4 — Confirm Product",        "confirm_hint"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._step         = 0
        self._product_name = ""
        self._product_desc = ""
        self._price        = 100.0
        self._photo_paths  = [None, None, None, None]
        self._active_slot  = 0
        self._cam          = None     # CameraService instance
        self._cam_timer    = None
        # Legacy attrs kept so any residual references don't crash
        self._cap          = None
        self._build_ui()

    # ── Convenience: primary photo for ML inference ────────────────────────
    @property
    def _photo_path(self):
        """Return first captured photo (slot 0), or None."""
        for p in self._photo_paths:
            if p and p != "placeholder":
                return p
        if "placeholder" in self._photo_paths:
            return "placeholder"
        return None

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setSpacing(12)

        self.header_lbl = make_label("", 20, True, PALETTE["primary"], Qt.AlignCenter)
        lay.addWidget(self.header_lbl)

        self.progress = QProgressBar()
        self.progress.setRange(0, self.STEPS)
        self.progress.setValue(0)
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            f"QProgressBar{{background:{PALETTE['bg2']};border-radius:5px;border:none;}}"
            f"QProgressBar::chunk{{background:{PALETTE['primary']};border-radius:5px;}}"
        )
        lay.addWidget(self.progress)

        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_step0())   # 0 — camera
        self.stack.addWidget(self._build_step1())   # 1 — AI
        self.stack.addWidget(self._build_step2())   # 2 — price
        self.stack.addWidget(self._build_step3())   # 3 — confirm

        nav = QHBoxLayout()
        self.back_btn = make_btn(t("back"), primary=False, size=16)
        self.back_btn.setFixedHeight(60)
        self.back_btn.clicked.connect(self._go_back)
        nav.addWidget(self.back_btn)

        self.next_btn = make_btn("▶  Next", primary=True, size=18)
        self.next_btn.setFixedHeight(70)
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)
        lay.addLayout(nav)

    # ── Step 0: Camera — Amazon-style 4-photo capture ──────────────────────
    def _build_step0(self) -> QWidget:
        """
        Layout (800 wide):
          ┌──────────┬───────────────────────────────┬──────────┐
          │ [Slot 1] │   LIVE CAMERA PREVIEW          │ [Slot 3] │
          │ [Slot 2] │   560 × 310  (centred)         │ [Slot 4] │
          └──────────┴───────────────────────────────┴──────────┘
              ◀ prev     [Start] [Capture] [Retake]     next ▶
                    Status: "Photo 2 of 4"
        """
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        # ── Status text ───────────────────────────────────────────────────
        self.photo_status = make_label(
            "Tap Start Camera to begin", 14, False, PALETTE["text_sec"], Qt.AlignCenter
        )
        root.addWidget(self.photo_status)

        # ── Main 3-column row: left slots | preview | right slots ─────────
        row = QHBoxLayout()
        row.setSpacing(8)

        # LEFT column — slots 1 & 2
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.setAlignment(Qt.AlignVCenter)

        # RIGHT column — slots 3 & 4
        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        right_col.setAlignment(Qt.AlignVCenter)

        SLOT_W, SLOT_H = 100, 90
        self._slot_labels = []
        for i in range(4):
            lbl = QLabel()
            lbl.setFixedSize(SLOT_W, SLOT_H)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"background:{PALETTE['bg2']};border-radius:8px;"
                f"border:2px solid {PALETTE['border']};font-size:22px;"
            )
            lbl.setText("📷\n" + str(i+1))
            lbl.setFont(QFont("Arial", 11))
            lbl.mousePressEvent = lambda e, idx=i: self._select_slot(idx)
            lbl.setCursor(Qt.PointingHandCursor)
            self._slot_labels.append(lbl)
            if i < 2:
                left_col.addWidget(lbl)
            else:
                right_col.addWidget(lbl)

        # Centre — live preview
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(560, 310)
        self.camera_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.camera_label.setStyleSheet(
            "background:#1a1a1a;border-radius:12px;"
            f"border:3px solid {PALETTE['primary']};"
        )
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setScaledContents(False)
        self.camera_label.setText("📷")
        self.camera_label.setFont(QFont("Arial", 56))

        row.addLayout(left_col)
        row.addWidget(self.camera_label, 0, Qt.AlignVCenter)
        row.addLayout(right_col)
        root.addLayout(row)

        # ── Button row ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.cam_start_btn = make_btn("📷  Start Camera", primary=False, size=15)
        self.cam_start_btn.setFixedHeight(62)
        self.cam_start_btn.clicked.connect(self._start_camera)
        btn_row.addWidget(self.cam_start_btn, 1)

        self.capture_btn = make_btn("✅  Capture", primary=True, size=15)
        self.capture_btn.setFixedHeight(62)
        self.capture_btn.setEnabled(False)
        self.capture_btn.clicked.connect(self._capture_photo)
        btn_row.addWidget(self.capture_btn, 1)

        self.retake_btn = make_btn("🔄  Retake", primary=False, size=15)
        self.retake_btn.setFixedHeight(62)
        self.retake_btn.setEnabled(False)
        self.retake_btn.clicked.connect(self._retake_photo)
        btn_row.addWidget(self.retake_btn, 1)

        root.addLayout(btn_row)
        return w

    # ── Step 1: AI Detection ────────────────────────────────────────────────
    def _build_step1(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(12)

        # --- Scanning animation (shown while ML runs) ---
        self.detect_widget = QWidget()
        det_lay = QVBoxLayout(self.detect_widget)
        det_lay.setAlignment(Qt.AlignCenter)
        det_lay.setSpacing(10)

        self.detect_icon = QLabel("🤖")
        self.detect_icon.setFont(QFont("Arial", 56))
        self.detect_icon.setAlignment(Qt.AlignCenter)
        self.detect_icon.setStyleSheet("background:transparent;")
        det_lay.addWidget(self.detect_icon)

        self.detect_status = make_label(
            t("detecting"), 16, False, PALETTE["text_sec"], Qt.AlignCenter
        )
        det_lay.addWidget(self.detect_status)

        self._bars = []
        for cat in ["Identifying…", "Classifying…", "Generating name…", "Writing description…"]:
            row = QHBoxLayout()
            lbl = make_label(cat, 13, False, PALETTE["text_sec"])
            lbl.setFixedWidth(170)
            row.addWidget(lbl)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(16)
            bar.setTextVisible(False)
            bar.setStyleSheet(
                f"QProgressBar{{background:{PALETTE['bg2']};border-radius:8px;border:none;}}"
                f"QProgressBar::chunk{{background:{PALETTE['gold']};border-radius:8px;}}"
            )
            row.addWidget(bar)
            self._bars.append(bar)
            det_lay.addLayout(row)

        lay.addWidget(self.detect_widget)

        # --- Edit fields (shown after ML finishes) ---
        self.edit_widget = QWidget()
        self.edit_widget.setVisible(False)
        edit_lay = QVBoxLayout(self.edit_widget)
        edit_lay.setContentsMargins(0, 0, 0, 0)
        edit_lay.setSpacing(8)

        # "Not recognised" warning banner — shown only when ML fails
        self.not_recognised_banner = QWidget()
        self.not_recognised_banner.setVisible(False)
        self.not_recognised_banner.setStyleSheet(
            f"background:#FFF3CD;border:2px solid {PALETTE['gold']};"
            f"border-radius:10px;"
        )
        nb_lay = QHBoxLayout(self.not_recognised_banner)
        nb_lay.setContentsMargins(14, 10, 14, 10)
        nb_lay.setSpacing(10)
        warn_ico = QLabel("⚠️")
        warn_ico.setFont(QFont("Arial", 22))
        warn_ico.setStyleSheet("background:transparent;")
        nb_lay.addWidget(warn_ico)
        warn_txt = QLabel(
            "<b>Product not recognised.</b><br>"
            "Please type your product name and description below."
        )
        warn_txt.setWordWrap(True)
        warn_txt.setStyleSheet(
            f"color:#856404;font-size:15px;background:transparent;"
        )
        nb_lay.addWidget(warn_txt, 1)
        edit_lay.addWidget(self.not_recognised_banner)

        # Product Name label + large input
        edit_lay.addWidget(
            make_label("Product Name", 16, True, PALETTE["text"])
        )
        self.name_input = QLineEdit()
        self.name_input.setFixedHeight(58)
        self.name_input.setPlaceholderText("e.g. Clay Pot, Bamboo Basket…")
        self.name_input.setStyleSheet(
            f"font-size:18px;padding:10px 14px;"
            f"border:2px solid {PALETTE['border']};border-radius:10px;"
            f"background:{PALETTE['card']};color:{PALETTE['text']};"
        )
        edit_lay.addWidget(self.name_input)

        # Product Description label + input
        edit_lay.addWidget(
            make_label("Product Description", 16, True, PALETTE["text"])
        )
        self.desc_input = QTextEdit()
        self.desc_input.setFixedHeight(110)
        self.desc_input.setPlaceholderText("Describe your product…")
        edit_lay.addWidget(self.desc_input)

        lay.addWidget(self.edit_widget)
        lay.addStretch()
        return w

    # ── Step 2: Price ───────────────────────────────────────────────────────
    def _build_step2(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(20)

        ico = QLabel("💰")
        ico.setFont(QFont("Arial", 56))
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        lay.addWidget(ico)

        lay.addWidget(
            make_label(t("price_hint"), 16, False, PALETTE["text_sec"], Qt.AlignCenter)
        )

        self.price_display = make_label("₹100", 36, True, PALETTE["primary"], Qt.AlignCenter)
        lay.addWidget(self.price_display)

        self.price_slider = QSlider(Qt.Horizontal)
        self.price_slider.setRange(0, 15000)
        self.price_slider.setValue(100)
        self.price_slider.setTickInterval(1000)
        self.price_slider.setFixedHeight(44)
        self.price_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:8px;background:{PALETTE['bg2']};border-radius:4px;}}"
            f"QSlider::handle:horizontal{{width:36px;height:36px;margin:-14px 0;"
            f"border-radius:18px;background:{PALETTE['primary']};border:3px solid {PALETTE['white']};}}"
            f"QSlider::sub-page:horizontal{{background:{PALETTE['primary']};border-radius:4px;}}"
        )
        self.price_slider.valueChanged.connect(
            lambda v: self.price_display.setText(f"₹{v:,}")
        )
        lay.addWidget(self.price_slider)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)
        for p in [100, 500, 1000, 5000]:
            qb = QPushButton(f"₹{p:,}")
            qb.setFixedHeight(50)
            qb.setCursor(Qt.PointingHandCursor)
            qb.setStyleSheet(
                f"QPushButton{{background:{PALETTE['card']};color:{PALETTE['primary']};"
                f"border:2px solid {PALETTE['accent']};border-radius:10px;"
                f"font-size:16px;font-weight:bold;}}"
                f"QPushButton:pressed{{background:{PALETTE['bg2']};}}"
            )
            qb.clicked.connect(lambda _, v=p: (
                self.price_slider.setValue(v),
                self.price_display.setText(f"₹{v:,}"),
            ))
            quick_row.addWidget(qb)
        lay.addLayout(quick_row)
        return w

    # ── Step 3: Confirm ─────────────────────────────────────────────────────
    def _build_step3(self) -> QWidget:
        """
        Confirm screen layout:
          ┌─────────────────────────────────────────────────────┐
          │  [img1] [img2] [img3] [img4]   ← 4-photo strip     │
          ├─────────────────────────────────────────────────────┤
          │  Product Name                                       │
          │  ₹ Price                                            │
          │  Description…                                       │
          ├─────────────────────────────────────────────────────┤
          │  [✏️ Edit]          [✅ Confirm & Save]             │
          └─────────────────────────────────────────────────────┘
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(12)

        # ── Swipeable photo preview (large, fills card width) ─────────────
        conf_viewer_h = 200
        conf_photo_w = QWidget()
        conf_photo_w.setFixedHeight(conf_viewer_h)
        conf_photo_w.setStyleSheet(
            f"background:{PALETTE['bg2']};border-radius:10px;"
        )
        cv_lay = QHBoxLayout(conf_photo_w)
        cv_lay.setContentsMargins(0, 0, 0, 0)
        cv_lay.setSpacing(0)

        self._conf_photo_idx  = [0]
        self._conf_photo_list = []    # filled in _enter_step3

        self._conf_left_btn = QPushButton("◀")
        self._conf_left_btn.setFixedSize(36, conf_viewer_h)
        self._conf_left_btn.setStyleSheet(
            "QPushButton{background:rgba(0,0,0,0.20);color:white;"
            "border:none;border-radius:10px 0 0 10px;"
            "font-size:18px;font-weight:bold;}"
            "QPushButton:pressed{background:rgba(0,0,0,0.40);}"
        )
        self._conf_left_btn.setCursor(Qt.PointingHandCursor)
        self._conf_left_btn.clicked.connect(lambda: self._conf_navigate(-1))

        self._conf_img_lbl = QLabel()
        self._conf_img_lbl.setAlignment(Qt.AlignCenter)
        self._conf_img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._conf_img_lbl.setStyleSheet("background:transparent;")

        self._conf_dot_lbl = QLabel()
        self._conf_dot_lbl.setAlignment(Qt.AlignCenter)
        self._conf_dot_lbl.setStyleSheet(
            "background:rgba(0,0,0,0.45);color:white;"
            "font-size:12px;border-radius:8px;padding:2px 10px;"
        )

        self._conf_right_btn = QPushButton("▶")
        self._conf_right_btn.setFixedSize(36, conf_viewer_h)
        self._conf_right_btn.setStyleSheet(
            "QPushButton{background:rgba(0,0,0,0.20);color:white;"
            "border:none;border-radius:0 10px 10px 0;"
            "font-size:18px;font-weight:bold;}"
            "QPushButton:pressed{background:rgba(0,0,0,0.40);}"
        )
        self._conf_right_btn.setCursor(Qt.PointingHandCursor)
        self._conf_right_btn.clicked.connect(lambda: self._conf_navigate(1))

        centre_w = QWidget()
        centre_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cent_lay = QVBoxLayout(centre_w)
        cent_lay.setContentsMargins(0, 0, 0, 4)
        cent_lay.setSpacing(0)
        cent_lay.addWidget(self._conf_img_lbl, 1)
        dot_row = QHBoxLayout()
        dot_row.addStretch()
        dot_row.addWidget(self._conf_dot_lbl)
        dot_row.addStretch()
        cent_lay.addLayout(dot_row)

        cv_lay.addWidget(self._conf_left_btn)
        cv_lay.addWidget(centre_w, 1)
        cv_lay.addWidget(self._conf_right_btn)
        lay.addWidget(conf_photo_w)

        # ── Product details ────────────────────────────────────────────────
        details = QWidget()
        details.setStyleSheet(
            f"background:{PALETTE['card']};border-radius:10px;"
            f"border:1px solid {PALETTE['border']};"
        )
        dl = QVBoxLayout(details)
        dl.setContentsMargins(16, 12, 16, 12)
        dl.setSpacing(6)

        self.conf_name  = make_label("", 18, True,  PALETTE["primary"])
        self.conf_price = make_label("", 16, False, PALETTE["text_sec"])
        self.conf_desc  = QLabel()
        self.conf_desc.setWordWrap(True)
        self.conf_desc.setStyleSheet(
            f"color:{PALETTE['text_sec']};font-size:14px;background:transparent;"
        )
        dl.addWidget(self.conf_name)
        dl.addWidget(self.conf_price)
        dl.addWidget(self.conf_desc)
        lay.addWidget(details)

        lay.addWidget(hline())

        # ── Action buttons ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        edit_back_btn = make_btn(t("edit_btn"), primary=False, size=16)
        edit_back_btn.setFixedHeight(65)
        edit_back_btn.clicked.connect(lambda: self._jump_to_step(1))
        btn_row.addWidget(edit_back_btn)

        confirm_btn = make_btn(t("confirm_save"), primary=True, size=18)
        confirm_btn.setFixedHeight(70)
        confirm_btn.clicked.connect(self._finish_add)
        btn_row.addWidget(confirm_btn)

        lay.addLayout(btn_row)
        return w

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def on_enter(self):
        self._step         = 0
        self._product_name = ""
        self._product_desc = ""
        self._price        = 100.0
        self._photo_paths  = [None, None, None, None]
        self._active_slot  = 0
        self._stop_camera()
        self._reset_step0_ui()
        self._show_step()

    def on_leave(self):
        self._stop_camera()

    # ── Step logic ──────────────────────────────────────────────────────────
    def _show_step(self):
        self.stack.setCurrentIndex(self._step)
        self.progress.setValue(self._step + 1)
        header, voice_key = self._STEP_META[self._step]
        self.header_lbl.setText(header)
        self._speak(voice_key)
        if self._step == self.STEPS - 1:
            self.next_btn.setVisible(False)
        else:
            self.next_btn.setVisible(True)
            self.next_btn.setText("▶  Next")
        self.back_btn.setText(t("back"))
        self.back_btn.setEnabled(True)
        if self._step == 1:
            self._enter_step1()
        elif self._step == 2:
            self._enter_step2()
        elif self._step == 3:
            self._enter_step3()

    def _go_next(self):
        if self._step == 0:
            captured = [p for p in self._photo_paths if p and p != "placeholder"]
            if not captured:
                self.photo_status.setText("⚠️  Please capture at least 1 photo!")
                self.photo_status.setStyleSheet(
                    f"color:{PALETTE['error']};background:transparent;"
                )
                return
            self._stop_camera()
            self._step = 1
            self._show_step()
        elif self._step == 1:
            name = self.name_input.text().strip()
            desc = self.desc_input.toPlainText().strip()
            if not name:
                self.detect_status.setText("⚠️  Please enter a product name!")
                self.detect_status.setStyleSheet(
                    f"color:{PALETTE['error']};background:transparent;"
                )
                return
            self._product_name = name
            self._product_desc = desc
            self._step = 2
            self._show_step()
        elif self._step == 2:
            self._price = float(self.price_slider.value())
            self._step  = 3
            self._show_step()
        elif self._step == 3:
            self._finish_add()

    def _go_back(self):
        if self._step > 0:
            self._step -= 1
            self._show_step()
        else:
            self._stop_camera()
            self.navigate.emit("dashboard")

    def _jump_to_step(self, step: int):
        self._step = step
        self._show_step()

    # ── Step 0 actions ──────────────────────────────────────────────────────
    def _reset_step0_ui(self):
        self.camera_label.setPixmap(QPixmap())
        self.camera_label.setText("📷")
        self.camera_label.setFont(QFont("Arial", 56))
        self.capture_btn.setEnabled(False)
        self.retake_btn.setEnabled(False)
        self.cam_start_btn.setEnabled(True)
        for i, lbl in enumerate(self._slot_labels):
            lbl.setPixmap(QPixmap())
            lbl.setText("📷\n" + str(i + 1))
            lbl.setFont(QFont("Arial", 11))
            lbl.setStyleSheet(
                f"background:{PALETTE['bg2']};border-radius:8px;"
                f"border:2px solid {PALETTE['border']};font-size:22px;"
            )
        self._active_slot = 0
        self._update_slot_highlight()
        self._update_status_text()

    def _select_slot(self, idx: int):
        """User tapped a slot thumbnail — make it the active capture target."""
        self._active_slot = idx
        self._update_slot_highlight()
        self._update_status_text()
        self.retake_btn.setEnabled(
            bool(self._photo_paths[idx] and self._photo_paths[idx] != "placeholder")
        )

    def _update_slot_highlight(self):
        """Green border on active slot, grey on others."""
        for i, lbl in enumerate(self._slot_labels):
            if i == self._active_slot:
                lbl.setStyleSheet(
                    f"background:{PALETTE['bg2']};border-radius:8px;"
                    f"border:3px solid {PALETTE['primary']};font-size:22px;"
                )
            else:
                lbl.setStyleSheet(
                    f"background:{PALETTE['bg2']};border-radius:8px;"
                    f"border:2px solid {PALETTE['border']};font-size:22px;"
                )

    def _update_status_text(self):
        captured = sum(1 for p in self._photo_paths if p)
        slot = self._active_slot + 1
        if captured == 0:
            msg = "📷  Tap Start Camera, then Capture to take Photo 1"
        elif captured == 4:
            msg = "✅  All 4 photos captured! Press Next to continue."
        else:
            msg = f"✅  {captured}/4 captured  ·  Now capturing Photo {slot} — tap a slot to change"
        self.photo_status.setText(msg)
        self.photo_status.setStyleSheet(
            f"color:{'#27AE60' if captured > 0 else PALETTE['text_sec']};"
            f"background:transparent;"
        )

    def _start_camera(self):
        """
        Open camera using CameraService (tries picamera2 → GStreamer → V4L2).
        Falls back to placeholder mode if nothing works.
        """
        if self._cam and self._cam.is_open():
            return   # already running

        if _CAMERA_SERVICE_AVAILABLE:
            self._cam = CameraService()
            backend = self._cam.start()
        else:
            backend = "placeholder"

        if backend == "placeholder" or not _CAMERA_SERVICE_AVAILABLE:
            self.photo_status.setText(
                "❌  Camera not available — enter details manually"
            )
            self.photo_status.setStyleSheet(
                f"color:{PALETTE['error']};background:transparent;"
            )
            self._photo_paths = ["placeholder"] * 4
            for i, lbl in enumerate(self._slot_labels):
                lbl.setText("🖼️\n" + str(i + 1))
            self.retake_btn.setEnabled(True)
            return

        # Start frame-grab timer  (80 ms ≈ 12 fps — lightweight on Pi)
        self._cam_timer = QTimer(self)
        self._cam_timer.timeout.connect(self._update_frame)
        self._cam_timer.start(80)

        self.cam_start_btn.setEnabled(False)
        self.capture_btn.setEnabled(True)
        self.photo_status.setText(
            f"🎥  Camera live [{backend}] — Capture Photo {self._active_slot + 1}"
        )
        self.photo_status.setStyleSheet(
            f"color:{PALETTE['success']};background:transparent;"
        )

    def _update_frame(self):
        """Called by QTimer every 80 ms to refresh the camera preview."""
        import cv2
        if not self._cam or not self._cam.is_open():
            return
        frame_rgb = self._cam.read_frame()   # already RGB from camera_service
        if frame_rgb is None:
            return
        # No conversion needed — picamera2 returns RGB888 directly
        h, w, ch = frame_rgb.shape
        qt_img   = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.camera_label.setPixmap(
            QPixmap.fromImage(qt_img).scaled(
                self.camera_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def _capture_photo(self):
        """
        Capture current frame to disk via CameraService and
        update the slot thumbnail and main preview.
        """
        import cv2
        from datetime import datetime

        app_dir   = os.path.dirname(os.path.abspath(__file__))
        photo_dir = os.path.join(app_dir, "artbridge_photos")
        os.makedirs(photo_dir, exist_ok=True)

        slot     = self._active_slot
        filename = datetime.now().strftime("photo_%Y%m%d_%H%M%S_s") + str(slot + 1) + ".jpg"
        path     = os.path.join(photo_dir, filename)

        ok = self._cam.capture_to_file(path) if self._cam else False

        if ok:
            self._photo_paths[slot] = path
            # Load saved file into Qt pixmap
            pix = QPixmap(path)
            if not pix.isNull():
                slot_lbl = self._slot_labels[slot]
                slot_lbl.setPixmap(
                    pix.scaled(slot_lbl.size(), Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
                )
                slot_lbl.setText("")
                slot_lbl.setStyleSheet(
                    f"background:{PALETTE['bg2']};border-radius:10px;"
                    f"border:3px solid {PALETTE['success']};font-size:26px;"
                )
                self.camera_label.setPixmap(
                    pix.scaled(self.camera_label.size(), Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
                )
        else:
            self._photo_paths[slot] = "placeholder"
            self._slot_labels[slot].setText("🖼️\n" + str(slot + 1))

        self.retake_btn.setEnabled(True)

        # Auto-advance to next empty slot
        for i in range(4):
            if not self._photo_paths[i]:
                self._active_slot = i
                self._update_slot_highlight()
                break

        self._update_status_text()

        # If all 4 slots filled, stop camera feed
        if all(self._photo_paths):
            self._stop_camera()
            self.cam_start_btn.setEnabled(True)
            self.capture_btn.setEnabled(False)

    def _retake_photo(self):
        """
        Clear the current active slot and immediately restart the camera
        so the user can capture a new photo for that slot without extra taps.
        """
        slot = self._active_slot

        self._photo_paths[slot] = None
        lbl = self._slot_labels[slot]
        lbl.setPixmap(QPixmap())
        lbl.setText("📷\n" + str(slot + 1))
        lbl.setFont(QFont("Arial", 14))
        self._update_slot_highlight()
        self._update_status_text()

        self.camera_label.setPixmap(QPixmap())
        self.camera_label.setText("📷")
        self.camera_label.setFont(QFont("Arial", 60))

        self.retake_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.cam_start_btn.setEnabled(False)

        self._stop_camera()    # uses CameraService.stop()
        self._start_camera()   # uses CameraService.start()

    def _stop_camera(self):
        if self._cam_timer:
            self._cam_timer.stop()
            self._cam_timer = None
        if self._cam:
            self._cam.stop()
            self._cam = None
        # Legacy cleanup
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    # ── Step 1 actions ──────────────────────────────────────────────────────
    def _enter_step1(self):
        self.detect_widget.setVisible(True)
        self.edit_widget.setVisible(False)
        self.next_btn.setEnabled(False)
        self.detect_status.setText(t("detecting"))
        self.detect_status.setStyleSheet(
            f"color:{PALETTE['text_sec']};background:transparent;"
        )
        for bar in self._bars:
            bar.setValue(0)
        self._bar_targets = [88, 94, 82, 97]
        self._bar_tick    = [0]
        self._animate_bars()
        threading.Thread(
            target=self._ml_worker, args=(self._photo_path,), daemon=True
        ).start()

    def _animate_bars(self):
        tick = self._bar_tick
        targets = self._bar_targets
        def _step():
            if tick[0] >= 25:
                return
            for bar, tgt in zip(self._bars, targets):
                bar.setValue(min(bar.value() + tgt // 25 + 1, int(tgt * 0.85)))
            tick[0] += 1
            QTimer.singleShot(90, _step)
        QTimer.singleShot(100, _step)

    def _ml_worker(self, image_path: str):
        name, desc = detect_product(image_path)
        QMetaObject.invokeMethod(
            self, "_on_ml_done", Qt.QueuedConnection,
            Q_ARG(str, name), Q_ARG(str, desc),
        )

    @pyqtSlot(str, str)
    def _on_ml_done(self, name: str, desc: str):
        for bar, tgt in zip(self._bars, self._bar_targets):
            bar.setValue(tgt)

        # Detect "not recognised" — ml_service returns "Artisan Product" as sentinel
        _NOT_RECOGNISED = "Artisan Product"
        is_recognised = (name != _NOT_RECOGNISED)

        self._product_name = name if is_recognised else ""
        self._product_desc = desc if is_recognised else ""

        if is_recognised:
            # ML gave a real result — fill fields, hide warning
            self.name_input.setText(name)
            self.desc_input.setPlainText(desc)
            self.not_recognised_banner.setVisible(False)
        else:
            # ML could not identify the product — show warning, leave fields empty
            self.name_input.clear()
            self.name_input.setPlaceholderText(
                "Product not recognised — please type the name here"
            )
            self.desc_input.clear()
            self.desc_input.setPlaceholderText(
                "Describe your product (e.g. material, use, style)…"
            )
            self.not_recognised_banner.setVisible(True)

        self.detect_widget.setVisible(False)
        self.edit_widget.setVisible(True)
        self.next_btn.setEnabled(True)

        self.detect_status.setText(
            "✅  Detected! Edit below." if is_recognised
            else "⚠️  Not recognised — please fill in the details below."
        )
        self.detect_status.setStyleSheet(
            f"color:{PALETTE['success'] if is_recognised else PALETTE['error']};"
            f"background:transparent;"
        )

    # ── Step 2 actions ──────────────────────────────────────────────────────
    def _enter_step2(self):
        self.price_slider.setValue(int(self._price))
        self.price_display.setText(f"₹{int(self._price):,}")

    # ── Step 3 actions ──────────────────────────────────────────────────────
    def _conf_navigate(self, delta: int):
        photos = self._conf_photo_list
        if not photos:
            return
        self._conf_photo_idx[0] = (self._conf_photo_idx[0] + delta) % len(photos)
        self._conf_show_photo()

    def _conf_show_photo(self):
        photos = self._conf_photo_list
        if not photos:
            self._conf_img_lbl.setText("🖼️")
            self._conf_dot_lbl.setText("")
            self._conf_left_btn.setVisible(False)
            self._conf_right_btn.setVisible(False)
            return
        idx = self._conf_photo_idx[0]
        path = photos[idx]
        pix = QPixmap(path)
        if not pix.isNull():
            self._conf_img_lbl.setPixmap(
                pix.scaled(
                    self._conf_img_lbl.width() or 600, 190,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
            )
            self._conf_img_lbl.setText("")
        else:
            self._conf_img_lbl.setPixmap(QPixmap())
            self._conf_img_lbl.setText("🖼️")
            self._conf_img_lbl.setFont(QFont("Arial", 40))
        count = len(photos)
        self._conf_dot_lbl.setText(str(idx + 1) + " / " + str(count))
        self._conf_left_btn.setVisible(count > 1)
        self._conf_right_btn.setVisible(count > 1)

    def _enter_step3(self):
        self.conf_name.setText("📦  " + self._product_name)
        self.conf_price.setText("💰  ₹" + f"{self._price:,.0f}")
        desc = self._product_desc or "No description provided."
        self.conf_desc.setText(desc[:160] + ("…" if len(desc) > 160 else ""))
        self._conf_photo_list = [
            p for p in self._photo_paths
            if p and p != "placeholder"
        ]
        self._conf_photo_idx[0] = 0
        self._conf_show_photo()

    def _finish_add(self):
        name  = self._product_name or "My Product"
        desc  = self._product_desc
        price = self._price
        
        pid = -1
        if AppState.db:
            pid = AppState.db.add_product(
                name, desc, price,
                photo_paths=self._photo_paths,
            )
        
        self._speak("product_added")

        # ── Start Background Cloud Sync ──────────────────────────────────────
        if pid != -1 and _CLOUD_SYNC_AVAILABLE:
            # Take a snapshot copy NOW — before the UI resets self._photo_paths
            photo_paths_snapshot = list(self._photo_paths or [])
            threading.Thread(
                target=self._bg_cloud_sync,
                args=(pid, name, photo_paths_snapshot),
                daemon=True
            ).start()

        QTimer.singleShot(800, lambda: self.navigate.emit("my_products"))

    def _bg_cloud_sync(self, pid, name, photo_paths):
        """Upload images to S3 and sync details to DynamoDB in background."""
        try:
            print(f"[Sync] ☁️  Starting cloud sync for '{name}' (ID: {pid})...")
            
            # 1. Get Artisan ID (from current user)
            artisan_id = "0"
            if AppState.current_user:
                artisan_id = str(AppState.current_user[0])
            
            # 2. Upload images to S3 using the snapshot copy
            print(f"[Sync]  -> Uploading {len(photo_paths)} photos to S3...")
            urls = upload_product_images(photo_paths, artisan_id, pid)
            print(f"[Sync]  -> S3 URLs: {urls}")
            
            # 3. Save S3 URLs to local DB
            if any(urls):
                AppState.db.update_product_image_urls(pid, urls)
                print(f"[Sync]  -> S3 URLs saved to local DB.")
            else:
                print(f"[Sync]  -> ⚠️ No URLs returned from S3 upload. Check AWS credentials/bucket.")
            
            # 4. Push to DynamoDB
            print(f"[Sync]  -> Pushing to DynamoDB...")
            sync_products_to_dynamo()
            
            print(f"[Sync] ✅ Cloud sync complete for '{name}'.")
        except Exception as e:
            print(f"[Sync] ❌ Cloud sync failed: {e}")


# ──────────────────────────────────────────────────────────────────────────────
#  6. MY PRODUCTS  —  2-column image-card grid  (only screen changed from original)
# ──────────────────────────────────────────────────────────────────────────────
class MyProductsScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        lay.addWidget(self._header("my_products"))

        # Scrollable 2-column grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet(f"background:{PALETTE['bg']};")
        self.grid_lay = QGridLayout(self.grid_container)
        self.grid_lay.setContentsMargins(4, 4, 4, 4)
        self.grid_lay.setSpacing(14)
        self.grid_lay.setColumnStretch(0, 1)
        self.grid_lay.setColumnStretch(1, 1)

        scroll.setWidget(self.grid_container)
        lay.addWidget(scroll, 1)

        add_btn = make_btn("➕  " + t("add_product"), primary=True, size=18)
        add_btn.setFixedHeight(70)
        add_btn.clicked.connect(lambda: self.navigate.emit("add_product"))
        lay.addWidget(add_btn)

        back_btn = make_btn(t("back"), primary=False, size=16)
        back_btn.setFixedHeight(60)
        back_btn.clicked.connect(lambda: self.navigate.emit("dashboard"))
        lay.addWidget(back_btn)

    def on_enter(self):
        self._speak("my_products")
        self._refresh()

    def _refresh(self):
        # Clear all grid items
        while self.grid_lay.count():
            item = self.grid_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        products = AppState.db.get_products() if AppState.db else []

        if not products:
            empty_lbl = make_label(
                "No products yet.\nAdd your first product! 📦",
                16, False, PALETTE["text_sec"], Qt.AlignCenter,
            )
            empty_lbl.setWordWrap(True)
            self.grid_lay.addWidget(empty_lbl, 0, 0, 1, 2)
            return

        for idx, (pid, name, price, cat, synced, created) in enumerate(products):
            card = self._product_card(pid, name, price, cat, synced)
            self.grid_lay.addWidget(card, idx // 2, idx % 2)

    def _product_card(self, pid, name, price, cat, synced) -> QWidget:
        """
        Amazon-style card with multi-photo strip:
          ┌──────────────────────────────────────┐
          │  [Photo1] [Photo2] [Photo3] [Photo4] │  ← horizontal strip
          ├──────────────────────────────────────┤
          │  Product Name  (bold)                │
          │  Price                               │
          │  Description…                        │
          │  Status badge                        │
          └──────────────────────────────────────┘
        """
        card = QWidget()
        card.setStyleSheet(
            "QWidget{background:" + PALETTE["card"] + ";border-radius:14px;"
            "border:1px solid " + PALETTE["border"] + ";}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 10)
        cl.setSpacing(0)

        # ── Swipeable photo viewer — one photo at a time, ◀ ▶ to navigate ──
        photos = AppState.db.get_product_photos(pid) if AppState.db else []
        # Filter out nulls
        photos = [p for p in photos if p]

        viewer_h = 190
        viewer_w = QWidget()
        viewer_w.setFixedHeight(viewer_h)
        viewer_w.setStyleSheet(
            "background:" + PALETTE["bg2"] + ";"
            "border-radius:14px 14px 0 0;"
        )
        vl = QHBoxLayout(viewer_w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)

        if photos:
            # State: current photo index (stored on the label via a list cell)
            photo_idx = [0]

            # ◀ left arrow button
            left_btn = QPushButton("◀")
            left_btn.setFixedSize(32, viewer_h)
            left_btn.setStyleSheet(
                "QPushButton{background:rgba(0,0,0,0.18);color:white;"
                "border:none;border-radius:14px 0 0 0;font-size:16px;font-weight:bold;}"
                "QPushButton:pressed{background:rgba(0,0,0,0.38);}"
            )
            left_btn.setCursor(Qt.PointingHandCursor)

            # Main image display
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignCenter)
            img_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            img_lbl.setStyleSheet("background:transparent;")

            # Dot indicator (e.g. "2 / 4")
            dot_lbl = QLabel()
            dot_lbl.setAlignment(Qt.AlignCenter)
            dot_lbl.setStyleSheet(
                "background:rgba(0,0,0,0.45);color:white;"
                "font-size:11px;border-radius:8px;padding:2px 8px;"
            )

            # ▶ right arrow button
            right_btn = QPushButton("▶")
            right_btn.setFixedSize(32, viewer_h)
            right_btn.setStyleSheet(
                "QPushButton{background:rgba(0,0,0,0.18);color:white;"
                "border:none;border-radius:0 14px 0 0;font-size:16px;font-weight:bold;}"
                "QPushButton:pressed{background:rgba(0,0,0,0.38);}"
            )
            right_btn.setCursor(Qt.PointingHandCursor)

            def _show_photo(n):
                idx = n % len(photos)
                photo_idx[0] = idx
                pix = QPixmap(photos[idx])
                if not pix.isNull():
                    img_lbl.setPixmap(
                        pix.scaled(img_lbl.width() or 250, viewer_h - 4,
                                   Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
                else:
                    img_lbl.setText("🖼️")
                    img_lbl.setFont(QFont("Arial", 36))
                dot_lbl.setText(str(idx + 1) + " / " + str(len(photos)))
                left_btn.setVisible(len(photos) > 1)
                right_btn.setVisible(len(photos) > 1)

            left_btn.clicked.connect(lambda: _show_photo(photo_idx[0] - 1))
            right_btn.clicked.connect(lambda: _show_photo(photo_idx[0] + 1))

            # Stack: arrows overlay the image
            stack_w = QWidget()
            stack_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            stack_lay = QVBoxLayout(stack_w)
            stack_lay.setContentsMargins(0, 0, 0, 0)
            stack_lay.setSpacing(0)
            stack_lay.addWidget(img_lbl, 1)
            dot_row = QHBoxLayout()
            dot_row.addStretch()
            dot_row.addWidget(dot_lbl)
            dot_row.addStretch()
            stack_lay.addLayout(dot_row)

            vl.addWidget(left_btn, 0, Qt.AlignVCenter)
            vl.addWidget(stack_w, 1)
            vl.addWidget(right_btn, 0, Qt.AlignVCenter)

            _show_photo(0)
        else:
            no_img = QLabel("🖼️")
            no_img.setFont(QFont("Arial", 48))
            no_img.setAlignment(Qt.AlignCenter)
            no_img.setStyleSheet("background:transparent;")
            vl.addWidget(no_img)

        cl.addWidget(viewer_w)

        # ── Thin separator ───────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:" + PALETTE["border"] + ";border:none;")
        cl.addWidget(sep)

        # ── Text block ───────────────────────────────────────────────────────
        text_w = QWidget()
        text_w.setStyleSheet("background:transparent;")
        tl = QVBoxLayout(text_w)
        tl.setContentsMargins(12, 8, 12, 4)
        tl.setSpacing(4)

        name_lbl = make_label(name[:32], 16, True, PALETTE["text"])
        name_lbl.setWordWrap(True)
        tl.addWidget(name_lbl)

        price_lbl = make_label("Rs." + str(int(price)), 15, True, PALETTE["primary"])
        tl.addWidget(price_lbl)

        desc_text = ""
        if AppState.db:
            try:
                desc_text = AppState.db.get_product_description(pid) or ""
            except Exception:
                desc_text = ""
        if desc_text:
            desc_lbl = make_label(
                desc_text[:65] + ("..." if len(desc_text) > 65 else ""),
                12, False, PALETTE["text_sec"],
            )
            desc_lbl.setWordWrap(True)
            tl.addWidget(desc_lbl)

        badge_text  = "Synced" if synced else "Pending"
        badge_color = PALETTE["success"] if synced else PALETTE["accent2"]
        badge = QLabel(("Checked " if synced else "Clock ") + badge_text)
        badge.setStyleSheet(
            "color:" + badge_color + ";font-size:11px;font-weight:bold;"
            "background:transparent;"
        )
        tl.addWidget(badge)

        cl.addWidget(text_w)
        return card


# ──────────────────────────────────────────────────────────────────────────────
#  7. EARNINGS  (original)
# ──────────────────────────────────────────────────────────────────────────────
class EarningsScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 24)
        lay.setSpacing(16)
        lay.addWidget(self._header("earnings"))

        self.big_rev = make_label("₹0", 48, True, PALETTE["primary"], Qt.AlignCenter)
        lay.addWidget(self.big_rev)
        lay.addWidget(make_label("Total Revenue", 16, False,
                                 PALETTE["text_sec"], Qt.AlignCenter))
        lay.addWidget(hline())

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)
        self.mini_total   = self._mini_card("📋", "0", "Total Orders")
        self.mini_pending = self._mini_card("⏳", "0", "Pending")
        self.mini_synced  = self._mini_card("🔄", "0", "Synced")
        for c in (self.mini_total, self.mini_pending, self.mini_synced):
            cards_row.addWidget(c)
        lay.addLayout(cards_row)
        lay.addStretch()

        back_btn = make_btn(t("back"), primary=False, size=16)
        back_btn.setFixedHeight(60)
        back_btn.clicked.connect(lambda: self.navigate.emit("dashboard"))
        lay.addWidget(back_btn)

    def _mini_card(self, icon, val, sub) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            f"background:{PALETTE['card']};border-radius:14px;"
            f"border:1px solid {PALETTE['border']};"
        )
        cl = QVBoxLayout(w)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(4)
        ico = QLabel(icon)
        ico.setFont(QFont("Arial", 24))
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet("background:transparent;")
        cl.addWidget(ico)
        v = make_label(val, 18, True, PALETTE["primary"], Qt.AlignCenter)
        v.setObjectName("val")
        cl.addWidget(v)
        cl.addWidget(make_label(sub, 12, False, PALETTE["text_sec"], Qt.AlignCenter))
        return w

    def on_enter(self):
        self._speak("earnings")
        if not AppState.db:
            return
        rev, total, pending, synced = AppState.db.get_earnings()
        self.big_rev.setText(f"₹{rev:,.0f}")
        for card, text in zip(
            (self.mini_total, self.mini_pending, self.mini_synced),
            (str(total), str(pending), str(synced)),
        ):
            card.findChild(QLabel, "val").setText(text)


# ──────────────────────────────────────────────────────────────────────────────
#  8. ORDERS  (original)
# ──────────────────────────────────────────────────────────────────────────────
class OrdersScreen(BaseScreen):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)
        lay.addWidget(self._header("orders"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.list_w = QWidget()
        self.list_w.setStyleSheet(f"background:{PALETTE['bg']};")
        self.list_lay = QVBoxLayout(self.list_w)
        self.list_lay.setSpacing(10)
        self.list_lay.addStretch()

        scroll.setWidget(self.list_w)
        lay.addWidget(scroll)

        back_btn = make_btn(t("back"), primary=False, size=16)
        back_btn.setFixedHeight(60)
        back_btn.clicked.connect(lambda: self.navigate.emit("dashboard"))
        lay.addWidget(back_btn)

    def on_enter(self):
        self._speak("orders")
        self._refresh()

        # Pull latest orders from DynamoDB in background, then refresh UI
        def _bg_sync():
            try:
                from sync import sync_orders_from_dynamo
                from PyQt5.QtCore import QMetaObject, Qt
                print("[Orders] Syncing from DynamoDB...")
                sync_orders_from_dynamo()
                QMetaObject.invokeMethod(self, "_refresh", Qt.QueuedConnection)
                print("[Orders] Sync done — UI refreshed.")
            except Exception as e:
                print(f"[Orders] Sync failed: {e}")

        import threading
        threading.Thread(target=_bg_sync, daemon=True).start()

    def _refresh(self):
        while self.list_lay.count() > 1:
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        orders = AppState.db.get_orders() if AppState.db else []
        if not orders:
            empty = make_label(
                "📋  No orders yet.", 16, False, PALETTE["text_sec"], Qt.AlignCenter
            )
            self.list_lay.insertWidget(0, empty)
            return
        # get_orders returns 8 columns:
        # id, product_name, customer, amount, status, created_at,
        # customer_name (from shipping), customer_address (from shipping)
        for row in orders:
            oid, prod, cust, amt, status, created = row[0], row[1], row[2], row[3], row[4], row[5]
            ship_name    = row[6] or cust          # fall back to orders.customer
            ship_address = row[7] or "Address not available"
            self.list_lay.insertWidget(
                self.list_lay.count() - 1,
                self._order_card(oid, prod, amt, status, ship_name, ship_address),
            )

    def _order_card(self, oid, prod, amt, status,
                        ship_name, ship_address) -> QWidget:
        """
        Expanded order card layout:
          ┌──────────────────────────────────────────────────┐
          │  #3  Bamboo Basket                    SHIPPED    │
          │  👤  Suresh Babu          ₹180                   │
          │  📍  78, Anna Salai, Chennai - 600002            │
          └──────────────────────────────────────────────────┘
        """
        STATUS_COLORS = {
            "Delivered": PALETTE["success"],
            "Pending":   PALETTE["accent2"],
            "Shipped":   PALETTE["primary"],
        }
        status_color = STATUS_COLORS.get(status, PALETTE["text_sec"])

        card = QWidget()
        card.setStyleSheet(
            f"QWidget{{background:{PALETTE['card']};border-radius:14px;"
            f"border:1px solid {PALETTE['border']};}}"
        )
        root = QVBoxLayout(card)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        # ── Row 1: order id + product name | status badge ─────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        order_lbl = make_label(f"#{oid}  {prod}", 16, True, PALETTE["text"])
        top_row.addWidget(order_lbl, 1)

        badge = QLabel("  " + status + "  ")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{status_color};color:white;border-radius:8px;"
            f"font-size:13px;font-weight:bold;padding:3px 8px;"
        )
        top_row.addWidget(badge, 0, Qt.AlignVCenter)
        root.addLayout(top_row)

        # ── Row 2: customer name + amount ─────────────────────────────────
        cust_row = QHBoxLayout()
        cust_row.setSpacing(8)
        cust_row.addWidget(
            make_label("👤  " + ship_name, 14, False, PALETTE["text_sec"]), 1
        )
        cust_row.addWidget(
            make_label("₹" + str(int(amt)), 15, True, PALETTE["primary"],
                       Qt.AlignRight)
        )
        root.addLayout(cust_row)

        # ── Row 3: shipping address ────────────────────────────────────────
        addr_lbl = make_label(
            "📍  " + ship_address, 13, False, PALETTE["text_sec"]
        )
        addr_lbl.setWordWrap(True)
        root.addWidget(addr_lbl)

        return card
