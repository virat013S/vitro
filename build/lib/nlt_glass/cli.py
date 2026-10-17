"""vitro — CLI front. Thin: parsing here, GTK lives behind glass.run()."""
from __future__ import annotations

import argparse
import sys

from . import APP, __version__


def parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=APP,
        description="vitro — the fish-first terminal window around the nlt brain.")
    p.add_argument("--font", default="",
                   help="Pango font, e.g. 'JetBrainsMono Nerd Font 11' (auto-detected by default)")
    p.add_argument("--shell", default="",
                   help="shell to run in tabs (fish by default; falls back to $SHELL/bash)")
    p.add_argument("--dir", default="",
                   help="working directory for the first tab")
    p.add_argument("--opacity", default=None, type=float,
                   help="background transparency, 0.15-1.0 (default: from "
                        "settings or 1.0 — Ctrl+Shift+[ / ] adjusts live)")
    p.add_argument("--theme", default=None, choices=("glass", "graphite"),
                   help="color theme (default: from settings or glass)")
    p.add_argument("--no-nlt", action="store_true",
                   help="hide the nlt sidecar entirely (plain terminal mode)")
    p.add_argument("-V", "--version", action="version",
                   version=f"{APP} {__version__}")
    return p.parse_args(argv or [])


def settings_cmd(rest: list[str] | None) -> int:
    """`vitro settings` — show / init / edit the settings file."""
    import json
    import os
    import subprocess

    from . import settings as cfg

    rest = list(rest or [])
    path = cfg.config_path()
    if rest and rest[0] == "init":
        if os.path.exists(path) and "--force" not in rest:
            print(f"{APP}: {path} already exists — edit it, or use "
                  f"'vitro settings init --force'")
            return 1
        if cfg.save(cfg.clean({})):
            print(f"{APP}: wrote {path}")
            return 0
        print(f"{APP}: could not write {path}", file=sys.stderr)
        return 1
    if rest and rest[0] == "edit":
        if not os.path.exists(path):
            cfg.save(cfg.clean({}))
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if editor:
            return subprocess.call([editor, path]) or 0
        print(f"{APP}: $EDITOR not set — open {path} manually")
        return 1
    current = cfg.clean(cfg.load())
    print(f"settings file: {path} "
          f"({'exists' if os.path.exists(path) else 'defaults below — file absent'})")
    print(json.dumps(current, indent=2, sort_keys=True))
    print("\nedit the file, or run 'vitro settings init --force' / 'vitro settings edit'")
    print("builtin plugins: clock, cheats, theme, sysinfo")
    print("your plugins:    drop files in ~/.config/vitro/plugins/ (def register(ctx))")
    return 0


def main(argv: list[str] | None = None) -> int:
    flat = list(sys.argv[1:] if argv is None else argv)
    if flat and flat[0] == "settings":
        return settings_cmd(flat[1:])
    args = parse(flat)
    from . import glass
    return glass.run(args)


if __name__ == "__main__":
    sys.exit(main())
