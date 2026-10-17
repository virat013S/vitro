"""Spawn decisions — pure, testable shell logic (no GTK imports)."""
from __future__ import annotations

import os
import shutil


def shell_argv(shell: str = "") -> list[str]:
    """The shell every tab runs. fish is first-class (--login pulls your
    fish integration, nlt's ctrl-g included); other shells still work."""
    if shell:
        found = shutil.which(shell)
        if not found:
            raise FileNotFoundError(f"shell not found: {shell!r}")
        argv = [found]
        if os.path.basename(found) == "fish":
            argv.append("--login")
        return argv
    fish = shutil.which("fish")
    if fish:
        return [fish, "--login"]
    env = os.environ.get("SHELL", "")
    found = shutil.which(env) if env else None
    if found:
        return [found]
    for cand in ("bash", "sh", "pwsh", "powershell", "cmd"):
        found = shutil.which(cand)
        if found:
            return [found]
    raise FileNotFoundError("no shell found at all — even sh is missing")


def sidecar_argv() -> list[str] | None:
    """`nlt chat` for the sidecar, or None when nlt isn't installed."""
    bin_ = shutil.which("nlt")
    return [bin_, "chat"] if bin_ else None


def workdir_arg(dir_arg: str) -> str:
    """Normalize --dir: expand ~/ , keep real dirs, else fall back to $HOME."""
    d = os.path.expanduser(dir_arg or "")
    if d and os.path.isdir(d):
        return d
    return os.path.expanduser("~")
