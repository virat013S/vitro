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


def env_list(extra: dict | None = None) -> list[str]:
    """Inherited env + vitro markers, shaped for vte spawn's envv."""
    env = {k: v for k, v in os.environ.items() if "=" not in k}
    env["TERM_PROGRAM"] = "Vitro"
    env.setdefault("COLORTERM", "truecolor")
    if extra:
        for k, v in extra.items():
            env[str(k)] = str(v)
    return [f"{k}={v}" for k, v in env.items()]


def fetch_available() -> bool:
    """True when the ourfetch binary is reachable."""
    try:
        return shutil.which("ourfetch") is not None
    except Exception:
        return False


def uri_to_path(uri: str | None) -> str:
    """file:// URI (vte current-directory-uri) → local path. '' when unknown."""
    if not uri or not uri.startswith("file://"):
        return ""
    try:
        from urllib.parse import unquote, urlparse
        parsed = urlparse(uri)
        if parsed.netloc and parsed.netloc not in ("", "localhost"):
            return ""
        return unquote(parsed.path)
    except Exception:
        return ""
