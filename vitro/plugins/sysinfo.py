"""Sysinfo plugin — one-minute load average (λ) in the status strip.

Linux only (/proc/loadavg); silently inert everywhere else.
"""

INTERVAL = 5
BADGE = "λ"


def register(ctx) -> None:
    import os

    from gi.repository import GLib

    if not os.path.exists("/proc/loadavg"):
        return

    def tick() -> bool:
        try:
            with open("/proc/loadavg", encoding="ascii") as f:
                first = (f.read().split() or [""])[0]
            ctx.status("sysinfo", f"{BADGE} {first}")
        except Exception:
            ctx.status("sysinfo", "")
        return True

    tick()
    GLib.timeout_add_seconds(INTERVAL, tick)
