"""
Futurix Jarvis — Centralized Stylesheet.

Dark futuristic theme with cyan accents, glassmorphism surfaces, and
smooth animations.  All QSS is defined here so the visual design is
maintained in one place.
"""

from __future__ import annotations

# ── Colour Palette ───────────────────────────────────────────────────────────
# Primary background:    #0a0e1a  (deep space navy)
# Secondary background:  #111827  (dark panel)
# Surface / cards:       #1e293b  (elevated surface)
# Border:                #334155  (subtle separator)
# Text primary:          #f1f5f9  (near white)
# Text secondary:        #94a3b8  (muted)
# Accent cyan:           #00d4ff
# Accent purple:         #7c3aed
# Success green:         #22c55e
# Warning amber:         #f59e0b
# Error red:             #ef4444

MAIN_STYLESHEET = """
/* ── Global ────────────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #0a0e1a;
    color: #f1f5f9;
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif;
    font-size: 14px;
}

/* ── Scroll Bars ───────────────────────────────────────────── */
QScrollBar:vertical {
    background: #111827;
    width: 8px;
    margin: 0;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #00d4ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #111827;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #00d4ff;
}

/* ── Menus ─────────────────────────────────────────────────── */
QMenuBar {
    background: #111827;
    color: #f1f5f9;
    border-bottom: 1px solid #334155;
    padding: 4px;
}
QMenuBar::item:selected {
    background: #1e293b;
    border-radius: 4px;
}
QMenu {
    background: #1e293b;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item:selected {
    background: rgba(0, 212, 255, 0.15);
    border-radius: 4px;
}

/* ── Status Bar ────────────────────────────────────────────── */
QStatusBar {
    background: #111827;
    color: #94a3b8;
    border-top: 1px solid #334155;
    font-size: 12px;
    padding: 2px 8px;
}

/* ── Tooltips ──────────────────────────────────────────────── */
QToolTip {
    background: #1e293b;
    color: #f1f5f9;
    border: 1px solid #00d4ff;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
"""

# ── History Panel (sidebar) ──────────────────────────────────────────────────

SIDEBAR_STYLESHEET = """
QWidget#sidebar {
    background-color: #111827;
    border-right: 1px solid #334155;
}

QLabel#sidebar_title {
    color: #00d4ff;
    font-size: 16px;
    font-weight: bold;
    padding: 12px 16px 4px 16px;
}

QPushButton#new_chat_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00d4ff, stop:1 #7c3aed);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 14px;
    font-weight: bold;
    margin: 8px 12px;
}
QPushButton#new_chat_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #33dfff, stop:1 #9b59f5);
}
QPushButton#new_chat_btn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00a8cc, stop:1 #6b2fc4);
}

QListWidget#conversation_list {
    background: transparent;
    border: none;
    outline: none;
    padding: 4px;
}
QListWidget#conversation_list::item {
    background: transparent;
    color: #94a3b8;
    border-radius: 8px;
    padding: 10px 12px;
    margin: 2px 8px;
}
QListWidget#conversation_list::item:hover {
    background: rgba(0, 212, 255, 0.08);
    color: #f1f5f9;
}
QListWidget#conversation_list::item:selected {
    background: rgba(0, 212, 255, 0.15);
    color: #00d4ff;
}
"""

# ── Chat Area ────────────────────────────────────────────────────────────────

CHAT_STYLESHEET = """
QTextBrowser#chat_display {
    background-color: #0a0e1a;
    border: none;
    padding: 16px;
    font-size: 14px;
    line-height: 1.6;
}

QLineEdit#chat_input {
    background-color: #1e293b;
    color: #f1f5f9;
    border: 2px solid #334155;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
    selection-background-color: rgba(0, 212, 255, 0.3);
}
QLineEdit#chat_input:focus {
    border-color: #00d4ff;
}
QLineEdit#chat_input::placeholder {
    color: #64748b;
}

QPushButton#send_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00d4ff, stop:1 #7c3aed);
    color: white;
    border: none;
    border-radius: 12px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: bold;
    min-width: 80px;
}
QPushButton#send_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #33dfff, stop:1 #9b59f5);
}
QPushButton#send_btn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #00a8cc, stop:1 #6b2fc4);
}
QPushButton#send_btn:disabled {
    background: #334155;
    color: #64748b;
}
"""

# ── Voice Button ─────────────────────────────────────────────────────────────

VOICE_BUTTON_STYLESHEET = """
QPushButton#voice_btn {
    background: rgba(0, 212, 255, 0.1);
    border: 2px solid rgba(0, 212, 255, 0.3);
    border-radius: 24px;
    min-width: 48px;
    min-height: 48px;
    max-width: 48px;
    max-height: 48px;
    font-size: 20px;
    color: #00d4ff;
}
QPushButton#voice_btn:hover {
    background: rgba(0, 212, 255, 0.2);
    border-color: #00d4ff;
}
QPushButton#voice_btn:pressed {
    background: rgba(0, 212, 255, 0.3);
}
QPushButton#voice_btn[listening="true"] {
    background: rgba(239, 68, 68, 0.2);
    border-color: #ef4444;
    color: #ef4444;
}
"""

# ── Model Selector ──────────────────────────────────────────────────────────

MODEL_SELECTOR_STYLESHEET = """
QComboBox#model_selector {
    background: #1e293b;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px 12px;
    min-width: 150px;
    font-size: 12px;
}
QComboBox#model_selector:hover {
    border-color: #00d4ff;
}
QComboBox#model_selector::drop-down {
    border: none;
    width: 24px;
}
QComboBox#model_selector QAbstractItemView {
    background: #1e293b;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 8px;
    selection-background-color: rgba(0, 212, 255, 0.15);
    outline: none;
}
"""

# ── Status Indicator ────────────────────────────────────────────────────────

STATUS_STYLES = {
    "online": "color: #22c55e; font-weight: bold;",
    "offline": "color: #ef4444; font-weight: bold;",
    "thinking": "color: #f59e0b; font-weight: bold;",
    "listening": "color: #00d4ff; font-weight: bold;",
    "idle": "color: #94a3b8;",
}

# ── Chat Message HTML Templates ──────────────────────────────────────────────

USER_MESSAGE_HTML = """
<div style="
    display: flex;
    justify-content: flex-end;
    margin: 8px 0;
">
    <div style="
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 212, 255, 0.15), stop:1 rgba(124, 58, 237, 0.15));
        background-color: rgba(0, 212, 255, 0.12);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 16px 16px 4px 16px;
        padding: 12px 16px;
        max-width: 70%;
        color: #f1f5f9;
        font-size: 14px;
        margin-left: 30%;
    ">
        <div style="color: #00d4ff; font-size: 11px; font-weight: bold; margin-bottom: 4px;">You</div>
        {message}
    </div>
</div>
"""

ASSISTANT_MESSAGE_HTML = """
<div style="
    margin: 8px 0;
">
    <div style="
        background-color: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(51, 65, 85, 0.5);
        border-radius: 16px 16px 16px 4px;
        padding: 12px 16px;
        max-width: 80%;
        color: #f1f5f9;
        font-size: 14px;
    ">
        <div style="color: #7c3aed; font-size: 11px; font-weight: bold; margin-bottom: 4px;">⚡ Jarvis</div>
        {message}
    </div>
</div>
"""

TOOL_EXECUTION_HTML = """
<div style="
    margin: 4px 0;
    padding: 8px 12px;
    background-color: rgba(34, 197, 94, 0.08);
    border-left: 3px solid #22c55e;
    border-radius: 0 8px 8px 0;
    font-size: 12px;
    color: #94a3b8;
">
    🔧 <span style="color: #22c55e; font-weight: bold;">{tool_name}</span> — {result_preview}
</div>
"""

SYSTEM_MESSAGE_HTML = """
<div style="
    text-align: center;
    margin: 12px 0;
    color: #64748b;
    font-size: 12px;
    font-style: italic;
">
    {message}
</div>
"""

WELCOME_HTML = """
<div style="text-align: center; padding: 40px 20px;">
    <div style="font-size: 48px; margin-bottom: 16px;">⚡</div>
    <div style="
        font-size: 28px;
        font-weight: bold;
        background: linear-gradient(90deg, #00d4ff, #7c3aed);
        -webkit-background-clip: text;
        color: #00d4ff;
        margin-bottom: 8px;
    ">Futurix Jarvis</div>
    <div style="color: #94a3b8; font-size: 14px; margin-bottom: 24px;">
        Your intelligent desktop assistant
    </div>
    <div style="color: #64748b; font-size: 13px; max-width: 500px; margin: 0 auto; line-height: 1.8;">
        Try saying:<br>
        <span style="color: #00d4ff;">"Open Chrome"</span> · 
        <span style="color: #00d4ff;">"Search Google for Python tutorials"</span><br>
        <span style="color: #00d4ff;">"Show battery status"</span> · 
        <span style="color: #00d4ff;">"Create a folder called Projects"</span><br>
        <span style="color: #00d4ff;">"Analyse this repository"</span> · 
        <span style="color: #00d4ff;">"Take a screenshot"</span>
    </div>
</div>
"""
