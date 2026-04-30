#!/usr/bin/env python3
"""
fingerprint_debug.py — Complete diagnostic for R307 fingerprint sensor on Raspberry Pi.

Run this FIRST before starting the main app:
    python3 fingerprint_debug.py

It checks every possible failure point and tells you exactly what to fix.
"""

import os
import sys
import glob
import subprocess

print("\n" + "=" * 60)
print("  ArtBridge — Fingerprint Sensor Diagnostics")
print("=" * 60)

ALL_OK = True

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 1: USB device detected by OS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/7] Checking USB device detection ...")

usb_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")

if usb_ports:
    print(f"      ✅  Found serial ports: {usb_ports}")
else:
    print("      ❌  No /dev/ttyUSB* or /dev/ttyACM* found!")
    print()
    print("      CAUSES AND FIXES:")
    print("      a) TTL adapter not connected — check USB cable")
    print("      b) CP2102/CH340 driver not loaded:")
    print("           sudo apt install -y libftdi1 libusb-1.0-0")
    print("           lsusb   ← should show 'Silicon Labs CP2102' or 'CH340'")
    print("      c) Kernel module not loaded:")
    print("           sudo modprobe cp210x    # for CP2102")
    print("           sudo modprobe ch341     # for CH340")
    print("      d) After loading driver, unplug and replug USB")
    ALL_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 2: lsusb — what USB devices does the Pi see?
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/7] USB bus scan (lsusb) ...")
try:
    result = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
    lines  = result.stdout.strip().split("\n")
    for line in lines:
        tag = "  →  " if any(k in line.lower() for k in
                             ["cp210", "ch340", "ftdi", "pl2303", "sillab", "prolific"]) else "     "
        print(f"     {tag}{line}")
    if not any(any(k in line.lower() for k in
                   ["cp210", "ch340", "ftdi", "pl2303", "sillab", "prolific"])
               for line in lines):
        print("     ⚠️   No known USB-serial adapter found in lsusb output.")
        print("         Check your TTL adapter chip (CP2102, CH340, FT232, PL2303)")
except FileNotFoundError:
    print("     ⚠️   lsusb not available — install with: sudo apt install usbutils")
except Exception as e:
    print(f"     ⚠️   lsusb error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 3: User in 'dialout' group (permission to open serial port)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/7] Checking serial port permissions ...")
import grp, pwd

username = os.environ.get("USER") or os.environ.get("LOGNAME") or "pi"
try:
    groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
    if "dialout" in groups or "tty" in groups:
        print(f"      ✅  User '{username}' is in dialout/tty group")
    else:
        print(f"      ❌  User '{username}' NOT in 'dialout' group!")
        print()
        print("      FIX:")
        print(f"           sudo usermod -a -G dialout {username}")
        print(f"           sudo usermod -a -G tty     {username}")
        print("           Then LOG OUT AND LOG BACK IN (or reboot)")
        print("           Verify with:  groups")
        ALL_OK = False
except Exception as e:
    print(f"      ⚠️   Could not check groups: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 4: pyfingerprint installed
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/7] Checking pyfingerprint library ...")
try:
    from pyfingerprint.pyfingerprint import PyFingerprint
    print("      ✅  pyfingerprint imported OK")
except ImportError:
    print("      ❌  pyfingerprint not installed!")
    print()
    print("      FIX:")
    print("           pip install pyfingerprint --break-system-packages")
    print("           OR (if using venv):")
    print("           pip install pyfingerprint")
    ALL_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 5: pyserial installed
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/7] Checking pyserial library ...")
try:
    import serial
    print(f"      ✅  pyserial {serial.VERSION} installed")
except ImportError:
    print("      ❌  pyserial not installed!")
    print()
    print("      FIX:")
    print("           pip install pyserial --break-system-packages")
    ALL_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 6: Try to connect with correct baud rate (9600)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6/7] Attempting sensor connection ...")

BAUD_RATES_TO_TRY = [9600, 57600, 115200, 19200, 38400]

if not usb_ports:
    print("      ⏭️   Skipped — no serial port found (see check 1)")
else:
    try:
        from pyfingerprint.pyfingerprint import PyFingerprint

        connected = False
        for port in usb_ports:
            for baud in BAUD_RATES_TO_TRY:
                try:
                    print(f"      Trying {port} @ {baud} baud ...", end=" ", flush=True)
                    f = PyFingerprint(port, baud)
                    if f.verifyPassword():
                        print(f"✅  CONNECTED!")
                        print(f"\n      ════ WORKING SETTINGS ════")
                        print(f"      Port : {port}")
                        print(f"      Baud : {baud}")
                        print(f"      ══════════════════════════")

                        # Read sensor info
                        try:
                            cap = f.getStorageCapacity()
                            cnt = f.getTemplateCount()
                            print(f"\n      Sensor capacity : {cap} templates")
                            print(f"      Stored templates: {cnt}")
                        except Exception:
                            pass

                        connected = True
                        break
                    else:
                        print("wrong password")
                except Exception as exc:
                    msg = str(exc)
                    if "Permission denied" in msg:
                        print("PERMISSION DENIED")
                        print(f"      ❌  Fix: sudo chmod 666 {port}")
                        print(f"         Or add user to dialout group (see check 3)")
                        ALL_OK = False
                        break
                    elif "No such file" in msg:
                        print("port gone")
                    else:
                        short = msg[:60]
                        print(f"failed ({short})")
            if connected:
                break

        if not connected:
            print("\n      ❌  Could not connect on any port/baud combination.")
            print()
            print("      MOST COMMON CAUSES:")
            print("      a) WRONG WIRING — most likely cause:")
            print("         R307 sensor pins:  VCC  GND  TX  RX")
            print("         TTL adapter pins:  VCC  GND  RX  TX")
            print("         ⚠️  Connect sensor TX → adapter RX")
            print("            Connect sensor RX → adapter TX")
            print("            (TX and RX are CROSSED — not same-to-same)")
            print("         VCC must be 3.3V (some sensors) or 5V (R307)")
            print()
            print("      b) WRONG BAUD RATE:")
            print("         Default R307 baud rate is 57600, NOT 9600")
            print("         Some modules are pre-set to 9600")
            print("         The script tried both — if neither worked,")
            print("         your wiring is likely incorrect")
            print()
            print("      c) VOLTAGE MISMATCH:")
            print("         R307 needs 5V VCC (not 3.3V)")
            print("         Use Pi's 5V pin, not 3.3V pin")
            ALL_OK = False

    except ImportError:
        print("      ⏭️   Skipped — pyfingerprint not installed")

# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 7: Raw serial communication test (without pyfingerprint)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7/7] Raw serial port open test ...")
if not usb_ports:
    print("      ⏭️   Skipped — no serial port found")
else:
    try:
        import serial as _serial
        for port in usb_ports:
            for baud in [9600, 57600]:
                try:
                    s = _serial.Serial(port, baud, timeout=1)
                    print(f"      ✅  {port} @ {baud} baud opens OK (raw serial)")
                    s.close()
                    break
                except _serial.SerialException as e:
                    print(f"      ❌  {port} @ {baud}: {e}")
                    if "Permission denied" in str(e):
                        print(f"         FIX: sudo chmod 666 {port}")
    except ImportError:
        print("      ⏭️   Skipped — pyserial not installed")

# ─────────────────────────────────────────────────────────────────────────────
#  SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if ALL_OK:
    print("  ✅  All checks passed — sensor should work.")
    print("  Run the app:  python3 main.py")
else:
    print("  ❌  Issues found — fix the errors above, then re-run:")
    print("       python3 fingerprint_debug.py")
print("=" * 60)
print()

print("WIRING REFERENCE (R307 → USB TTL adapter):")
print("  R307 Pin 1  VCC  →  TTL  5V    (⚠️  must be 5V, not 3.3V)")
print("  R307 Pin 2  GND  →  TTL  GND")
print("  R307 Pin 3  TX   →  TTL  RXD   (⚠️  TX goes to RX — crossed!)")
print("  R307 Pin 4  RX   →  TTL  TXD   (⚠️  RX goes to TX — crossed!)")
print("  R307 Pin 5  WAKE →  leave unconnected (or pull HIGH)")
print("  R307 Pin 6  3.3V →  leave unconnected")
print()
print("QUICK FIX COMMANDS (run on Raspberry Pi):")
print("  # Install dependencies")
print("  pip install pyfingerprint pyserial --break-system-packages")
print()
print("  # Fix permissions")
print("  sudo usermod -a -G dialout $USER")
print("  sudo chmod 666 /dev/ttyUSB0")
print()
print("  # Load USB-serial drivers")
print("  sudo modprobe cp210x && sudo modprobe ch341")
print()
print("  # Verify sensor is seen by OS")
print("  lsusb")
print("  ls -la /dev/ttyUSB*")
