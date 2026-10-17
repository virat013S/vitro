"""The Glass palette — every color nlt-glass paints with, plus its CSS.

Pure data: no GTK imports, so tests can read it anywhere.
"""
from __future__ import annotations

# name → 16 ANSI colors, dark-scheme first, glassy navy base
GLASS = {
    "background": "#161a24",
    "foreground": "#d5dbea",
    "cursor": "#9cc2ff",
    "cursor_text": "#161a24",
    "selection": "#3e6fb0",
    "selection_text": "#ffffff",
    "normal": [
        "#2b3142",  # black
        "#e56c7d",  # red
        "#86d69b",  # green
        "#efc97c",  # yellow
        "#7fa8f7",  # blue
        "#c298f5",  # magenta
        "#79d6d3",  # cyan
        "#c4cddf",  # white
    ],
    "bright": [
        "#5a627a",
        "#f491a0",
        "#a4e3b0",
        "#f7dfa9",
        "#9cc2ff",
        "#d9b6ff",
        "#9be3e0",
        "#edf1fa",
    ],
}

# chrome tones (not terminal colors): window, chrome, text, border
CHROME_BG = "#12141c"
CHROME_FG = "#d6dbe8"
CHROME_DIM = "#8b93a7"
CHROME_BORDER = "#2a3040"

GLASS_CSS = f"""
window {{
    background: {CHROME_BG};
}}
headerbar {{
    background: {CHROME_BG};
    color: {CHROME_FG};
    border-bottom: none;
    box-shadow: none;
}}
headerbar:backdrop {{
    background: #0e1017;
    color: {CHROME_DIM};
}}
headerbar button {{
    background: transparent;
    color: {CHROME_FG};
    border: none;
    padding: 3px 9px;
    border-radius: 8px;
}}
headerbar button:hover {{
    background: #232838;
}}
headerbar button:checked {{
    background: #232838;
    color: {CHROME_FG};
}}
notebook > header {{
    background: {CHROME_BG};
    border: none;
    box-shadow: none;
}}
notebook > header > tabs > tab {{
    background: transparent;
    padding: 3px 4px;
    color: {CHROME_DIM};
    border-bottom: 2px solid transparent;
    min-height: 20px;
}}
notebook > header > tabs > tab:checked {{
    color: {CHROME_FG};
    border-bottom: 2px solid #7fa8f7;
}}
notebook stack {{
    background: {GLASS['background']};
}}
terminal {{
    padding: 12px 14px;
}}
.nlt-side {{
    background: {CHROME_BG};
    border-top: 1px solid {CHROME_BORDER};
}}
.nlt-side-label {{
    color: {CHROME_DIM};
    padding: 4px 14px 0 14px;
    font-size: 88%;
}}
scrollbar {{
    background: transparent;
    border: none;
}}
scrollbar slider {{
    background: #3a4157;
    border-radius: 4px;
    min-width: 6px;
}}
scrollbar slider:hover {{
    background: #4c5471;
}}
"""


def palette_rgba(values: list[str]) -> list[str]:
    """Validate a hex list — raises ValueError on junk. Returns lowercase list."""
    out = []
    for v in values:
        out.append(rgba_hex(v))
    return out


def rgba_hex(value: str) -> str:
    """'#aabbcc' or '#ABC' → '#aabbcc'. ValueError otherwise."""
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        raise ValueError(f"not a hex color: {value!r}")
    return "#" + s.lower()


def pick_font() -> str:
    """Best default font available. Never raises."""
    import shutil
    import subprocess

    if shutil.which("fc-list"):
        try:
            out = subprocess.run(["fc-list", ":family"], capture_output=True,
                                 text=True, timeout=5).stdout
            for want in ("JetBrainsMono Nerd Font", "JetBrains Mono",
                         "FiraCode Nerd Font", "Iosevka", "Cascadia Code"):
                if want in out:
                    return f"{want} 11"
        except Exception:
            pass
    return "Monospace 11"
