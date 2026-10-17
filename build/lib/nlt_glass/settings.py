"""vitro settings — CLI flags win, then this file, then defaults.

File lives at ~/.config/vitro/settings.json (honors XDG_CONFIG_HOME).
Deliberately tiny and tolerant: broken JSON never crashes the terminal.
"""
from __future__ import annotations

import json
import os

DEFAULTS = {
    "theme": "glass",            # glass | graphite
    "opacity": 1.0,              # 0.15 – 1.0; 0.8 + compositor blur = frosted
    "font": "",                  # "" → auto-detect (JetBrains/Iosevka…)
    "shell": "",                 # "" → fish if present, else $SHELL/bash
    "dir": "",                   # working dir for the first tab
    "no_nlt": False,             # hide the nlt sidecar
    "plugins": ["clock", "cheats", "theme", "sysinfo"],
    "scrollback": 10000,
}


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "vitro")


def config_path() -> str:
    return os.path.join(config_dir(), "settings.json")


def load() -> dict:
    """Read the file → merged over DEFAULTS. Raises nothing."""
    merged = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            user = json.load(f)
    except FileNotFoundError:
        return merged
    except Exception:
        return merged
    if isinstance(user, dict):
        for key in DEFAULTS:
            if key in user:
                merged[key] = user[key]
    return merged


def save(values: dict) -> bool:
    """Write settings.json from a full dict. Returns success (never raises)."""
    try:
        os.makedirs(config_dir(), exist_ok=True)
        tmp = config_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(values, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, config_path())
        return True
    except Exception:
        return False


def clean(value: dict) -> dict:
    """A file-ready dict: only keys we know, order matching DEFAULTS."""
    return {k: value.get(k, DEFAULTS[k]) for k in DEFAULTS}


def merge_onto(argv_ns, settings: dict) -> dict:
    """CLI flags override the file; empty-string flags mean 'not set'.

    argv_ns: argparse Namespace with attributes font/shell/dir/theme/
    opacity/no_nlt (None or "" = unset).
    """
    def pick(attr: str, fkey: str):
        av = getattr(argv_ns, attr, "")
        if av in ("", None):
            return settings.get(fkey, DEFAULTS[fkey])
        return av

    out = dict(settings)
    out["font"] = pick("font", "font")
    out["shell"] = pick("shell", "shell")
    out["dir"] = pick("dir", "dir")
    out["theme"] = pick("theme", "theme")
    op = getattr(argv_ns, "opacity", None)
    out["opacity"] = op if op not in ("", None) else settings.get("opacity", 1.0)
    out["no_nlt"] = bool(getattr(argv_ns, "no_nlt", False) or settings.get("no_nlt", False))
    if not isinstance(out.get("plugins"), list):
        out["plugins"] = list(DEFAULTS["plugins"])
    return out


def example_text() -> str:
    """Setup block a `vitro settings init` writes into the file."""
    return json.dumps(DEFAULTS, indent=2, sort_keys=True) + "\n"
