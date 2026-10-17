"""Theme plugin — one click cycles glass ⇄ graphite and remembers it."""

ORDER = ("glass", "graphite")


def register(ctx) -> None:
    from gi.repository import Gtk

    from .. import settings
    from ..palette import THEMES

    icon = Gtk.Label(label="◐")
    box = Gtk.Box(spacing=4)
    box.pack_start(icon, False, False, 0)
    btn = Gtk.Button()
    btn.add(box)
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.get_style_context().add_class("flat")
    btn.set_tooltip_text("cycle theme (glass ⇄ graphite) — saved to settings")

    def cycle(_widget=None) -> None:
        current = ctx.state.get("theme", ctx.settings.get("theme", ORDER[0]))
        order = [t for t in ORDER if t in THEMES] or list(ORDER)
        if current not in order:
            current = order[0]
        nxt = order[(order.index(current) + 1) % len(order)]
        ctx.retheme(nxt)
        ctx.settings["theme"] = nxt
        settings.save(settings.clean(ctx.settings))

    btn.connect("clicked", cycle)
    ctx.headerbar.pack_end(btn)
