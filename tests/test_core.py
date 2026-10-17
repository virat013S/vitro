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
from nlt_glass.palette import GLASS, GLASS_CSS, pick_font, rgba_hex
from nlt_glass.spawn import shell_argv, sidecar_argv, workdir_arg


# -------------------------------------------------------------------- meta

def test_meta():
    assert __version__ == "1.0.0"
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


# ------------------------------------------------------------------ palette

def test_glass_palette_complete():
    assert len(GLASS["normal"]) == 8
    assert len(GLASS["bright"]) == 8
    assert GLASS["normal"] == [rgba_hex(v) for v in GLASS["normal"]]
    assert GLASS["bright"] == [rgba_hex(v) for v in GLASS["bright"]]


def test_rgba_hex():
    assert rgba_hex("#ABC") == "#aabbcc"
    assert rgba_hex("#A1B2C3") == "#a1b2c3"
    with pytest.raises(ValueError):
        rgba_hex("nope")
    with pytest.raises(ValueError):
        rgba_hex("#GGHHII")


def test_css_carries_the_look():
    assert "padding: 12px 14px;" in GLASS_CSS
    assert GLASS["background"] in GLASS_CSS  # window + stack backgrounds


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


def test_workdir_arg():
    import tempfile
    home = os.path.expanduser("~")
    real = tempfile.gettempdir()
    assert workdir_arg("") == home
    assert workdir_arg(real) == real
    assert workdir_arg("/definitely/not/here") == home


def test_gui_module_is_import_safe():
    """glass.py must import everywhere (READY may be False off-linux)."""
    from nlt_glass import glass
    assert glass.READY in (True, False)
    if not glass.READY:
        assert glass.LOAD_ERROR is not None
