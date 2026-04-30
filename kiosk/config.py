#!/usr/bin/env python3
"""
config.py — Shared constants, colour palette, QSS, translations, AppState.
All modules import from here.  No UI or hardware code lives here.
"""

# ──────────────────────────────────────────────────────────────────────────────
#  COLOUR PALETTE  (warm brown / terracotta / cream)
# ──────────────────────────────────────────────────────────────────────────────
PALETTE = {
    "bg":         "#FDF6EC",
    "bg2":        "#F5E6D0",
    "card":       "#FFFAF4",
    "primary":    "#8B4513",
    "primary_lt": "#A0522D",
    "accent":     "#CD853F",
    "accent2":    "#D2691E",
    "gold":       "#DAA520",
    "gold_lt":    "#F4C96E",
    "success":    "#5D8A5E",
    "error":      "#B94040",
    "text":       "#3B1F0A",
    "text_sec":   "#7A5C3A",
    "border":     "#C8A882",
    "shadow":     "#D4B896",
    "white":      "#FFFFFF",
    "overlay":    "rgba(139,69,19,0.08)",
}

# ──────────────────────────────────────────────────────────────────────────────
#  GLOBAL STYLE SHEETS
# ──────────────────────────────────────────────────────────────────────────────
GLOBAL_QSS = f"""
QWidget {{
    background-color: {PALETTE['bg']};
    color: {PALETTE['text']};
    font-family: 'Noto Sans', 'Noto Sans Devanagari', Arial, sans-serif;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollBar:vertical {{
    width: 8px;
    background: {PALETTE['bg2']};
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {PALETTE['accent']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QLineEdit {{
    background: {PALETTE['card']};
    border: 2px solid {PALETTE['border']};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 18px;
    color: {PALETTE['text']};
}}
QLineEdit:focus {{
    border-color: {PALETTE['primary']};
}}
"""

BTN_PRIMARY_QSS = f"""
QPushButton {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {PALETTE['primary_lt']}, stop:1 {PALETTE['primary']});
    color: {PALETTE['white']};
    border-radius: 14px;
    padding: 14px 24px;
    font-size: 20px;
    font-weight: bold;
    border: none;
    min-height: 70px;
}}
QPushButton:pressed {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 {PALETTE['primary']}, stop:1 #5C2E00);
    padding-top: 17px;
}}
QPushButton:disabled {{
    background: {PALETTE['border']};
    color: {PALETTE['bg2']};
}}
"""

BTN_SECONDARY_QSS = f"""
QPushButton {{
    background: {PALETTE['card']};
    color: {PALETTE['primary']};
    border-radius: 14px;
    padding: 12px 20px;
    font-size: 18px;
    font-weight: bold;
    border: 2px solid {PALETTE['accent']};
    min-height: 60px;
}}
QPushButton:pressed {{
    background: {PALETTE['bg2']};
    padding-top: 15px;
}}
"""

BTN_LANG_QSS = f"""
QPushButton {{
    background: {PALETTE['card']};
    color: {PALETTE['text']};
    border-radius: 12px;
    padding: 10px;
    font-size: 16px;
    font-weight: bold;
    border: 2px solid {PALETTE['border']};
    min-height: 80px;
}}
QPushButton:checked {{
    background: {PALETTE['primary']};
    color: {PALETTE['white']};
    border-color: {PALETTE['primary']};
}}
QPushButton:pressed {{
    background: {PALETTE['bg2']};
}}
"""

# ──────────────────────────────────────────────────────────────────────────────
#  TRANSLATIONS  — 10 Indian languages + English
# ──────────────────────────────────────────────────────────────────────────────
TRANSLATIONS = {
    "English": {
        "flag": "🇬🇧", "name": "English",
        "welcome": "Welcome to ArtBridge",
        "tagline": "Empowering Rural Artisans with Technology",
        "start": "🚀  Get Started",
        "select_language": "Language selected",
        "back": "← Back",
        "fingerprint_title": "Place Your Finger",
        "fingerprint_hint": "Touch the sensor to verify your identity",
        "scan_finger": "👆  Scan Fingerprint",
        "scanning": "Scanning… please hold still",
        "login_success": "✅  Authentication Successful!",
        "login_failed": "❌  Fingerprint not recognised",
        "try_again": "Try again",
        "register_title": "Register Your Fingerprint",
        "register_step1": "Step 1 — Place your finger on the sensor",
        "register_step2": "Step 2 — Remove your finger",
        "register_step3": "Step 3 — Place the same finger again",
        "register_success": "✅  Fingerprint registered!",
        "register_failed": "❌  Registration failed. Try again.",
        "enter_name": "Enter your name",
        "register_btn": "📝  Register",
        "hello": "Hello",
        "dashboard": "Dashboard",
        "add_product": "➕  Add Product",
        "my_products": "📦  My Products",
        "orders": "📋  Orders",
        "earnings": "💰  Earnings",
        "sync": "🔄  Sync",
        "online": "🟢 Online",
        "offline": "🔴 Offline",
        "product_added": "Product added successfully!",
        "photo_hint": "Take a photo of your product",
        "voice_input": "🎙️  Speak Product Name",
        "speak_hint": "Press the button and speak clearly",
        "price_hint": "Enter the price of your product",
        "validating": "Validating product…",
        "confirm_hint": "Review and confirm your product",
        "recording": "🔴  Recording…",
        "my_products": "My Products",
        "earnings": "Earnings",
        "orders": "Orders",
    },
    "हिंदी": {
        "flag": "🇮🇳", "name": "हिंदी",
        "welcome": "ArtBridge में आपका स्वागत है",
        "tagline": "तकनीक से ग्रामीण कारीगरों को सशक्त बनाना",
        "start": "🚀  शुरू करें",
        "select_language": "भाषा चुनी गई",
        "back": "← वापस",
        "fingerprint_title": "अपनी उंगली रखें",
        "fingerprint_hint": "पहचान सत्यापित करने के लिए सेंसर छुएं",
        "scan_finger": "👆  फिंगरप्रिंट स्कैन करें",
        "scanning": "स्कैन हो रहा है… स्थिर रहें",
        "login_success": "✅  प्रमाणीकरण सफल!",
        "login_failed": "❌  फिंगरप्रिंट पहचाना नहीं गया",
        "try_again": "पुनः प्रयास करें",
        "register_title": "अपना फिंगरप्रिंट पंजीकृत करें",
        "register_step1": "चरण 1 — सेंसर पर उंगली रखें",
        "register_step2": "चरण 2 — उंगली हटाएं",
        "register_step3": "चरण 3 — वही उंगली फिर रखें",
        "register_success": "✅  फिंगरप्रिंट पंजीकृत!",
        "register_failed": "❌  पंजीकरण विफल। पुनः प्रयास करें।",
        "enter_name": "अपना नाम दर्ज करें",
        "register_btn": "📝  पंजीकरण करें",
        "hello": "नमस्ते",
        "dashboard": "डैशबोर्ड",
        "add_product": "➕  उत्पाद जोड़ें",
        "my_products": "📦  मेरे उत्पाद",
        "orders": "📋  ऑर्डर",
        "earnings": "💰  आय",
        "sync": "🔄  सिंक",
        "online": "🟢 ऑनलाइन",
        "offline": "🔴 ऑफलाइन",
        "product_added": "उत्पाद सफलतापूर्वक जोड़ा गया!",
        "photo_hint": "अपने उत्पाद की फोटो लें",
        "voice_input": "🎙️  उत्पाद का नाम बोलें",
        "speak_hint": "बटन दबाएं और स्पष्ट रूप से बोलें",
        "price_hint": "उत्पाद की कीमत दर्ज करें",
        "validating": "उत्पाद सत्यापित हो रहा है…",
        "confirm_hint": "अपने उत्पाद की समीक्षा और पुष्टि करें",
        "recording": "🔴  रिकॉर्ड हो रहा है…",
    },
    "தமிழ்": {
        "flag": "🏛️", "name": "தமிழ்",
        "welcome": "ArtBridge-க்கு வரவேற்கிறோம்",
        "tagline": "தொழில்நுட்பத்தால் கிராம கலைஞர்களை வலுப்படுத்துதல்",
        "start": "🚀  தொடங்குங்கள்",
        "select_language": "மொழி தேர்ந்தெடுக்கப்பட்டது",
        "back": "← பின்னால்",
        "fingerprint_title": "விரலை வைக்கவும்",
        "fingerprint_hint": "அடையாளம் சரிபார்க்க சென்சாரை தொடவும்",
        "scan_finger": "👆  கைரேகை ஸ்கேன் செய்யவும்",
        "scanning": "ஸ்கேன் ஆகிறது… அசையாமல் இருங்கள்",
        "login_success": "✅  அங்கீகாரம் வெற்றி!",
        "login_failed": "❌  கைரேகை அங்கீகரிக்கப்படவில்லை",
        "try_again": "மீண்டும் முயலவும்",
        "register_title": "கைரேகையை பதிவு செய்யவும்",
        "register_step1": "படி 1 — சென்சாரில் விரல் வைக்கவும்",
        "register_step2": "படி 2 — விரலை எடுக்கவும்",
        "register_step3": "படி 3 — அதே விரலை மீண்டும் வைக்கவும்",
        "register_success": "✅  கைரேகை பதிவு செய்யப்பட்டது!",
        "register_failed": "❌  பதிவு தோல்வி. மீண்டும் முயலவும்.",
        "enter_name": "உங்கள் பெயரை உள்ளிடவும்",
        "register_btn": "📝  பதிவு செய்யவும்",
        "hello": "வணக்கம்",
        "dashboard": "டாஷ்போர்டு",
        "add_product": "➕  பொருள் சேர்க்கவும்",
        "my_products": "📦  என் பொருட்கள்",
        "orders": "📋  ஆர்டர்கள்",
        "earnings": "💰  வருமானம்",
        "sync": "🔄  ஒத்திசை",
        "online": "🟢 ஆன்லைன்",
        "offline": "🔴 ஆஃப்லைன்",
        "product_added": "பொருள் வெற்றிகரமாக சேர்க்கப்பட்டது!",
        "photo_hint": "உங்கள் பொருளின் புகைப்படம் எடுக்கவும்",
        "voice_input": "🎙️  பொருளின் பெயரை பேசுங்கள்",
        "speak_hint": "பொத்தானை அழுத்தி தெளிவாக பேசுங்கள்",
        "price_hint": "பொருளின் விலையை உள்ளிடவும்",
        "validating": "பொருளை சரிபார்க்கிறது…",
        "confirm_hint": "உங்கள் பொருளை மதிப்பாய்வு செய்து உறுதிப்படுத்தவும்",
        "recording": "🔴  பதிவாகிறது…",
    },
    "తెలుగు": {
        "flag": "🌺", "name": "తెలుగు",
        "welcome": "ArtBridge కి స్వాగతం",
        "tagline": "సాంకేతికతతో గ్రామీణ కళాకారులను శక్తివంతం చేయడం",
        "start": "🚀  ప్రారంభించండి",
        "select_language": "భాష ఎంచుకోబడింది",
        "back": "← వెనుకకు",
        "fingerprint_title": "వేలు పెట్టండి",
        "fingerprint_hint": "గుర్తింపు ధృవీకరించడానికి సెన్సర్ తాకండి",
        "scan_finger": "👆  వేలిముద్ర స్కాన్",
        "scanning": "స్కాన్ అవుతోంది… స్థిరంగా ఉండండి",
        "login_success": "✅  ప్రమాణీకరణ విజయవంతమైంది!",
        "login_failed": "❌  వేలిముద్ర గుర్తించబడలేదు",
        "try_again": "మళ్ళీ ప్రయత్నించండి",
        "register_title": "వేలిముద్రను నమోదు చేయండి",
        "register_step1": "దశ 1 — సెన్సర్ పై వేలు ఉంచండి",
        "register_step2": "దశ 2 — వేలు తీయండి",
        "register_step3": "దశ 3 — అదే వేలు మళ్ళీ ఉంచండి",
        "register_success": "✅  వేలిముద్ర నమోదైంది!",
        "register_failed": "❌  నమోదు విఫలమైంది. మళ్ళీ ప్రయత్నించండి.",
        "enter_name": "మీ పేరు నమోదు చేయండి",
        "register_btn": "📝  నమోదు చేయండి",
        "hello": "నమస్కారం",
        "dashboard": "డాష్‌బోర్డ్",
        "add_product": "➕  ఉత్పత్తి జోడించండి",
        "my_products": "📦  నా ఉత్పత్తులు",
        "orders": "📋  ఆర్డర్లు",
        "earnings": "💰  ఆదాయం",
        "sync": "🔄  సమకాలీకరించు",
        "online": "🟢 ఆన్‌లైన్",
        "offline": "🔴 ఆఫ్‌లైన్",
        "product_added": "ఉత్పత్తి విజయవంతంగా జోడించబడింది!",
        "photo_hint": "మీ ఉత్పత్తి ఫోటో తీయండి",
        "voice_input": "🎙️  ఉత్పత్తి పేరు చెప్పండి",
        "speak_hint": "బటన్ నొక్కి స్పష్టంగా మాట్లాడండి",
        "price_hint": "ఉత్పత్తి ధర నమోదు చేయండి",
        "validating": "ఉత్పత్తిని ధృవీకరిస్తోంది…",
        "confirm_hint": "మీ ఉత్పత్తిని సమీక్షించి నిర్ధారించండి",
        "recording": "🔴  రికార్డ్ అవుతోంది…",
    },
    "ಕನ್ನಡ": {
        "flag": "🌻", "name": "ಕನ್ನಡ",
        "welcome": "ArtBridge ಗೆ ಸ್ವಾಗತ",
        "tagline": "ತಂತ್ರಜ್ಞಾನದಿಂದ ಗ್ರಾಮೀಣ ಕಲಾವಿದರನ್ನು ಸಬಲಗೊಳಿಸುವುದು",
        "start": "🚀  ಪ್ರಾರಂಭಿಸಿ",
        "select_language": "ಭಾಷೆ ಆಯ್ಕೆ ಮಾಡಲಾಗಿದೆ",
        "back": "← ಹಿಂದೆ",
        "fingerprint_title": "ಬೆರಳಿಡಿ",
        "fingerprint_hint": "ಗುರುತು ಪರಿಶೀಲಿಸಲು ಸೆನ್ಸರ್ ಮುಟ್ಟಿ",
        "scan_finger": "👆  ಬೆರಳಚ್ಚು ಸ್ಕ್ಯಾನ್ ಮಾಡಿ",
        "scanning": "ಸ್ಕ್ಯಾನ್ ಆಗುತ್ತಿದೆ… ಸ್ಥಿರವಾಗಿರಿ",
        "login_success": "✅  ದೃಢೀಕರಣ ಯಶಸ್ವಿ!",
        "login_failed": "❌  ಬೆರಳಚ್ಚು ಗುರುತಿಸಲಿಲ್ಲ",
        "try_again": "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ",
        "register_title": "ನಿಮ್ಮ ಬೆರಳಚ್ಚು ನೋಂದಾಯಿಸಿ",
        "register_step1": "ಹಂತ 1 — ಸೆನ್ಸರ್ ಮೇಲೆ ಬೆರಳಿಡಿ",
        "register_step2": "ಹಂತ 2 — ಬೆರಳು ತೆಗೆಯಿರಿ",
        "register_step3": "ಹಂತ 3 — ಅದೇ ಬೆರಳನ್ನು ಮತ್ತೆ ಇಡಿ",
        "register_success": "✅  ಬೆರಳಚ್ಚು ನೋಂದಾಯಿಸಲಾಗಿದೆ!",
        "register_failed": "❌  ನೋಂದಣಿ ವಿಫಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "enter_name": "ನಿಮ್ಮ ಹೆಸರನ್ನು ನಮೂದಿಸಿ",
        "register_btn": "📝  ನೋಂದಾಯಿಸಿ",
        "hello": "ನಮಸ್ಕಾರ",
        "dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
        "add_product": "➕  ಉತ್ಪನ್ನ ಸೇರಿಸಿ",
        "my_products": "📦  ನನ್ನ ಉತ್ಪನ್ನಗಳು",
        "orders": "📋  ಆರ್ಡರ್‌ಗಳು",
        "earnings": "💰  ಆದಾಯ",
        "sync": "🔄  ಸಿಂಕ್",
        "online": "🟢 ಆನ್‌ಲೈನ್",
        "offline": "🔴 ಆಫ್‌ಲೈನ್",
        "product_added": "ಉತ್ಪನ್ನ ಯಶಸ್ವಿಯಾಗಿ ಸೇರಿಸಲಾಗಿದೆ!",
        "photo_hint": "ನಿಮ್ಮ ಉತ್ಪನ್ನದ ಫೋಟೋ ತೆಗೆಯಿರಿ",
        "voice_input": "🎙️  ಉತ್ಪನ್ನದ ಹೆಸರು ಹೇಳಿ",
        "speak_hint": "ಬಟನ್ ಒತ್ತಿ ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ",
        "price_hint": "ಉತ್ಪನ್ನದ ಬೆಲೆ ನಮೂದಿಸಿ",
        "validating": "ಉತ್ಪನ್ನ ಪರಿಶೀಲಿಸಲಾಗುತ್ತಿದೆ…",
        "confirm_hint": "ನಿಮ್ಮ ಉತ್ಪನ್ನವನ್ನು ಪರಿಶೀಲಿಸಿ ದೃಢಪಡಿಸಿ",
        "recording": "🔴  ರೆಕಾರ್ಡ್ ಆಗುತ್ತಿದೆ…",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
#  APPLICATION STATE  — singleton namespace shared across all modules
# ──────────────────────────────────────────────────────────────────────────────
class AppState:
    language:      str  = "English"
    is_online:     bool = True
    current_user:  tuple = None   # (id, name)
    db             = None         # DatabaseManager instance (set at startup)
    voice          = None         # VoiceEngine instance  (set at startup)
    sensor         = None         # FingerprintSensor instance (set at startup)


# ──────────────────────────────────────────────────────────────────────────────
#  TRANSLATION HELPER
# ──────────────────────────────────────────────────────────────────────────────
def t(key: str) -> str:
    """Return the translated string for *key* in the current AppState.language."""
    lang = TRANSLATIONS.get(AppState.language, TRANSLATIONS["English"])
    return lang.get(key, TRANSLATIONS["English"].get(key, key))
