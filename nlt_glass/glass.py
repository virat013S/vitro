"""The glass — a GTK3 + VTE terminal window built around fish + nlt.

Every tab spawns fish (or --shell); the nlt chat sidecar is one keypress
away; your nlt fish integration (ctrl-g rescue) works because fish loads
conf.d as usual. nlt itself is optional — the glass works without it.

Importing this module is safe everywhere: without GTK/VTE bindings it
loads with READY=False and run() prints a friendly pointer instead of a
traceback.
"""
from __future__ import annotations

import re

READY = False
LOAD_ERROR: Exception | None = None

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("Vte", "2.91")
    from gi.repository import Gtk, Vte, Gdk, Gio, GLib, Pango

    READY = True
except (ImportError, ValueError, TypeError) as _e:  # bindings or runtime missing
    LOAD_ERROR = _e

from . import APP, APP_ID
from .palette import GLASS, GLASS_CSS, pick_font, rgba_hex
from .spawn import shell_argv, sidecar_argv, workdir_arg


def _rgba(hexstr: str):
    c = Gdk.RGBA()
    c.parse(rgba_hex(hexstr))
    return c


def _apply_css() -> None:
    provider = Gtk.CssProvider.new()
    provider.load_from_data(GLASS_CSS.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _paint_terminal(term) -> None:
    """vte colors from the Glass palette."""
    term.set_colors(_rgba(GLASS["foreground"]), _rgba(GLASS["background"]),
                    [_rgba(v) for v in GLASS["normal"] + GLASS["bright"]])
    if hasattr(term, "set_color_cursor"):
        term.set_color_cursor(_rgba(GLASS["cursor"]))
        term.set_color_cursor_foreground(_rgba(GLASS["cursor_text"]))
    sel_bg = getattr(term, "set_color_selection_background", None)
    sel_fg = getattr(term, "set_color_selection_foreground", None)
    if sel_bg and sel_fg:
        sel_bg(_rgba(GLASS["selection"]))
        sel_fg(_rgba(GLASS["selection_text"]))


def _run_shell(term, argv: list[str], cwd: str) -> None:
    """Spawn the shell into a vte. spawn_async first, spawn_sync fallback.
    VTE reaps its own children — plain SEARCH_PATH, no extra flags."""
    flags = GLib.SpawnFlags.SEARCH_PATH
    try:
        term.spawn_async(Vte.PtyFlags.DEFAULT, cwd or None, argv, [],
                         flags, None, None, -1, None)
    except (AttributeError, TypeError):
        try:
            term.spawn_sync(Vte.PtyFlags.DEFAULT, cwd or None, argv, [],
                            flags, None, None, None)
        except TypeError:
            term.spawn_sync(Vte.PtyFlags.DEFAULT, cwd or None, argv, [],
                            flags | (GLib.SpawnFlags.DO_NOT_REAP_CHILD
                                     if hasattr(GLib.SpawnFlags, "DO_NOT_REAP_CHILD")
                                     else 0), None, None, None)


def run(args) -> int:
    """Build + run the window. args = parsed namespace from cli.parse()."""
    if not READY:
        print(f"{APP}: GTK3/VTE bindings not importable — {LOAD_ERROR}")
        print("  linux:  sudo pacman -S gtk3 vte3 python-gobject")
        print("  macos:  brew install vte3 pygobject3 gtk+3")
        print("  windows: nlt-glass lives on Linux — use WSL/WSLg")
        return 77

    args_shell = getattr(args, "shell", "") or ""
    cwd = workdir_arg(getattr(args, "dir", ""))
    no_nlt = bool(getattr(args, "no_nlt", False))
    base_font = getattr(args, "font", "") or pick_font()
    m = re.search(r"^(.*?)\s+(\d+(?:\.\d+)?)$", base_font)
    family = m.group(1) if m else base_font
    size0 = float(m.group(2)) if m else 11.0

    app = Gtk.Application(application_id=APP_ID,
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    tabs: list[dict] = []
    state = {"size": size0, "win": None, "nb": None, "subtitle": None,
             "revealer": None, "side_vte": None, "side_spawned": False}

    def font_desc():
        return Pango.FontDescription.from_string(f"{family} {state['size']:g}")

    def apply_font() -> None:
        for tab in tabs:
            tab["term"].set_font(font_desc())
        if state["side_vte"] is not None:
            state["side_vte"].set_font(font_desc())

    def cur_term():
        page = state["nb"].get_nth_page(state["nb"].get_current_page())
        for tab in tabs:
            if tab["box"] is page:
                return tab["term"], tab
        return None, None

    def new_tab(*_a, focus: bool = True) -> None:
        term = Vte.Terminal()
        _paint_terminal(term)
        term.set_font(font_desc())

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        scroll = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL,
                               adjustment=term.get_vadjustment())
        box.pack_start(term, True, True, 0)
        box.pack_end(scroll, False, False, 0)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        label = Gtk.Label(label=fish_label(cwd))
        label.set_max_width_chars(26)
        close = Gtk.Button.new_from_icon_name(
            "window-close-symbolic", Gtk.IconSize.MENU)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.get_style_context().add_class("flat")
        row.pack_start(label, False, False, 1)
        row.pack_end(close, False, False, 0)
        row.show_all()

        tab = {"term": term, "box": box, "label": label,
               "title": fish_label(cwd)}
        tabs.append(tab)
        state["nb"].append_page(box, row)
        state["nb"].set_tab_reorderable(box, True)
        state["nb"].set_current_page(state["nb"].page_num(box))
        close.connect("clicked", lambda _b: close_page(box))
        term.connect("child-exited", on_child_exited, tab)
        term.connect("window-title-changed", on_title, tab)
        _run_shell(term, shell_argv(args_shell), cwd)
        if focus:
            term.grab_focus()

    def fish_label(where: str) -> str:
        base = "fish" if (not args_shell or "fish" in args_shell) else args_shell
        return f"{base} · {where.rsplit('/', 1)[-1] or '/'}"

    def on_title(_term, tab) -> None:
        t = tab["term"].get_window_title() or ""
        tab["title"] = t
        tab["label"].set_text(t[:30] or "shell")
        _c, cur = cur_term()
        if cur is tab and state["subtitle"] is not None:
            state["subtitle"].set_text(t)

    def close_page(box) -> None:
        idx = state["nb"].page_num(box)
        if idx < 0:
            return
        state["nb"].remove_page(idx)
        for tab in list(tabs):
            if tab["box"] is box:
                tabs.remove(tab)
        if state["nb"].get_n_pages() == 0:
            state["win"].destroy()

    def on_child_exited(_term, _status, tab) -> None:
        close_page(tab["box"])

    def close_tab() -> None:
        _t, tab = cur_term()
        if tab:
            close_page(tab["box"])

    def switch(delta: int) -> bool:
        nb = state["nb"]
        n = nb.get_n_pages()
        if n:
            nb.set_current_page((nb.get_current_page() + delta) % n)
            _t, tab = cur_term()
            if tab:
                tab["term"].grab_focus()
            return True
        return False

    def jump(page_num: int) -> bool:
        nb = state["nb"]
        if 0 <= page_num < nb.get_n_pages():
            nb.set_current_page(page_num)
            _t, tab = cur_term()
            if tab:
                tab["term"].grab_focus()
            return True
        return False

    def toggle_sidecar() -> None:
        if no_nlt or state["revealer"] is None:
            return
        revealing = not state["revealer"].get_reveal_child()
        state["revealer"].set_reveal_child(revealing)
        if revealing and not state["side_spawned"]:
            state["side_spawned"] = True
            argv = sidecar_argv()
            if argv:
                _run_shell(state["side_vte"], argv, cwd)
                state["side_vte"].grab_focus()
        elif revealing:
            state["side_vte"].grab_focus()

    def on_key(_win, ev) -> bool:
        name = Gdk.keyval_name(ev.keyval) or ""
        ctrl = bool(ev.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(ev.state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(ev.state & Gdk.ModifierType.MOD1_MASK)
        term, _tab = cur_term()
        eat = False
        if ctrl and shift:
            low = name.lower()
            if low == "t":
                new_tab()
                eat = True
            elif low == "w":
                close_tab()
                eat = True
            elif low == "g":
                toggle_sidecar()
                eat = True
            elif low in ("c",) and term:
                term.copy_clipboard()
                eat = True
            elif low in ("v",) and term:
                term.paste_clipboard()
                eat = True
            elif low in ("equal", "plus", "kp_add"):
                state["size"] = min(31.0, state["size"] + 1)
                apply_font()
                eat = True
            elif low in ("minus", "kp_subtract"):
                state["size"] = max(6.0, state["size"] - 1)
                apply_font()
                eat = True
        elif ctrl and not shift and not alt:
            if name == "Page_Up":
                eat = switch(-1)
            elif name == "Page_Down":
                eat = switch(1)
        elif alt and name in tuple("123456789"):
            eat = jump(int(name) - 1)
        elif name == "F1":
            toggle_sidecar()
            eat = True
        return eat

    def side_exited(_term, _status) -> None:
        state["side_spawned"] = False
        if state["revealer"] is not None:
            state["revealer"].set_reveal_child(False)

    def activate(_app) -> None:
        Gtk.Settings.get_default().set_property(
            "gtk-application-prefer-dark-theme", True)
        _apply_css()

        win = Gtk.ApplicationWindow(application=app)
        win.set_title("nlt-glass")
        win.set_default_size(960, 620)
        state["win"] = win

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.set_title("nlt-glass")
        subtitle = Gtk.Label(label=cwd)
        subtitle.get_style_context().add_class("subtitle")
        hb.set_custom_title(subtitle)
        state["subtitle"] = subtitle

        plus = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.MENU)
        plus.set_tooltip_text("new tab — ctrl+shift+t")
        plus.connect("clicked", new_tab)
        hb.pack_start(plus)

        nlt_btn = Gtk.Button(label="nlt")
        nlt_btn.get_style_context().add_class("flat")
        nlt_btn.set_tooltip_text("nlt chat sidecar — F1")
        installed = sidecar_argv() is not None
        nlt_btn.set_sensitive(installed and not no_nlt)
        if not installed:
            nlt_btn.set_tooltip_text("nlt not installed — pipx install nlt for the sidecar")
        nlt_btn.connect("clicked", lambda _b: toggle_sidecar())
        hb.pack_end(nlt_btn)
        win.set_titlebar(hb)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        nb = Gtk.Notebook()
        nb.set_show_border(False)
        nb.set_scrollable(True)
        state["nb"] = nb
        vbox.pack_start(nb, True, True, 0)

        revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP,
                                transition_duration=260, reveal_child=False)
        side_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        side_box.get_style_context().add_class("nlt-side")
        hint = Gtk.Label(label="nlt — chat · F1 hides · ctrl-g rescue works in tabs")
        hint.get_style_context().add_class("nlt-side-label")
        hint.set_halign(Gtk.Align.START)
        hint_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hint_box.pack_start(hint, False, False, 4)
        side_vte = Vte.Terminal()
        side_vte.set_size_request(-1, 240)
        side_vte.connect("child-exited", side_exited)
        s_scroll = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL,
                                 adjustment=side_vte.get_vadjustment())
        side_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        side_h.pack_start(side_vte, True, True, 0)
        side_h.pack_end(s_scroll, False, False, 0)
        side_vte.set_font(font_desc())
        _paint_terminal(side_vte)
        side_box.pack_start(hint_box, False, False, 0)
        side_box.pack_start(side_h, True, True, 0)
        revealer.add(side_box)
        state["revealer"] = revealer
        state["side_vte"] = side_vte
        vbox.pack_end(revealer, False, False, 0)
        win.add(vbox)

        win.connect("key-press-event", on_key)
        win.connect("destroy", lambda _w: app.quit())
        new_tab()
        win.show_all()

    app.connect("activate", activate)
    app.run([])
    return 0
