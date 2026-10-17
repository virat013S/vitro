"""nlt-glass — CLI front. Thin: parsing here, GTK lives behind glass.run()."""
from __future__ import annotations

import argparse
import sys

from . import APP, __version__


def parse(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=APP,
        description="nlt-glass — the fish-first terminal window around the nlt brain.")
    p.add_argument("--font", default="",
                   help="Pango font, e.g. 'JetBrainsMono Nerd Font 11' (auto-detected by default)")
    p.add_argument("--shell", default="",
                   help="shell to run in tabs (fish by default; falls back to $SHELL/bash)")
    p.add_argument("--dir", default="",
                   help="working directory for the first tab")
    p.add_argument("--opacity", default="1.0", type=float,
                   help="background transparency, 0.15-1.0 (default: 1.0 — "
                        "Ctrl+Shift+[ / ] adjusts live). Needs a compositor.")
    p.add_argument("--theme", default="glass", choices=("glass", "graphite"),
                   help="color theme (default: glass)")
    p.add_argument("--no-nlt", action="store_true",
                   help="hide the nlt sidecar entirely (plain terminal mode)")
    p.add_argument("-V", "--version", action="version",
                   version=f"{APP} {__version__}")
    return p.parse_args(argv or [])


def main(argv: list[str] | None = None) -> int:
    args = parse(sys.argv[1:] if argv is None else argv)
    from . import glass
    return glass.run(args)


if __name__ == "__main__":
    sys.exit(main())
