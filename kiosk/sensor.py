#!/usr/bin/env python3
"""
fingerprint/sensor.py — Stable R307 fingerprint wrapper (NO auto-detection)
"""

import threading
import time

_sensor_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Safe connection (prevents hanging)
# ─────────────────────────────────────────────────────────────
def _connect_with_timeout(port, baud, timeout=2):
    from pyfingerprint.pyfingerprint import PyFingerprint
    import threading

    result = {"ok": False, "sensor": None}

    def target():
        try:
            f = PyFingerprint(port, baud)
            if f.verifyPassword():
                result["ok"] = True
                result["sensor"] = f
        except Exception:
            pass

    t = threading.Thread(target=target)
    t.daemon = True
    t.start()
    t.join(timeout)

    if not result["ok"]:
        raise RuntimeError(f"Connection failed @ {port} {baud}")

    return result["sensor"]


# ─────────────────────────────────────────────────────────────
# Real sensor (STRICT CONFIG)
# ─────────────────────────────────────────────────────────────
class FingerprintSensor:

    def __init__(self, port="/dev/ttyUSB0", baud=57600):
        self._port = port
        self._baud = baud

        print(f"[Fingerprint] Using port={self._port}, baud={self._baud}")

        # Connect safely (no hanging)
        self._f = _connect_with_timeout(self._port, self._baud, timeout=2)

        time.sleep(0.3)
        print("[Fingerprint] ✅ connected")


    # ─────────────────────────────────────────────────────────
    # Authentication
    # ─────────────────────────────────────────────────────────
    def authenticate(self, timeout=15):
        with _sensor_lock:
            try:
                f = self._f

                deadline = time.time() + timeout
                while not f.readImage():
                    if time.time() > deadline:
                        return False, -1
                    time.sleep(0.05)

                f.convertImage(0x01)
                pos, _ = f.searchTemplate()

                return (True, pos) if pos >= 0 else (False, -1)

            except Exception as e:
                print(f"[Fingerprint] auth error: {e}")
                return False, -1


    # ─────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────
    def register(self, progress_cb=None, timeout=30):

        def cb(msg):
            if progress_cb:
                progress_cb(msg)

        with _sensor_lock:
            try:
                f = self._f

                # Scan 1
                cb("step1")
                deadline = time.time() + timeout
                while not f.readImage():
                    if time.time() > deadline:
                        cb("timeout")
                        return False, -1
                    time.sleep(0.05)

                f.convertImage(0x01)

                # Wait for finger removal
                cb("step2")
                while f.readImage():
                    time.sleep(0.1)

                # Scan 2
                cb("step3")
                deadline = time.time() + timeout
                while not f.readImage():
                    if time.time() > deadline:
                        cb("timeout")
                        return False, -1
                    time.sleep(0.05)

                f.convertImage(0x02)

                # Store
                if f.createTemplate():
                    pos = f.storeTemplate()
                    cb("success")
                    return True, pos
                else:
                    cb("mismatch")
                    return False, -1

            except Exception as e:
                print(f"[Fingerprint] register error: {e}")
                cb("error")
                return False, -1


# ─────────────────────────────────────────────────────────────
# Mock sensor
# ─────────────────────────────────────────────────────────────
class MockFingerprintSensor:

    def __init__(self):
        print("[Fingerprint] ⚠️ MOCK MODE")

    def authenticate(self, timeout=15):
        time.sleep(2)
        return True, 1

    def register(self, progress_cb=None, timeout=30):
        def cb(msg):
            if progress_cb:
                progress_cb(msg)

        cb("step1"); time.sleep(1)
        cb("step2"); time.sleep(1)
        cb("step3"); time.sleep(1)
        cb("success")
        return True, 2


# ─────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────
def get_sensor(port="/dev/ttyUSB0", baud=57600, force_mock=False):

    if force_mock:
        return MockFingerprintSensor()

    try:
        return FingerprintSensor(port=port, baud=baud)

    except Exception as e:
        print(f"[Fingerprint] ❌ fallback to MOCK: {e}")
        return MockFingerprintSensor()
