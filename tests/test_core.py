"""nlt-glass tests — pure logic only (no GTK imports, runs on any OS).

The GUI path is exercised by the linux CI smoke job (xvfb + gir1.2-vte).
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from nlt_glass import APP, APP_ID, __version__
from nlt_glass import cli
from nlt_glass.palette import pick_font, rgba_hex
from nlt_glass.spawn import shell_argv, sidecar_argv, uri_to_path, workdir_arg


# -------------------------------------------------------------------- meta

def test_meta():
    assert __version__ == "1.2.0"
    assert APP == "nlt-glass"
    assert APP_ID.replace("io.github.virat013s.", "") == "nlt_glass"


def test_parse_defaults():
    args = cli.parse([])
    assert args.font == "" and args.shell == "" and args.dir == ""
    assert args.no_nlt is False


def test_parse_options():
    a = cli.parse(["--font", "DejaVu Sans Mono 12", "--shell", "zsh",
                   "--dir", "~/x", "--no-nlt"])
    assert a.font == "DejaVu Sans Mono 12"
    assert a.shell == "zsh"
    assert a.no_nlt is True


def test_parse_opacity_and_theme():
    a = cli.parse(["--opacity", "0.7", "--theme", "graphite"])
    assert a.opacity == pytest.approx(0.7)
    assert a.theme == "graphite"
    b = cli.parse([])
    assert b.opacity is None       # unset → settings.json wins
    assert b.theme is None
    with pytest.raises(SystemExit):
        cli.parse(["--theme", "nope"])


# ------------------------------------------------------------------ palette

def test_themes_complete():
    from nlt_glass.palette import (CHROME, THEMES, glass_css, hex_rgba_tuple,
                                   theme_names)
    assert theme_names() == ["glass", "graphite"]
    for name in theme_names():
        pal = THEMES[name]
        assert len(pal["normal"]) == 8 and len(pal["bright"]) == 8
        assert pal["normal"] == [rgba_hex(v) for v in pal["normal"]]
        assert pal["bright"] == [rgba_hex(v) for v in pal["bright"]]
        assert name in CHROME
    for theme in theme_names():
        css = glass_css(theme, 1.0)
        chrome_bg = CHROME[theme]["bg"]
        assert hex_rgba_tuple(chrome_bg, 1.0) in css
    css70 = glass_css("glass", 0.7)
    assert hex_rgba_tuple(CHROME["glass"]["bg"], 0.7) in css70
    with pytest.raises(KeyError):
        glass_css("nope")  # type: ignore[arg-type]


def test_hex_to_rgba_tuple():
    from nlt_glass.palette import hex_rgba_tuple
    assert hex_rgba_tuple("#12141C", 1.0) == "rgba(18, 20, 28, 1)"
    assert hex_rgba_tuple("#12141c", 0.7) == "rgba(18, 20, 28, 0.7)"
    assert hex_rgba_tuple("#abc", 0) == "rgba(170, 187, 204, 0)"


def test_rgba_hex():
    assert rgba_hex("#ABC") == "#aabbcc"
    assert rgba_hex("#A1B2C3") == "#a1b2c3"
    with pytest.raises(ValueError):
        rgba_hex("nope")
    with pytest.raises(ValueError):
        rgba_hex("#GGHHII")


def test_pick_font_fallback(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _x: None)
    assert pick_font() == "Monospace 11"


def test_pick_font_detects_nice_fonts(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _x: "/usr/bin/fc-list")
    fake = subprocess.CompletedProcess([], 0, stdout="JetBrains Mono,Iosevka")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    assert pick_font() == "JetBrains Mono 11"


# -------------------------------------------------------------------- spawn

def test_shell_argv_defaults_to_found_shell():
    argv = shell_argv("")
    assert argv and os.path.isabs(argv[0])
    if os.path.basename(argv[0]) == "fish":
        assert "--login" in argv


def test_shell_argv_custom_classic():
    import sys
    assert shell_argv(sys.executable) == [sys.executable]
    sh = shell_argv("bash")  # exists on unix and the windows runner (git-bash)
    if sh:
        assert os.path.isabs(sh[0])


def test_shell_argv_names_fish_as_login():
    fish = shutil.which("fish")
    if fish:
        assert shell_argv("fish") == [fish, "--login"]


def test_shell_argv_missing_shell_raises():
    with pytest.raises(FileNotFoundError):
        shell_argv("/no/such/zsh-xyz")


def test_sidecar_argv_shape():
    argv = sidecar_argv()
    if argv is not None:
        assert argv[1] == "chat"
        assert os.path.isabs(argv[0])


def test_uri_to_path():
    assert uri_to_path("file:///home/mitsuki/Lezy%20OS") == "/home/mitsuki/Lezy OS"
    assert uri_to_path("file://localhost/tmp") == "/tmp"
    assert uri_to_path("http://example.com/x") == ""
    assert uri_to_path("") == ""
    assert uri_to_path(None) == ""


def test_workdir_arg():
    import tempfile
    home = os.path.expanduser("~")
    real = tempfile.gettempdir()
    assert workdir_arg("") == home
    assert workdir_arg(real) == real
    assert workdir_arg("/definitely/not/here") == home


def test_settings_roundtrip(monkeypatch, tmp_path):
    from nlt_glass import settings as cfg

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    s = cfg.load()
    assert s == dict(cfg.DEFAULTS)          # no file → coded defaults
    assert cfg.config_path().endswith("settings.json")

    s["opacity"] = 0.75
    s["plugins"] = ["clock"]
    assert cfg.save(s) is True
    assert cfg.load()["opacity"] == 0.75
    assert cfg.load()["plugins"] == ["clock"]

    # broken file never wins / never wedges
    (tmp_path / "nlt-glass" / "settings.json").write_text(
        "{ not json at all", encoding="utf-8")
    assert cfg.load() == dict(cfg.DEFAULTS)


def test_settings_merge_precedence():
    from argparse import Namespace

    from nlt_glass import settings as cfg

    ns = Namespace(font="", shell="zsh", dir="", theme=None,
                   opacity=None, no_nlt=False)
    merged = cfg.merge_onto(ns, {"font": "Mono 10", "opacity": 0.5,
                                 "theme": "graphite", "no_nlt": True})
    assert merged["font"] == "Mono 10"      # file value, flag unset
    assert merged["shell"] == "zsh"         # flag value wins
    assert merged["opacity"] == 0.5
    assert merged["theme"] == "graphite"
    assert merged["no_nlt"] is True

    ns2 = Namespace(font="", shell="", dir="", theme="glass",
                    opacity=1.0, no_nlt=True)
    merged2 = cfg.merge_onto(ns2, {"theme": "graphite", "opacity": 0.5})
    assert merged2["theme"] == "glass"      # explicit CLI beats file
    assert merged2["opacity"] == 1.0
    assert merged2["no_nlt"] is True        # either source sticks


def test_builtin_plugins_importable():
    import importlib

    for name in ("clock", "cheats", "theme", "sysinfo"):
        mod = importlib.import_module(f"nlt_glass.plugins.{name}")
        assert callable(mod.register)


def test_plugin_loader_user_files_and_fails_soft(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace

    from nlt_glass.bridge import GlassContext, load_plugins

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    plugdir = tmp_path / "nlt-glass" / "plugins"
    plugdir.mkdir(parents=True)
    (plugdir / "marker.py").write_text(
        "def register(ctx):\n"
        "    ctx.state['marker'] = True\n"
        "    ctx.status('t', 'on')\n", encoding="utf-8")
    (plugdir / "bare.py").write_text("X = 1\n", encoding="utf-8")

    ctx = GlassContext(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                       {"subtitle_extra": None}, {}, None)
    live = load_plugins(["marker", "bare", "no_such_plugin_xyz"], ctx)
    assert live == ["marker"]               # bare has no register; unknown skipped
    assert ctx.state["marker"] is True
    err = capsys.readouterr().err
    assert "no register(ctx)" in err
    assert "no_such_plugin_xyz" in err

    # zero-config auto-load: fresh ctx, no names — marker runs again
    ctx2 = GlassContext(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                        {"subtitle_extra": None}, {}, None)
    live2 = load_plugins([], ctx2)
    assert live2 == ["marker"]


def test_context_status_slots():
    from types import SimpleNamespace

    from nlt_glass.bridge import GlassContext

    seen: dict = {}

    def set_text(t: str) -> None:
        seen["t"] = t

    extra = SimpleNamespace(set_text=set_text)
    ctx = GlassContext(SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
                       {"subtitle_extra": extra}, {}, None)
    ctx.status("clock", "13:37")
    assert seen["t"] == "13:37"
    ctx.status("sysinfo", "λ 0.4")
    assert seen["t"] == "13:37  ·  λ 0.4"    # joined, sorted
    ctx.status("clock", "")
    assert seen["t"] == "λ 0.4"


def test_gui_module_is_import_safe():
    """glass.py must import everywhere (READY may be False off-linux)."""
    from nlt_glass import glass
    assert glass.READY in (True, False)
    if not glass.READY:
        assert glass.LOAD_ERROR is not None
