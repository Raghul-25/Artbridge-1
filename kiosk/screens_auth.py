#!/usr/bin/env python3
"""
ui/screens_auth.py — Login (fingerprint authenticate) and Register screens.

Both screens are non-blocking:
  - Hardware I/O runs in daemon threads
  - UI updates are dispatched via QMetaObject.invokeMethod (thread-safe)
  - Voice guidance fires for every step automatically
"""

import threading

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, QMetaObject, Q_ARG, pyqtSlot

from config import PALETTE, AppState, t
from widgets import (
    BaseScreen, FingerprintWidget, make_label, make_btn, hline,
)


# ──────────────────────────────────────────────────────────────────────────────
#  3. LOGIN SCREEN  (Fingerprint authentication)
# ──────────────────────────────────────────────────────────────────────────────
class LoginScreen(BaseScreen):
    """
    Touchscreen fingerprint login.

    Flow:
      1. User taps "Scan Fingerprint"
      2. Voice says "Place your finger"
      3. Sensor thread runs; UI animates
      4. On success → voice says "Authentication successful" → dashboard
      5. On failure → voice says "Try again" → reset for retry
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scanning = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(20)
        lay.setAlignment(Qt.AlignCenter)

        lay.addWidget(self._header("fingerprint_title", "fingerprint_hint"))

        # Fingerprint animation widget
        fp_row = QHBoxLayout()
        fp_row.setAlignment(Qt.AlignCenter)
        self.fp_widget = FingerprintWidget()
        fp_row.addWidget(self.fp_widget)
        lay.addLayout(fp_row)

        self.status_lbl = make_label("", 16, False, PALETTE["text_sec"], Qt.AlignCenter)
        lay.addWidget(self.status_lbl)

        self.scan_btn = make_btn("", primary=True, size=20)
        self.scan_btn.setFixedHeight(80)
        self.scan_btn.clicked.connect(self._start_scan)
        lay.addWidget(self.scan_btn)

        self.register_btn = make_btn("➕  Register New User", primary=False, size=16)
        self.register_btn.setFixedHeight(60)
        self.register_btn.clicked.connect(lambda: self.navigate.emit("register"))
        lay.addWidget(self.register_btn)

        # ── Demo bypass (no fingerprint sensor) ───────────────────────────────
        demo_btn = make_btn("🚧  Skip Login (Demo Mode)", primary=False, size=15)
        demo_btn.setFixedHeight(55)
        demo_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FFF8E7; color: #8B6914;"
            "  border: 2px dashed #DAA520; border-radius: 12px;"
            "  font-size: 15px; font-weight: bold; min-height: 55px;"
            "}"
            "QPushButton:pressed { background: #F5E6C0; }"
        )
        demo_btn.clicked.connect(self._demo_login)
        lay.addWidget(demo_btn)

        self.back_btn = make_btn("", primary=False, size=16)
        self.back_btn.setFixedHeight(60)
        self.back_btn.clicked.connect(lambda: self.navigate.emit("welcome"))
        lay.addWidget(self.back_btn)

    def on_enter(self):
        self.status_lbl.setText(t("fingerprint_hint"))
        self.status_lbl.setStyleSheet(
            f"color:{PALETTE['text_sec']};background:transparent;"
        )
        self.scan_btn.setText(t("scan_finger"))
        self.back_btn.setText(t("back"))
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self.fp_widget.reset()
        self._speak("fingerprint_hint")

    # ── Scan trigger ──────────────────────────────────────────────────────────
    def _start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self.scan_btn.setEnabled(False)
        self.status_lbl.setText(t("scanning"))
        self.status_lbl.setStyleSheet(
            f"color:{PALETTE['accent2']};background:transparent;"
        )
        self.fp_widget.start_scan()
        self._speak("scanning")
        threading.Thread(target=self._auth_worker, daemon=True).start()

    def _auth_worker(self):
        sensor = AppState.sensor
        success, position = sensor.authenticate()

        if success:
            user = AppState.db.get_user_by_fingerprint(position)
            if user:
                AppState.current_user = user
                QMetaObject.invokeMethod(self, "_on_success", Qt.QueuedConnection)
            else:
                # Fingerprint on sensor but not in DB — treat as unknown
                QMetaObject.invokeMethod(self, "_on_failure", Qt.QueuedConnection)
        else:
            QMetaObject.invokeMethod(self, "_on_failure", Qt.QueuedConnection)

    @pyqtSlot()
    def _on_success(self):
        self.fp_widget.stop_scan()
        self.status_lbl.setText(t("login_success"))
        self.status_lbl.setStyleSheet(
            f"color:{PALETTE['success']};background:transparent;"
            f"font-size:20px;font-weight:bold;"
        )
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self._speak("login_success")
        QTimer.singleShot(1200, lambda: self.navigate.emit("dashboard"))

    @pyqtSlot()
    def _on_failure(self):
        self.fp_widget.stop_scan()
        self.fp_widget.reset()
        self.status_lbl.setText(t("login_failed") + "  —  " + t("try_again"))
        self.status_lbl.setStyleSheet(
            f"color:{PALETTE['error']};background:transparent;"
            f"font-size:16px;font-weight:bold;"
        )
        self._scanning = False
        self.scan_btn.setEnabled(True)
        self._speak("login_failed")
        QTimer.singleShot(1500, lambda: self._speak("try_again"))

    def _demo_login(self):
        """Bypass fingerprint — go straight to dashboard."""
        AppState.current_user = (0, "Demo Artisan")
        self.navigate.emit("dashboard")


# ──────────────────────────────────────────────────────────────────────────────
#  REGISTER SCREEN  (Fingerprint registration)
# ──────────────────────────────────────────────────────────────────────────────
class RegisterScreen(BaseScreen):
    """
    Two-scan fingerprint registration with voice guidance at each step.

    Steps:
      1. Enter name
      2. Tap Register → voice: "Place your finger"
      3. Scan 1 done → voice: "Remove your finger"
      4. Scan 2 done → voice: "Place same finger again"
      5. Success     → voice: "Fingerprint registered"  → navigate to login
    """

    # Maps progress-cb strings → translation keys and voice lines
    _STEP_MAP = {
        "step1":    ("register_step1", "register_step1"),
        "step2":    ("register_step2", "register_step2"),
        "step3":    ("register_step3", "register_step3"),
        "success":  ("register_success", "register_success"),
        "mismatch": ("register_failed",  "register_failed"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registering = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(20)
        lay.setAlignment(Qt.AlignCenter)

        lay.addWidget(self._header("register_title"))

        # Fingerprint animation
        fp_row = QHBoxLayout()
        fp_row.setAlignment(Qt.AlignCenter)
        self.fp_widget = FingerprintWidget()
        fp_row.addWidget(self.fp_widget)
        lay.addLayout(fp_row)

        # Name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(t("enter_name"))
        self.name_input.setFixedHeight(56)
        lay.addWidget(self.name_input)

        # Status label
        self.status_lbl = make_label("", 16, False, PALETTE["text_sec"], Qt.AlignCenter)
        lay.addWidget(self.status_lbl)

        # Register button
        self.reg_btn = make_btn("", primary=True, size=20)
        self.reg_btn.setFixedHeight(80)
        self.reg_btn.clicked.connect(self._start_register)
        lay.addWidget(self.reg_btn)

        # Back button
        self.back_btn = make_btn("", primary=False, size=16)
        self.back_btn.setFixedHeight(60)
        self.back_btn.clicked.connect(lambda: self.navigate.emit("login"))
        lay.addWidget(self.back_btn)

    def on_enter(self):
        self.name_input.setPlaceholderText(t("enter_name"))
        self.reg_btn.setText(t("register_btn"))
        self.back_btn.setText(t("back"))
        self.status_lbl.setText("")
        self._registering = False
        self.reg_btn.setEnabled(True)
        self.fp_widget.reset()
        self._speak("register_title")

    # ── Register trigger ──────────────────────────────────────────────────────
    def _start_register(self):
        name = self.name_input.text().strip()
        if not name:
            self.status_lbl.setText("⚠️  " + t("enter_name"))
            self.status_lbl.setStyleSheet(
                f"color:{PALETTE['error']};background:transparent;"
            )
            self._speak("enter_name")
            return
        if self._registering:
            return
        self._registering = True
        self.reg_btn.setEnabled(False)
        self.fp_widget.start_scan()
        threading.Thread(
            target=self._register_worker, args=(name,), daemon=True
        ).start()

    def _register_worker(self, name: str):
        sensor = AppState.sensor
        success, position = sensor.register(progress_cb=self._progress_cb)
        if success:
            try:
                AppState.db.add_user(name, position)
            except Exception as e:
                print(f"[Register] DB error: {e}")
            QMetaObject.invokeMethod(
                self, "_on_done",
                Qt.QueuedConnection,
                Q_ARG(bool, True),
                Q_ARG(str, name),
            )
        else:
            QMetaObject.invokeMethod(
                self, "_on_done",
                Qt.QueuedConnection,
                Q_ARG(bool, False),
                Q_ARG(str, ""),
            )

    def _progress_cb(self, msg: str):
        """Called from sensor worker thread — dispatch to UI thread."""
        QMetaObject.invokeMethod(
            self, "_update_status",
            Qt.QueuedConnection,
            Q_ARG(str, msg),
        )

    @pyqtSlot(str)
    def _update_status(self, msg: str):
        label_key, voice_key = self._STEP_MAP.get(msg, (msg, msg))
        text = t(label_key) if label_key in (
            "register_step1","register_step2","register_step3",
            "register_success","register_failed",
        ) else msg
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            f"color:{PALETTE['text_sec']};background:transparent;"
        )
        self._speak(voice_key)

    @pyqtSlot(bool, str)
    def _on_done(self, success: bool, name: str):
        self.fp_widget.stop_scan()
        self._registering = False
        self.reg_btn.setEnabled(True)

        if success:
            self.status_lbl.setText(t("register_success"))
            self.status_lbl.setStyleSheet(
                f"color:{PALETTE['success']};background:transparent;"
                f"font-size:18px;font-weight:bold;"
            )
            self._speak("register_success")
            QTimer.singleShot(2000, lambda: self.navigate.emit("login"))
        else:
            self.fp_widget.reset()
            self.status_lbl.setText(t("register_failed"))
            self.status_lbl.setStyleSheet(
                f"color:{PALETTE['error']};background:transparent;"
                f"font-size:16px;font-weight:bold;"
            )
            self._speak("register_failed")
