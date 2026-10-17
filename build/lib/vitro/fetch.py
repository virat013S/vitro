"""ourfetch — the fetch built into vitro.

System info next to the OS logo (or an image you set), typed out fast like
someone showing off. vitro runs it in the first tab of every fresh window;
it also works as a plain CLI anywhere:

    ourfetch                  run it (typewriter animation on a tty)
    ourfetch --no-anim        instant — for scripts
    ourfetch --cols 44        wider logo
    ourfetch set-image X.png  remember an image as the logo
    ourfetch clear-image      back to the automatic OS logo
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

ACCENT = (134, 174, 246)
DIM = (118, 125, 141)
FG = (210, 214, 222)
BG = (19, 19, 23)                      # vitro glass background — images blend in
BLOCKS = [(220, 111, 120), (141, 207, 157), (226, 196, 130),
          (131, 170, 240), (196, 156, 240), (123, 212, 210),
          (168, 199, 255), (233, 237, 246)]

DEFAULTS = {"image": "", "cols": 36, "anim": True, "speed": 2.0,
            "line_delay": 12}

# Logos straight from fastfetch's collection (tokens $1/$2/$3 → brand colors).
LOGOS = {
    "arch": [
        r"                  -`",
        r"                 .o+`",
        r"                `ooo/",
        r"               `+oooo:",
        r"              `+oooooo:",
        r"              -+oooooo+:",
        r"            `/:-:++oooo+:",
        r"           `/++++/+++++++:",
        r"          `/++++++++++++++:",
        r"         `/+++o$2oooooooo$1oooo/`",
        r"        ./$2ooosssso++osssssso$1+`",
        r"$2       .oossssso-````/ossssss+`",
        r"      -osssssso.      :ssssssso.",
        r"     :osssssss/        osssso+++.",
        r"    /ossssssss/        +ssssooo/-",
        r"  `/ossssso+/:-        -:/+osssso+-",
        r" `+sso+:-`                 `.-/+oso:",
        r"`++:.                           `-/+/",
        r".`                                 `/",
    ],
    "cachyos": [
        r"           $3.$1-------------------------:",
        r"          .$2+=$1========================.",
        r"         :$2++$1===$2++===$1===============-       :$2++$1-",
        r"        :$2*++$1====$2+++++==$1===========-        .==:",
        r"       -$2*+++$1=====$2+***++=$1=========:",
        r"      =$2*++++=$1=======------------:",
        r"     =$2*+++++=$1====-                     $3...$1",
        r"   .$2+*+++++$1=-===:                    .$2=+++=$1:",
        r"  :$2++++$1=====-==:                     -***$2**$1+",
        r" :$2++=$1=======-=.                      .=+**+$3.$1",
        r".$2+$1==========-.                          $3.$1",
        r" :$2+++++++$1====-                                $3.$1--==-$3.$1",
        r"  :$2++$1==========.                             $3:$2+++++++$1$3:",
        r"   $1.-===========.                            =*****+*+",
        r"    $1.-===========:                           .+*****+:",
        r"      $1-=======$2++++$1:::::::::::::::::::::::::-:  $3.$1---:",
        r"       :======$2++++$1====$2+++******************=.",
        r"        $1:=====$2+++$1==========$2++++++++++++++*-",
        r"         $1.====$2++$1==============$2++++++++++*-",
        r"          $1.===$2+$1==================$2+++++++:",
        r"           $1.-=======================$2+++:",
        r"             $3..........................",
    ],
    "generic": [
        "     ▄▄▀▀▄     ",
        "   ▄█▀▀  ▀▀█▄  ",
        "  ▄█▀      ▀█▄ ",
        " ▐█▌  ▄▄▄▄  ▐█▌",
        "  ▀█▄▄▀▀▀▄▄█▀  ",
        "   ▀█▄▄  ▄▄█▀  ",
        "     ▀▀▄▄▀▀    ",
    ],
}

# $1 = body, $2 = detail/outline, $3 = pale highlight (per distro brand).
TOKEN_COLORS = {
    "arch": {"1": (36, 145, 210), "2": (137, 201, 242), "3": (150, 165, 200)},
    "cachyos": {"1": (76, 195, 189), "2": (150, 224, 217), "3": (219, 244, 242)},
}


# ------------------------------------------------------------------ config
def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "vitro")


def config_path() -> str:
    return os.path.join(config_dir(), "fetch.json")


def load_config() -> dict:
    merged = dict(DEFAULTS)
    try:
        with open(config_path(), encoding="utf-8") as f:
            user = json.load(f)
    except Exception:
        return merged
    if isinstance(user, dict):
        for key in DEFAULTS:
            if key in user:
                merged[key] = user[key]
    return merged


def save_config(values: dict) -> bool:
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


def image_path() -> Path | None:
    """The remembered logo image, or None (→ automatic OS logo)."""
    cfg = load_config()
    raw = str(cfg.get("image") or "").strip()
    if not raw:
        return None
    p = Path(os.path.expanduser(raw))
    return p if p.is_file() and p.stat().st_size > 0 else None


# ------------------------------------------------------------------ info bits
def _os_release() -> dict:
    out: dict[str, str] = {}
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"')
    except Exception:
        pass
    return out


def os_id() -> str:
    return _os_release().get("ID", "").lower()


def sys_name() -> str:
    rel = _os_release()
    if rel.get("PRETTY_NAME"):
        return rel["PRETTY_NAME"]
    try:
        return f"macOS {platform.mac_ver()[0]}" if sys.platform == "darwin" \
            else platform.system()
    except Exception:
        return platform.system() or "?"


def kernel() -> str:
    try:
        return platform.release()
    except Exception:
        return ""


def machine() -> str:
    try:
        return platform.machine()
    except Exception:
        return ""


def user_host() -> str:
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    host = os.uname().nodename if hasattr(os, "uname") else ""
    return f"{user}@{host}".strip("@")


def shell_name() -> str:
    s = os.environ.get("SHELL") or ""
    return s.rsplit("/", 1)[-1] if s else ""


def desktop() -> str:
    for var in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION"):
        v = os.environ.get(var)
        if v:
            return v.split(":")[0].strip() or v
    return "tty" if not os.environ.get("WAYLAND_DISPLAY") else "wayland"


def terminal_name() -> str:
    tp = os.environ.get("TERM_PROGRAM")
    if tp:
        return tp
    t = os.environ.get("TERM") or ""
    return "vt" if t in ("", "dumb") else t


def cpu() -> str:
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("model name") and ":" in line:
                        return line.split(":", 1)[1].strip()
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                 capture_output=True, text=True, timeout=3)
            return out.stdout.strip()
    except Exception:
        pass
    return ""


def mem_str() -> str:
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k] = int(v.strip().split()[0])   # kB
        total, avail = info.get("MemTotal"), info.get("MemAvailable")
        if total and avail is not None:
            used = total - avail
            return f"{used / 2 ** 20:.1f} / {total / 2 ** 20:.1f} GiB"
    except Exception:
        pass
    return ""


def disk_str() -> str:
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_bsize
        free = st.f_bavail * st.f_bsize
        used = total - free
        pct = (used / total * 100) if total else 0
        return f"{used / 2 ** 30:.0f} / {total / 2 ** 30:.0f} GiB ({pct:.0f}%)"
    except Exception:
        return ""


def uptime_str() -> str:
    secs = 0.0
    try:
        if os.path.exists("/proc/uptime"):
            with open("/proc/uptime", encoding="ascii") as f:
                secs = float(f.read().split()[0])
        else:
            return ""
    except Exception:
        return ""
    d, r = divmod(int(secs), 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or d:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def packages() -> str:
    if shutil.which("pacman"):
        try:
            out = subprocess.run(["pacman", "-Q"], capture_output=True,
                                 text=True, timeout=5)
            return f"{len(out.stdout.splitlines())} (pacman)"
        except Exception:
            pass
    return ""


def gather() -> list[tuple[str, str]]:
    """Ordered (label, value) rows; empty values dropped by compose()."""
    rows: list[tuple[str, str]] = []
    if user_host():
        rows.append(("user", user_host()))
    rows.append(("os", sys_name()))
    k = " ".join(x for x in (kernel(), machine()) if x)
    if k:
        rows.append(("kernel", k))
    if shell_name():
        rows.append(("shell", shell_name()))
    rows.append(("wm", desktop()))
    rows.append(("term", terminal_name()))
    c = cpu()
    if c:
        rows.append(("cpu", c))
    m = mem_str()
    if m:
        rows.append(("mem", m))
    d = disk_str()
    if d:
        rows.append(("disk", d))
    u = uptime_str()
    if u:
        rows.append(("uptime", u))
    p = packages()
    if p:
        rows.append(("packages", p))
    return rows


# ----------------------------------------------------------------- png decode
def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _png_decode(data: bytes) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Minimal PNG: 8-bit, RGB/RGBA/gray/gray+alpha/palette, no interlace."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, w, h, depth, ctype, plte, trns, idat = 8, 0, 0, 8, 6, b"", b"", []
    while pos + 8 <= len(data):
        (size,), tag = struct.unpack(">I", data[pos:pos + 4]), data[pos + 4:pos + 8]
        body, pos = data[pos + 8:pos + 8 + size], pos + 8 + size + 4
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
        elif tag == b"PLTE":
            plte = body
        elif tag == b"tRNS":
            trns = body
        elif tag == b"IDAT":
            idat.append(body)
        elif tag == b"IEND":
            break
    if not w or not h:
        raise ValueError("no IHDR")
    if depth != 8:
        raise ValueError(f"bit depth {depth} unsupported (need 8)")
    if ctype == 0:
        bpp = 1
    elif ctype == 2:
        bpp = 3
    elif ctype == 3:
        bpp = 1
    elif ctype == 4:
        bpp = 2
    elif ctype == 6:
        bpp = 4
    else:
        raise ValueError(f"color type {ctype} unsupported")
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    if len(raw) < h * (stride + 1):
        raise ValueError("truncated PNG data")
    rows = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, prev[i], c)) & 0xFF
        rows[y * stride:(y + 1) * stride] = line
        prev = line

    px: list[tuple[int, int, int, int]] = []
    for i in range(w * h):
        if ctype == 0:
            v = rows[i]
            px.append((v, v, v, 255))
        elif ctype == 2:
            px.append((rows[i * 3], rows[i * 3 + 1], rows[i * 3 + 2], 255))
        elif ctype == 3:
            idx = rows[i]
            r = plte[idx * 3] if idx * 3 + 2 < len(plte) else 0
            g = plte[idx * 3 + 1] if idx * 3 + 2 < len(plte) else 0
            b = plte[idx * 3 + 2] if idx * 3 + 2 < len(plte) else 0
            a = trns[idx] if idx < len(trns) else 255
            px.append((r, g, b, a))
        elif ctype == 4:
            v, a = rows[i * 2], rows[i * 2 + 1]
            px.append((v, v, v, a))
        else:
            px.append((rows[i * 4], rows[i * 4 + 1], rows[i * 4 + 2],
                       rows[i * 4 + 3]))
    return w, h, px


def _load_rgba(path: str) -> tuple[int, int, list]:
    p = Path(os.path.expanduser(path))
    data = p.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return _png_decode(data)
    try:
        from PIL import Image
        im = Image.open(p).convert("RGBA")
        return im.width, im.height, list(im.getdata())
    except Exception:
        raise ValueError("only PNG works without Pillow (pip install pillow "
                         "for jpg/webp)")


def _blend(c: tuple, bg: tuple, a: int) -> tuple:
    t = a / 255.0
    return tuple(int(c[i] * t + bg[i] * (1 - t)) for i in range(3))


def image_to_ansi(path: str, cols: int = 36,
                  bg: tuple = BG) -> list[str]:
    """Image → upper-half-block truecolor lines (2 pixels per row)."""
    cols = max(8, min(80, int(cols)))
    w, h, px = _load_rgba(path)
    comp = [_blend(px[i], bg, px[i][3]) for i in range(w * h)]

    def sample(x0: int, x1: int, y0: int, y1: int) -> tuple:
        xs, ys = max(0, x0), max(0, y0)
        xe, ye = min(w, max(x1, xs + 1)), min(h, max(y1, ys + 1))
        n = 0
        acc = [0, 0, 0]
        for y in range(ys, ye):
            for x in range(xs, xe):
                c = comp[y * w + x]
                acc[0] += c[0]
                acc[1] += c[1]
                acc[2] += c[2]
                n += 1
        return (acc[0] // n, acc[1] // n, acc[2] // n) if n else bg

    rows_n = max(1, round(h * (cols / w) / 2))
    art: list[str] = []
    for r in range(rows_n):
        y0, y1 = round(r * h / rows_n), round((r + 1) * h / rows_n)
        ym = (y0 + y1) // 2
        line = []
        for c_i in range(cols):
            x0, x1 = round(c_i * w / cols), round((c_i + 1) * w / cols)
            top = sample(x0, x1, y0, ym)
            bot = sample(x0, x1, ym, y1)
            line.append(f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m"
                        f"\x1b[48;2;{bot[0]};{bot[1]};{bot[2]}m▀")
        art.append("".join(line) + "\x1b[0m")
    return art


# ---------------------------------------------------------------------- logo
TOKEN_RE = re.compile(r"\$(\d)")


def _token_colored(lines: list[str], colors: dict) -> list[str]:
    """fastfetch token lines ($1/$2/$3) → truecolor lines."""
    out = []
    for raw in lines:
        buf: list[str] = []
        cur = colors.get("1") or FG
        last: tuple | None = None
        segs = TOKEN_RE.split(raw)
        for j, seg in enumerate(segs):
            if j % 2 == 1:                 # capture: the token number
                cur = colors.get(seg) or colors.get("1") or FG
                continue
            if not seg:
                continue
            if cur != last:
                buf.append(f"\x1b[38;2;{cur[0]};{cur[1]};{cur[2]}m")
                last = cur
            buf.append(seg)
        buf.append("\x1b[0m")
        out.append("".join(buf))
    return out


def brand_color(os_id: str) -> tuple:
    """Body color of the logo — labels dress in it too."""
    return TOKEN_COLORS.get(os_id, {}).get("1", ACCENT)


def logo_for(os_id: str) -> list[str]:
    """The fastfetch logo for the running OS; vitro's shard for unknowns."""
    raw = LOGOS.get(os_id) or LOGOS["generic"]
    if any("$" in line for line in raw):
        return _token_colored(raw, TOKEN_COLORS.get(os_id)
                              or TOKEN_COLORS["arch"])
    out = []
    n = len(raw)
    base = (150, 165, 200) if os_id not in LOGOS else ACCENT
    for i, line in enumerate(raw):
        t = i / max(1, n - 1)          # fade logo base → foreground
        col = tuple(int(base[k] + (FG[k] - base[k]) * t) for k in range(3))
        out.append(f"\x1b[38;2;{col[0]};{col[1]};{col[2]}m{line}\x1b[0m")
    return out


# ------------------------------------------------------------------- compose
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def visible_len(s: str) -> int:
    return len(ANSI_RE.sub("", s))


def info_lines(rows: list[tuple[str, str]], color: bool = True,
               brand: tuple = ACCENT) -> list[str]:
    out = []
    width = max((len(label) for label, _ in rows), default=6)
    for label, value in rows:
        if not value:
            continue
        if color:
            out.append(f"\x1b[1m\x1b[38;2;{brand[0]};{brand[1]};{brand[2]}m"
                       f"{label.rjust(width)}\x1b[0m"
                       f"\x1b[38;2;{DIM[0]};{DIM[1]};{DIM[2]}m · \x1b[0m"
                       f"\x1b[38;2;{FG[0]};{FG[1]};{FG[2]}m{value}\x1b[0m")
        else:
            out.append(f"{label.rjust(width)} · {value}")
    return out


def colors_line(color: bool = True) -> str:
    if not color:
        return ""
    return "".join(f"\x1b[38;2;{c[0]};{c[1]};{c[2]}m███\x1b[0m"
                   for c in BLOCKS)


def compose(art: list[str], info: list[str], colors: str,
            color: bool = True) -> str:
    aw = max((visible_len(line) for line in art), default=0) + 3
    rows = max(len(art), len(info) + (2 if colors else 0))
    out = []
    for i in range(rows):
        line = art[i] if i < len(art) else ""
        pad = " " * (aw - visible_len(line)) if line else " " * aw
        text = ""
        if i < len(info):
            text = info[i]
        elif colors and i == len(info):
            text = colors
        out.append(f"{line}{pad}{text}\x1b[0m")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------- typing effect
def stream(text: str, speed_ms: float = 2.0, color: bool = True,
           art_rows: int = 0, line_ms: float = 12.0) -> None:
    """The animation: the logo builds row by row, the info types itself.
    Escape runs jump instantly; visible chars tick at speed_ms."""
    lines = text.split("\n")
    if not color or not sys.stdout.isatty() or speed_ms <= 0:
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    delay = max(0.2, speed_ms) / 1000.0
    line_wait = max(0.5, line_ms) / 1000.0
    try:
        for i, line in enumerate(lines):
            if i < art_rows:
                sys.stdout.write(line + ("\n" if i < len(lines) - 1 else ""))
                sys.stdout.flush()
                time.sleep(line_wait)
            else:
                for part in ANSI_RE.split(line):
                    if not part:
                        continue
                    if part.startswith("\x1b"):
                        sys.stdout.write(part)
                    else:
                        for ch in part:
                            sys.stdout.write(ch)
                            sys.stdout.flush()
                            time.sleep(delay)
                if i < len(lines) - 1:
                    sys.stdout.write("\n")
                sys.stdout.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        pass


# --------------------------------------------------------------------- faces
def set_image(rest: list[str]) -> int:
    args = [a for a in rest if not a.startswith("-")]
    if not args:
        print("usage: ourfetch set-image <image.png>")
        return 1
    src = Path(os.path.expanduser(args[0]))
    if not src.is_file():
        print(f"ourfetch: no such file: {src}")
        return 1
    os.makedirs(config_dir(), exist_ok=True)
    dest = Path(config_dir()) / "image.png"
    try:
        if src.suffix.lower() == ".png":
            shutil.copyfile(src, dest)
        else:
            from PIL import Image
            Image.open(src).convert("RGBA").save(dest)
    except Exception as err:
        print(f"ourfetch: couldn't use {src.name} — {err}")
        return 1
    cfg = load_config()
    cfg["image"] = str(dest)
    save_config(cfg)
    print(f"ourfetch: logo set → {dest}  (clear-image undoes)")
    return 0


def main(argv: list[str] | None = None) -> int:
    flat = list(sys.argv[1:] if argv is None else argv)
    if flat and flat[0] == "set-image":
        return set_image(flat[1:])
    if flat and flat[0] == "clear-image":
        cfg = load_config()
        cfg["image"] = ""
        save_config(cfg)
        print("ourfetch: image cleared — automatic OS logo from now on")
        return 0

    p = argparse.ArgumentParser(
        prog="ourfetch", description="vitro's fetch — info + logo, typed fast")
    p.add_argument("--no-anim", action="store_true", help="print instantly")
    p.add_argument("--cols", type=int, help="logo width in characters")
    p.add_argument("--speed", type=float, help="typing ms per char (default 2)")
    args = p.parse_args(flat)

    cfg = load_config()
    cols = int(args.cols or cfg.get("cols") or 36)
    speed = float(args.speed if args.speed is not None else cfg.get("speed", 2.0))
    animate = bool(cfg.get("anim", True)) and not args.no_anim
    color = not bool(os.environ.get("NO_COLOR"))

    art: list[str] | None = None
    img = image_path()
    if img:
        try:
            art = image_to_ansi(str(img), cols, BG)
        except Exception as err:
            print(f"ourfetch: image failed ({err}) — OS logo instead",
                  file=sys.stderr)
            art = None
    if art is None:
        art = logo_for(os_id())

    rows = gather()
    text = compose(art, info_lines(rows, color, brand_color(os_id())),
                   colors_line(color), color)
    if animate:
        stream(text, speed, color, art_rows=len(art),
               line_ms=float(cfg.get("line_delay", 12)))
    else:
        sys.stdout.write(text)
        sys.stdout.flush()
    return 0
