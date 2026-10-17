"""vitro tests — pure logic only (no GTK imports, runs on any OS).

The GUI path is exercised by the linux CI smoke job (xvfb + gir1.2-vte).
"""
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from vitro import APP, APP_ID, __version__
from vitro import cli
from vitro.palette import pick_font, rgba_hex
from vitro.spawn import shell_argv, sidecar_argv, uri_to_path, workdir_arg


# -------------------------------------------------------------------- meta

def test_meta():
    assert __version__ == "1.8.0"


def test_fetch_flying_bar(monkeypatch):
    import io
    import shutil

    from vitro import fetch
    monkeypatch.setattr(shutil, "get_terminal_size",
                       lambda: os.terminal_size((120, 24)))
    fake = io.StringIO()
    fake.isatty = lambda: True
    monkeypatch.setattr(fetch.sys, "stdout", fake)
    fetch.intro_bar(True)
    fetch.stream("typed line\n", 0.2, True, 0, line_ms=1, caret=True)
    sweep = fake.getvalue()
    assert "\x1b[2K" in sweep and "█" in sweep      # the intro comet
    assert "▊" in sweep and "\x1b[s" in sweep      # the caret flew ahead
    assert "╱" in sweep                            # slash trail
    fake2 = io.StringIO()
    fake2.isatty = lambda: True
    monkeypatch.setattr(fetch.sys, "stdout", fake2)
    fetch.stream("quiet line\n", 0.2, True, 0, line_ms=1, caret=False)
    assert "▊" not in fake2.getvalue()             # caret knob is honored


def test_cli_command_flag():
    from vitro import cli
    assert cli.parse(["-e", "htop"]).command == ["htop"]
    assert cli.parse(["--command", "echo", "hi"]).command == ["echo", "hi"]
    assert cli.parse(["--dir", "/tmp", "-e", "btop"]).command == ["btop"]
    assert cli.parse([]).command == []
    assert APP == "vitro"
    assert APP_ID.replace("io.github.virat013s.", "") == "vitro"


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
    from vitro.palette import (CHROME, THEMES, glass_css, hex_rgba_tuple,
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
    from vitro.palette import hex_rgba_tuple
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
    from vitro import settings as cfg

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
    (tmp_path / "vitro" / "settings.json").write_text(
        "{ not json at all", encoding="utf-8")
    assert cfg.load() == dict(cfg.DEFAULTS)


def test_settings_merge_precedence():
    from argparse import Namespace

    from vitro import settings as cfg

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
        mod = importlib.import_module(f"vitro.plugins.{name}")
        assert callable(mod.register)


def test_plugin_loader_user_files_and_fails_soft(monkeypatch, capsys, tmp_path):
    from types import SimpleNamespace

    from vitro.bridge import GlassContext, load_plugins

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    plugdir = tmp_path / "vitro" / "plugins"
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

    from vitro.bridge import GlassContext

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


# ------------------------------------------------------------------ ourfetch

def _tiny_png(w: int = 4, h: int = 4) -> bytes:
    import struct
    import zlib

    raw = bytearray()
    for y in range(h):
        raw.append(0)                        # filter byte: none
        for x in range(w):
            raw += bytes((x * 60 % 256, y * 60 % 256, 128))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body +
                struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)   # RGB, 8-bit
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))


def test_fetch_png_decode_and_ansi(tmp_path):
    from vitro import fetch
    w, h, px = fetch._png_decode(_tiny_png(4, 4))
    assert (w, h) == (4, 4) and len(px) == 16
    assert px[0][3] == 255 and 0 <= px[0][0] <= 255
    p = tmp_path / "t.png"
    p.write_bytes(_tiny_png(6, 6))
    art = fetch.image_to_ansi(str(p), 8)
    assert len(art) >= 3 and all("38;2" in line for line in art)


def test_fetch_logo_and_compose():
    from vitro import fetch
    for os_id, want in (("arch", 19), ("cachyos", 22), ("ubuntu", 20),
                        ("nixos", 20), ("macos", 17), ("windows", 16),
                        ("linuxmint", 19), ("void", 18),
                        ("definitely-not-an-os", 7)):
        art = fetch.logo_for(os_id)
        assert len(art) == want and all("\x1b[" in line for line in art)
    for key in fetch.LOGOS:                 # every logo renders colored
        assert all("\x1b[" in ln and ln.strip() for ln in fetch.logo_for(key)), key
    assert fetch.brand_color("cachyos") == (76, 195, 189)
    assert fetch.brand_color("opensuse-tumbleweed") == (0, 205, 0)
    assert fetch.brand_color("macos") == (229, 229, 229)
    info = fetch.info_lines([("os", "Test OS"), ("kernel", "6.9")], True,
                            (76, 195, 189))
    assert len(info) == 2 and "Test OS" in info[0]
    line = fetch.compose(art, info, fetch.colors_line(True), True)
    assert line.count("\x1b[0m") >= 2 and line.endswith("\x1b[0m\n")


def test_fetch_os_id_fallback(monkeypatch):
    from vitro import fetch
    monkeypatch.setattr(fetch, "_os_release", lambda: {})
    monkeypatch.setattr(fetch.platform, "system", lambda: "Darwin")
    assert fetch.os_id() == "macos"
    monkeypatch.setattr(fetch.platform, "system", lambda: "Windows")
    assert fetch.os_id() == "windows"
    assert fetch.logo_for("windows")                # both have real art


def test_fetch_gather_shape():
    from vitro import fetch
    rows = fetch.gather()
    assert rows and all(isinstance(r, tuple) and len(r) == 2 for r in rows)
    labels = [r[0] for r in rows]
    assert "os" in labels and "term" in labels


def test_fetch_config_roundtrip(monkeypatch, tmp_path):
    from vitro import fetch

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = fetch.load_config()
    assert cfg == dict(fetch.DEFAULTS)
    cfg["cols"] = 44
    assert fetch.save_config(cfg)
    assert fetch.load_config()["cols"] == 44
    assert fetch.image_path() is None


def test_fetch_set_image_command(monkeypatch, tmp_path):
    from vitro import fetch

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    src = tmp_path / "logo.png"
    src.write_bytes(_tiny_png(6, 6))
    assert fetch.main(["set-image", str(src)]) == 0
    assert fetch.load_config()["image"].endswith("image.png")
    assert fetch.image_path() is not None and fetch.image_path().exists()
    art = fetch.image_to_ansi(str(fetch.image_path()), 10)
    assert len(art) >= 3
    # junk path → error code 1
    assert fetch.main(["set-image", str(tmp_path / "nope.png")]) == 1
    # clear back
    assert fetch.main(["clear-image"]) == 0
    assert fetch.image_path() is None


def test_fetch_stream_off_tty_is_instant(capsys):
    from vitro import fetch
    rc = fetch.main(["--no-anim"])
    out = capsys.readouterr().out
    assert rc == 0 and "os" in out and "\x1b[38;2;" in out


def test_gui_module_is_import_safe():
    """glass.py must import everywhere (READY may be False off-linux)."""
    from vitro import glass
    assert glass.READY in (True, False)
    if not glass.READY:
        assert glass.LOAD_ERROR is not None
