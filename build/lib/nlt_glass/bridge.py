"""nlt-glass plugins — tiny, inbuilt, user-extensible.

A plugin is any python module exposing `register(ctx)`. Inbuilt ones live
in nlt_glass/plugins/; user ones in ~/.config/nlt-glass/plugins/*.py
(a user file with the same name as an inbuilt one wins). Names come from
settings["plugins"], plus every user *.py is auto-loaded once. A broken
plugin never crashes the terminal — it's skipped with a stderr note.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys


class GlassContext:
    """What a plugin gets. Small, honest surface."""

    def __init__(self, window, headerbar, nb, state, settings, app) -> None:
        self.window = window          # Gtk.ApplicationWindow
        self.headerbar = headerbar    # Gtk.HeaderBar
        self.notebook = nb            # Gtk.Notebook
        self.state = state            # the glass's live state dict
        self.settings = settings      # merged settings dict (mutable)
        self.app = app                # Gtk.Application
        self._status: dict[str, str] = {}

    def retheme(self, name: str) -> None:
        """Retheme the whole window live — CSS chrome + every vte."""
        from .glass import _apply_css, _paint_terminal
        from .palette import THEMES, glass_css

        if name not in THEMES:
            return
        self.state["theme"] = name
        opacity = float(self.state.get("opacity", 1.0) or 1.0)
        _apply_css(glass_css(name, opacity))
        for tab in self.state.get("tabs", []):
            for pane in tab["panes"]:
                _paint_terminal(pane["term"], name, opacity,
                                self.state.get("scrollback", 10000))

    def status(self, key: str, text: str) -> None:
        """Set one slot of the header status strip ('clock', 'sysinfo', …).
        Empty text clears the slot. Plugins share, nobody stomps."""
        if text:
            self._status[key] = text
        else:
            self._status.pop(key, None)
        extra = self.state.get("subtitle_extra")
        if extra is not None:
            extra.set_text("  ·  ".join(self._status[k]
                                        for k in sorted(self._status)))


def _import_user(path: str):
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        spec = importlib.util.spec_from_file_location(f"glass_user_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception as err:  # noqa: BLE001 — plugins must fail soft
        print(f"nlt-glass plugin '{name}': {err}", file=sys.stderr)
        return None


def _import_builtin(name: str):
    try:
        return importlib.import_module(f"nlt_glass.plugins.{name}")
    except Exception as err:  # noqa: BLE001
        print(f"nlt-glass plugin '{name}': {err}", file=sys.stderr)
        return None


def _register(mod, label: str, ctx: GlassContext, live: list[str]) -> None:
    if mod is None:
        return
    if not hasattr(mod, "register"):
        print(f"nlt-glass plugin '{label}': no register(ctx)", file=sys.stderr)
        return
    try:
        mod.register(ctx)
        live.append(label)
    except Exception as err:  # noqa: BLE001
        print(f"nlt-glass plugin '{label}' blew up: {err}", file=sys.stderr)


def user_plugin_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "nlt-glass", "plugins")


def _user_files() -> list[str]:
    d = user_plugin_dir()
    try:
        return sorted(
            os.path.join(d, f) for f in os.listdir(d) if f.endswith(".py"))
    except OSError:
        return []


def load_plugins(names: list[str], ctx: GlassContext) -> list[str]:
    """Resolve each settings name (user file first, then inbuilt module),
    then auto-load the remaining user *.py files. Returns live names."""
    live: list[str] = []
    loaded_files: set[str] = set()

    for name in names or []:
        user_path = os.path.join(user_plugin_dir(), f"{name}.py")
        if os.path.exists(user_path):
            _register(_import_user(user_path), name, ctx, live)
            loaded_files.add(user_path)
            continue
        _register(_import_builtin(name), name, ctx, live)

    for path in _user_files():      # zero-config extras
        if path in loaded_files:
            continue
        _register(_import_user(path),
                  os.path.splitext(os.path.basename(path))[0], ctx, live)
    return live
