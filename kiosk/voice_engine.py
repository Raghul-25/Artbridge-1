#!/usr/bin/env python3
"""
voice/engine.py — Multi-language TTS with 4-level fallback.

Priority order (best → most robust):
  Level 1 → gTTS  + pygame      (best quality, needs internet 1st run)
  Level 2 → gTTS  + ffplay      (fallback player if pygame missing)
  Level 3 → pyttsx3             (offline, quality varies by OS)
  Level 4 → espeak / espeak-ng  (offline, robotic but always works)
  Level 0 → silent (no TTS found)

Designed to be non-blocking: all speech runs in a dedicated daemon thread
via an internal queue.  The UI never blocks waiting for audio.
"""

import importlib
import os
import sys
import shutil
import subprocess
import tempfile
import threading
import time
import pyttsx3

from config import AppState, TRANSLATIONS


# ──────────────────────────────────────────────────────────────────────────────
#  Helper: silent background pip-install
# ──────────────────────────────────────────────────────────────────────────────
def _pip_install(*packages):
    try:
        subprocess.run(
            ["pip", "install", "--quiet", "--upgrade", *packages],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
#  VoiceEngine
# ──────────────────────────────────────────────────────────────────────────────
class VoiceEngine:
    """
    Thread-safe, non-blocking TTS engine.

    Usage:
        voice = VoiceEngine()
        voice.speak("Place your finger")          # raw text
        voice.speak("fingerprint_hint")           # translation key
        voice.set_language("தமிழ்")               # change language
    """

    # BCP-47 language code map
    LANG_CODE_MAP = {
        "English": "en",
        "हिंदी":   "hi",
        "தமிழ்":   "ta",
        "తెలుగు":  "te",
        "ಕನ್ನಡ":   "kn",
        "മലയാളം":  "ml",
        "বাংলা":   "bn",
        "मराठी":   "mr",
        "ગુજરાતી": "gu",
        "ਪੰਜਾਬੀ":  "pa",
        "ଓଡ଼ିଆ":   "or",
    }

    # pyttsx3 voice-selection hints per language code
    PYTTSX3_HINTS = {
        "en": ["english", "en_us", "en_gb", "en-us", "en-gb"],
        "hi": ["hindi", "hi_in"],
        "ta": ["tamil", "ta_in"],
        "te": ["telugu", "te_in"],
        "kn": ["kannada", "kn_in"],
        "ml": ["malayalam", "ml_in"],
        "bn": ["bengali", "bn_in"],
        "mr": ["marathi", "mr_in"],
        "gu": ["gujarati", "gu_in"],
        "pa": ["punjabi", "pa_in"],
        "or": ["odia", "or_in"],
    }

    def __init__(self):
        self._queue   = []
        self._lock    = threading.Lock()
        self._method  = None      # set by _detect_method()
        self._engine  = None      # pyttsx3 engine (if used)
        self._cache   = {}        # (phrase, lang_code) → mp3 path
        self._tmp     = tempfile.mkdtemp(prefix="artbridge_voice_")
        self._running = True

        # Detect best available TTS immediately
        self._detect_method()

        # Background worker thread — never blocks UI
        threading.Thread(target=self._worker_loop, daemon=True).start()

        # Try to upgrade to gTTS in background (internet may be available)
        threading.Thread(target=self._auto_upgrade, daemon=True).start()

        print(f"[Voice] method={self._method or 'none (silent)'}")

    # ── Method detection ──────────────────────────────────────────────────────
    def _detect_method(self):
        """Select the best available TTS + playback combination."""

        # Level 1: gTTS + Subprocess (Preferred on Linux/Pi to avoid pygame hangs)
        if sys.platform.startswith("linux"):
            player = shutil.which("mpg123") or shutil.which("mpg321") or shutil.which("ffplay")
            if player:
                try:
                    importlib.import_module("gtts")
                    self._player = player
                    self._method = "gtts_subprocess"
                    return
                except Exception:
                    pass

        # Level 2: gTTS + pygame (Best for Windows/Mac)
        try:
            importlib.import_module("gtts")
            importlib.import_module("pygame")
            import pygame
            # Small delay and specific init to avoid hangs
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
            self._pygame = pygame
            self._method = "gtts_pygame"
            return
        except Exception:
            pass

        # Level 3: gTTS + Subprocess (Fallback for other OS)
        try:
            importlib.import_module("gtts")
            player = shutil.which("ffplay") or shutil.which("mpg123") or shutil.which("mpg321")
            if player:
                self._player = player
                self._method = "gtts_subprocess"
                return
        except Exception:
            pass

        # Level 4: pyttsx3 (fully offline)
        try:
            importlib.import_module("pyttsx3")
            import pyttsx3
            eng = pyttsx3.init()
            eng.setProperty("rate", 145)
            self._engine = eng
            self._method = "pyttsx3"
            return
        except Exception:
            pass

        # Level 5: espeak / espeak-ng (offline, robotic)
        if shutil.which("espeak-ng") or shutil.which("espeak"):
            self._method = "espeak"
            return

        self._method = None  # Silent — no TTS available

    def _auto_upgrade(self):
        """Install gTTS + pygame in the background; upgrade method if possible."""
        _pip_install("gtts", "pygame")
        time.sleep(2)
        if self._method not in ("gtts_pygame", "gtts_subprocess"):
            old = self._method
            self._detect_method()
            if self._method != old:
                print(f"[Voice] upgraded method -> {self._method}")

    # -- Language helpers ------------------------------------------------------
    def _current_lang_code(self) -> str:
        return self.LANG_CODE_MAP.get(AppState.language, "en")

    @staticmethod
    def _phrases_for_lang(lang_name: str) -> dict:
        return TRANSLATIONS.get(lang_name, TRANSLATIONS["English"])

    # ── Public API ────────────────────────────────────────────────────────────
    def speak(self, text: str):
        """
        Queue *text* for speech.  Accepts a translation key or raw text.
        Phrase is automatically resolved using AppState.language so voice
        always matches the currently selected UI language.
        """
        if not text:
            return
        lang_name = AppState.language
        phrases   = self._phrases_for_lang(lang_name)
        phrase    = phrases.get(text, text)   # resolve key or pass raw text
        if not phrase:
            return
        with self._lock:
            self._queue.clear()   # CLEAR OLD VOICE
            self._queue.append(phrase)

    def speak_raw(self, text: str):
        """Queue a raw text string (no translation lookup)."""
        if not text:
            return
        with self._lock:
            if not self._queue or self._queue[-1] != text:
                self._queue.append(text)

    def set_language(self, lang_name: str):
        """
        Switch the voice engine to the given language.
        For pyttsx3, immediately selects the closest available voice.
        For gTTS/espeak the language is resolved dynamically at speak-time.
        """
        lang_code = self.LANG_CODE_MAP.get(lang_name, "en")
        if self._method == "pyttsx3" and self._engine:
            hints    = self.PYTTSX3_HINTS.get(lang_code, [lang_code])
            en_hints = self.PYTTSX3_HINTS.get("en", ["english", "en_us"])
            voices   = self._engine.getProperty("voices")
            matched  = False
            for v in voices:
                id_name = (v.id + v.name).lower()
                if any(h in id_name for h in hints):
                    self._engine.setProperty("voice", v.id)
                    matched = True
                    break
            if not matched:
                for v in voices:
                    id_name = (v.id + v.name).lower()
                    if any(h in id_name for h in en_hints):
                        self._engine.setProperty("voice", v.id)
                        break

    def shutdown(self):
        """Stop the worker loop gracefully."""
        self._running = False

    # ── Worker ────────────────────────────────────────────────────────────────
    def _worker_loop(self):
        while self._running:
            phrase = None
            with self._lock:
                if self._queue:
                    phrase = self._queue.pop(0)
            if phrase:
                try:
                    self._play(phrase)
                except Exception as e:
                    print(f"[Voice] play error: {e}")
            else:
                time.sleep(0.04)

    def _play(self, phrase: str):
        m = self._method
        if m is None:
            return
        if m in ("gtts_pygame", "gtts_subprocess"):
            self._play_gtts(phrase)
        elif m == "pyttsx3":
            self._play_pyttsx3(phrase)
        elif m == "espeak":
            self._play_espeak(phrase)

    # ── Playback implementations ──────────────────────────────────────────────
    def _gtts_mp3_path(self, phrase: str) -> str:
        """Return cached MP3 path, generating it if necessary."""
        from gtts import gTTS
        lang_code = self._current_lang_code()
        key = abs(hash(phrase + lang_code)) % (10 ** 10)
        fp  = os.path.join(self._tmp, f"{lang_code}_{key}.mp3")
        if not os.path.exists(fp):
            try:
                gTTS(text=phrase, lang=lang_code, slow=False).save(fp)
            except Exception:
                # Fallback to English if target language unavailable
                try:
                    gTTS(text=phrase, lang="en", slow=False).save(fp)
                except Exception:
                    return ""
        return fp

    def _play_gtts(self, phrase: str):
        fp = self._gtts_mp3_path(phrase)
        if not fp or not os.path.exists(fp):
            return
        if self._method == "gtts_pygame":
            try:
                pg = self._pygame
                pg.mixer.music.load(fp)
                pg.mixer.music.play()
                while pg.mixer.music.get_busy():
                    time.sleep(0.05)
            except Exception:
                pass
        else:
            cmd = self._player
            args = [cmd, "-nodisp", "-autoexit", fp] if "ffplay" in cmd else [cmd, fp]
            try:
                subprocess.run(args, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=15)
            except Exception:
                pass

    def _play_pyttsx3(self, phrase: str):
        if not self._engine:
            return
        try:
            self._engine.say(phrase)
            self._engine.runAndWait()
        except Exception:
            pass

    def _play_espeak(self, phrase: str):
        lang_code = self._current_lang_code()
        cmd = shutil.which("espeak-ng") or shutil.which("espeak") or "espeak"
        try:
            subprocess.run(
                [cmd, "-v", lang_code, "-s", "140", phrase],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except Exception:
            pass
    def stop(self):
        """Immediately stop all speech and clear queue"""
        with self._lock:
            self._queue.clear()

    # Stop active playback
        try:
            if self._method == "pyttsx3" and self._engine:
                self._engine.stop()
        except:
            pass

        try:
            if hasattr(self, "_pygame"):
                self._pygame.mixer.music.stop()
        except:
            pass
