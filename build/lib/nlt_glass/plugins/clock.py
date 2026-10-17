"""Clock plugin — quiet HH:MM tick in the header status strip."""

INTERVAL = 30


def register(ctx) -> None:
    from gi.repository import GLib

    def tick() -> bool:
        try:
            ctx.status("clock", GLib.DateTime.new_now_local().format("%H:%M") or "")
        except Exception:
            ctx.status("clock", "")
        return True

    tick()
    GLib.timeout_add_seconds(INTERVAL, tick)
