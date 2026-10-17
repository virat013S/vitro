"""Spawn decisions — pure, testable shell logic (no GTK imports)."""
from __future__ import annotations

import os
import shutil


def in_flatpak() -> bool:
    """True when vitro itself runs inside a flatpak sandbox."""
    return os.path.exists("/.flatpak-info") or bool(os.environ.get("FLATPAK_ID"))


_host_shell: list[str] | None = None


def host_shell_argv() -> list[str] | None:
    """Inside a flatpak: your real host shell, via flatpak-spawn (cached).

    The sandbox only carries the runtime's bash, so fish-first means spawning
    the shell on the host — your fish config, PATH and integration load as
    usual. Single cached probe (getent for $SHELL, which fish) keeps it
    sub-second once.
    """
    global _host_shell
    if _host_shell is not None:
        return _host_shell
    _host_shell = []
    if not in_flatpak():
        return _host_shell
    import subprocess

    def probe(argv: list[str]) -> str:
        try:
            r = subprocess.run(argv, capture_output=True, timeout=8, text=True)
            return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout else ""
        except Exception:
            return ""

    # the user's real login shell on the host
    login = probe(["flatpak-spawn", "--host", "getent", "passwd", str(os.getuid())])
    if login and ":" in login:
        argv0 = login.rstrip("\n").split(":")[-1]
        if argv0:
            _host_shell = (["flatpak-spawn", "--host", argv0]
                           + (["--login"] if os.path.basename(argv0) == "fish" else []))
    # fish-first: if the host has fish and it's not already the login shell,
    # still run fish (its --login integration is what nlt's ctrl-g needs)
    fish = probe(["flatpak-spawn", "--host", "which", "fish"])
    if fish and (_host_shell == [] or "fish" not in _host_shell[-1]):
        _host_shell = ["flatpak-spawn", "--host", fish, "--login"]
    return _host_shell


def shell_argv(shell: str = "") -> list[str]:
    """The shell every tab runs. fish is first-class (--login pulls your
    fish integration, nlt's ctrl-g included); other shells still work.
    Inside a flatpak the tab runs your real host shell via flatpak-spawn."""
    if shell:
        found = shutil.which(shell)
        if not found:
            raise FileNotFoundError(f"shell not found: {shell!r}")
        argv = [found]
        if os.path.basename(found) == "fish":
            argv.append("--login")
        return argv
    argv = host_shell_argv()
    if argv:
        return list(argv)
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
    if bin_:
        return [bin_, "chat"]
    if in_flatpak():
        # host nlt via the sandbox portal (cached probe)
        import subprocess

        try:
            r = subprocess.run(["flatpak-spawn", "--host", "which", "nlt"],
                               capture_output=True, timeout=8, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return ["flatpak-spawn", "--host", "nlt", "chat"]
        except Exception:
            pass
    return None


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
