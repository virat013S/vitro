"""Cheats plugin — a '⌨' button that opens the keybindings cheat sheet."""

TEXT = """\
vitro keys

  F1 / Ctrl+Shift+G     nlt sidecar hide/show
  Ctrl+Shift+T / W      new tab / close tab (new tab follows cwd)
  Ctrl+Shift+E / O      split side-by-side / stacked
  Alt+Arrow             move between panes
  Ctrl+PgUp / PgDn      previous / next tab
  Alt+1..9              jump to tab N
  Ctrl+Shift+C / V      copy / paste
  Ctrl+Shift+[ / ]      less / more transparency
  Ctrl+Shift+ +/- / 0   font bigger / smaller / reset

  settings: ~/.config/vitro/settings.json   (vitro settings)
  plugins:  ~/.config/vitro/plugins/*.py    (def register(ctx))
"""


def register(ctx) -> None:
    from gi.repository import Gtk, Pango

    btn = Gtk.Button(label="⌨")
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.get_style_context().add_class("flat")
    btn.set_tooltip_text("keybindings cheat sheet")

    def open_sheet(_btn) -> None:
        win = Gtk.Window(transient_for=ctx.window)
        win.set_title("vitro keys")
        win.set_default_size(460, 380)
        win.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_border_width(12)
        scroll = Gtk.ScrolledWindow()
        label = Gtk.Label(label=TEXT)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        label.override_font(Pango.FontDescription.from_string("Monospace 10"))
        scroll.add(label)
        outer.pack_start(scroll, True, True, 0)
        win.add(outer)
        win.show_all()

    btn.connect("clicked", open_sheet)
    ctx.headerbar.pack_end(btn)
