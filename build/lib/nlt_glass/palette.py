"""The Glass palette — colors + CSS for nlt-glass.

Pure data: no GTK imports, so tests can read it anywhere. CSS is generated
per-window-opacity so transparency reaches the chrome as well as the cells.
"""
from __future__ import annotations

# name → 8 ANSI base + 8 bright colors, glassy navy base
THEMES: dict[str, dict] = {
    "glass": {
        "background": "#131317",
        "foreground": "#d2d6de",
        "cursor": "#dfe3ee",
        "cursor_text": "#131317",
        "selection": "#3a456a",
        "selection_text": "#ffffff",
        "normal": [
            "#2d3038", "#dc6f78", "#8dcf9d", "#e2c482",
            "#83aaf0", "#c49cf0", "#7bd4d2", "#c6ccda",
        ],
        "bright": [
            "#565c6c", "#f2939c", "#a8e2b3", "#f5dea9",
            "#a5c4ff", "#dbb8fb", "#9fe3e1", "#e9edf6",
        ],
    },
    "graphite": {
        "background": "#101014",
        "foreground": "#d7d7dc",
        "cursor": "#e8e8ee",
        "cursor_text": "#101014",
        "selection": "#51557a",
        "selection_text": "#ffffff",
        "normal": [
            "#242430", "#e06b74", "#8fd39a", "#e3b95f",
            "#82aaff", "#c39ee7", "#63d6d2", "#bfbfc9",
        ],
        "bright": [
            "#4a4a5a", "#ff8f96", "#a8e5b2", "#eed79a",
            "#a8c7ff", "#dcb6ff", "#8ce4e0", "#e8e8f0",
        ],
    },
}
CHROME = {
    "glass": {"bg": "#0d0e12", "dim": "#767d8d", "fg": "#d2d6de", "accent": "#7195e8"},
    "graphite": {"bg": "#0c0c10", "dim": "#7a7a86", "fg": "#d7d7dc", "accent": "#a8c7ff"},
}
DEFAULT_THEME = "glass"


def theme_names() -> list[str]:
    return sorted(THEMES)


def rgba_hex(value: str) -> str:
    """'#AABBCC' or '#ABC' → '#aabbcc'. ValueError otherwise."""
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        raise ValueError(f"not a hex color: {value!r}")
    return "#" + s.lower()


def hex_rgba_tuple(value: str, alpha: float = 1.0) -> str:
    """Hex → CSS `rgba(r,g,b,a)` string (for the chrome/transparency)."""
    s = rgba_hex(value)[1:]
    r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {max(0.0, min(1.0, alpha)):g})"


def palette_rgba(values: list[str]) -> list[str]:
    """Validate a hex list — raises ValueError on junk. Lowercase list back."""
    return [rgba_hex(v) for v in values]


def glass_css(theme: str = DEFAULT_THEME, opacity: float = 1.0) -> str:
    """Full stylesheet, chrome alpha = opacity (blur-friendly on wayland)."""
    t = THEMES[theme]
    c = CHROME[theme]
    bg_alpha = hex_rgba_tuple(c["bg"], opacity)
    bg_back = hex_rgba_tuple("#090a0d" if theme == "glass" else "#08080b", opacity)
    stack = hex_rgba_tuple(t["background"], opacity)
    return f"""
window {{
    background: {bg_alpha};
}}
headerbar {{
    background: {bg_alpha};
    color: {c['fg']};
    border-bottom: none;
    box-shadow: none;
}}
headerbar:backdrop {{
    background: {bg_back};
    color: {c['dim']};
}}
headerbar button {{
    background: transparent;
    color: {c['fg']};
    border: none;
    padding: 3px 9px;
    border-radius: 8px;
}}
headerbar button:hover {{
    background: {hex_rgba_tuple(c['bg'], opacity * 1.9)};
}}
headerbar button:checked, headerbar button.suggested-action {{
    background: {hex_rgba_tuple(c['bg'], opacity * 1.9)};
    color: {c['fg']};
}}
notebook > header {{
    background: transparent;
    border: none;
    box-shadow: none;
}}
notebook > header > tabs > tab {{
    background: transparent;
    padding: 3px 5px;
    margin: 2px 1px;
    color: {c['dim']};
    border-radius: 7px;
}}
notebook > header > tabs > tab:hover {{
    background: {hex_rgba_tuple(c['bg'], opacity * 1.6)};
    color: {c['fg']};
}}
notebook > header > tabs > tab:checked {{
    background: {hex_rgba_tuple(c['bg'], opacity * 2.2)};
    color: {c['fg']};
    border-bottom: 2px solid {c['accent']};
}}
notebook > header > tabs > tab button {{
    min-height: 16px;
    min-width: 16px;
    padding: 0;
    margin: 0 0 0 2px;
}}
notebook stack {{
    background: {stack};
}}
terminal {{
    padding: 12px 14px;
}}
.nlt-side {{
    background: {bg_alpha};
    border-top: 1px solid {hex_rgba_tuple(c['bg'], min(1.0, opacity + 0.2))};
}}
.nlt-side-label {{
    color: {c['dim']};
    padding: 4px 14px 0 14px;
    font-size: 88%;
}}
.nlt-side button {{
    background: transparent;
    color: {c['fg']};
    border: none;
}}
scrollbar {{
    background: transparent;
    border: none;
    min-width: 8px;
}}
scrollbar slider {{
    background: {hex_rgba_tuple('#33363f' if theme == 'glass' else '#2a2a36', 0.85)};
    border-radius: 4px;
    min-width: 6px;
}}
scrollbar slider:hover {{
    background: {hex_rgba_tuple('#414551' if theme == 'glass' else '#3d3d4e', 0.95)};
}}
"""


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
