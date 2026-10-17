"""The glass — a GTK3 + VTE terminal window built around fish + nlt.

v1.1: real transparency (chrome + cells), two themes, split panes,
tabs that inherit the working directory, deeper nlt sidecar wiring.

Every tab spawns fish (or --shell); the nlt chat sidecar is one keypress
away; your nlt fish integration (ctrl-g rescue) works because fish loads
conf.d as usual. nlt itself is optional — the glass works without it.

Importing this module is safe everywhere: without GTK/VTE bindings it
loads with READY=False and run() prints a friendly pointer instead of a
traceback.
"""
from __future__ import annotations

import os
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

from . import APP, APP_ID, __version__
from . import bridge
from . import settings as cfg
from .palette import DEFAULT_THEME, THEMES, glass_css, pick_font, rgba_hex
from .spawn import shell_argv, sidecar_argv, uri_to_path, workdir_arg

OPACITY_MIN, OPACITY_STEP = 0.15, 0.1
SCROLLBACK = 10_000


def _clamp_f(value: object, lo: float, hi: float) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        v = 1.0
    return max(lo, min(hi, v))


def _rgba(hexstr: str):
    c = Gdk.RGBA()
    c.parse(rgba_hex(hexstr))
    return c


def _apply_css(stylesheet: str) -> None:
    provider = Gtk.CssProvider.new()
    provider.load_from_data(stylesheet.encode())
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _paint_terminal(term, theme: str, opacity: float) -> None:
    """vte colors from the palette + per-terminal opacity when supported."""
    pal = THEMES[theme]
    try:
        term.set_colors(_rgba(pal["foreground"]), _rgba(pal["background"]),
                        [_rgba(v) for v in pal["normal"] + pal["bright"]])
    except Exception:
        pass
    for prop, val in (("set_color_cursor", pal["cursor"]),
                      ("set_color_cursor_foreground", pal["cursor_text"]),
                      ("set_color_selection_background", pal["selection"]),
                      ("set_color_selection_foreground", pal["selection_text"])):
        fn = getattr(term, prop, None)
        if fn:
            try:
                fn(_rgba(val))
            except Exception:
                pass
    if 0.0 < opacity < 1.0:
        try:
            term.set_opacity(opacity)
        except Exception:
            pass  # visual/wayland constraints — degrade politely
    for call, arg in ((getattr(term, "set_scrollback_lines", None), SCROLLBACK),
                      (getattr(term, "set_audible_bell", None), False),
                      (getattr(term, "set_bold_is_bright", None), True)):
        if call:
            try:
                call(arg)
            except Exception:
                pass


def _run_shell(term, argv: list[str], cwd: str) -> None:
    """Spawn the shell into a vte. spawn_async first, spawn_sync fallback."""
    flags = GLib.SpawnFlags.SEARCH_PATH
    try:
        term.spawn_async(Vte.PtyFlags.DEFAULT, cwd or None, argv, [],
                         flags, None, None, -1, None)
    except (AttributeError, TypeError):
        try:
            term.spawn_sync(Vte.PtyFlags.DEFAULT, cwd or None, argv, [],
                            flags, None, None, None)
        except TypeError:
            try:
                term.spawn_sync(Vte.PtyFlags.DEFAULT, cwd or None, argv, [],
                                flags, None, None, -1, None)
            except TypeError:
                pass


def run(args) -> int:
    """Build + run the window. args = parsed namespace from cli.parse()."""
    if not READY:
        print(f"{APP}: GTK3/VTE bindings not importable — {LOAD_ERROR}")
        print("  linux:   sudo pacman -S gtk3 vte3 python-gobject")
        print("  macos:   brew install vte3 pygobject3 gtk+3")
        print("  windows: nlt-glass lives on Linux — use WSL/WSLg")
        return 77

    # precedence: CLI flags > settings.json > coded defaults
    s = cfg.merge_onto(args, cfg.load())
    args_shell = str(s.get("shell") or "")
    cwd = workdir_arg(str(s.get("dir") or ""))
    no_nlt = bool(s.get("no_nlt", False))
    theme = str(s.get("theme") or DEFAULT_THEME)
    if theme not in THEMES:
        print(f"{APP}: unknown theme {theme!r} — using {DEFAULT_THEME}")
        theme = DEFAULT_THEME
    opacity = _clamp_f(s.get("opacity", 1.0), OPACITY_MIN, 1.0)
    base_font = str(s.get("font") or "").strip() or pick_font()
    m = re.search(r"^(.*?)\s+(\d+(?:\.\d+)?)$", base_font)
    family = m.group(1) if m else base_font
    size0 = float(m.group(2)) if m else 11.0
    try:
        scrollback = int(s.get("scrollback", SCROLLBACK))
    except (TypeError, ValueError):
        scrollback = SCROLLBACK
    plugin_names = [str(p) for p in (s.get("plugins") or []) if str(p)]

    app = Gtk.Application(application_id=APP_ID,
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    tabs: list[dict] = []          # tab dicts: page/panes/label/title
    state = {"size": size0, "opacity": opacity, "win": None, "nb": None,
             "subtitle": None, "subtitle_extra": None, "revealer": None,
             "side_vte": None, "side_spawned": False, "pane": None,
             "theme": theme, "tabs": tabs, "scrollback": scrollback}

    # ------------------------------------------------------------ fonts
    def font_desc():
        return Pango.FontDescription.from_string(f"{family} {state['size']:g}")

    def apply_font() -> None:
        for tab in tabs:
            for pane in tab["panes"]:
                pane["term"].set_font(font_desc())
        if state["side_vte"] is not None:
            state["side_vte"].set_font(font_desc())

    # ------------------------------------------------------------- lookup
    def cur_tab() -> dict | None:
        pane = state.get("pane")
        if pane is not None and pane["tab"] in tabs:
            return pane["tab"]
        page = state["nb"].get_nth_page(state["nb"].get_current_page())
        for tab in tabs:
            if tab["page"] is page:
                return tab
        return None

    def cur_pane() -> dict | None:
        tab = cur_tab()
        if tab is None:
            return None
        if state.get("pane") is not None and state["pane"]["tab"] is tab:
            return state["pane"]
        return tab["panes"][0] if tab["panes"] else None

    # --------------------------------------------------------------- tabs
    def tab_paint() -> None:
        for tab in tabs:
            for pane in tab["panes"]:
                _paint_terminal(pane["term"], state.get("theme", theme),
                                state["opacity"])

    def fish_label(where: str) -> str:
        base = "fish" if (not args_shell or "fish" in args_shell) else args_shell
        return f"{base} · {where.rsplit('/', 1)[-1] or '/'}"

    def _make_pane(tab: dict, where: str) -> dict:
        term = Vte.Terminal()
        _paint_terminal(term, state.get("theme", theme), state["opacity"])
        term.set_font(font_desc())
        try:
            term.set_scrollback_lines(scrollback)
        except Exception:
            pass
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        scroll = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL,
                               adjustment=term.get_vadjustment())
        box.pack_start(term, True, True, 0)
        box.pack_end(scroll, False, False, 0)
        pane = {"term": term, "box": box, "tab": tab, "cwd": where}
        tab["panes"].append(pane)
        term.connect("child-exited", on_pane_exit, pane)
        term.connect("focus-in-event", on_pane_focus, pane)
        term.connect("window-title-changed", _pane_title, tab)
        _run_shell(term, shell_argv(args_shell), where)
        return pane

    def new_tab(*_a, cwd_arg: str = "") -> None:
        where = cwd_arg or inherit_cwd()
        nb = state["nb"]
        page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab = {"page": page, "panes": [], "label": None, "title": "",
               "cwd": where}
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        label = Gtk.Label(label=fish_label(where))
        label.set_max_width_chars(26)
        close = Gtk.Button.new_from_icon_name(
            "window-close-symbolic", Gtk.IconSize.MENU)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.get_style_context().add_class("flat")
        row.pack_start(label, False, False, 1)
        row.pack_end(close, False, False, 0)
        row.show_all()
        tab["label"] = label

        tabs.append(tab)
        nb.append_page(page, row)
        nb.set_tab_reorderable(page, True)
        nb.set_current_page(nb.page_num(page))
        close.connect("clicked", lambda _b: close_page(page))
        pane = _make_pane(tab, where)
        page.pack_start(pane["box"], True, True, 0)
        page.show_all()
        state["pane"] = pane
        pane["term"].grab_focus()

    def inherit_cwd() -> str:
        pane = state.get("pane")
        if pane is not None:
            try:
                p = uri_to_path(pane["term"].get_current_directory_uri() or "")
                if p and os.path.isdir(p):
                    return p
            except Exception:
                pass
            return pane["cwd"]
        return cwd

    def on_pane_focus(_term, _ev, pane) -> None:
        state["pane"] = pane
        tab = pane["tab"]
        if state["subtitle"] is not None:
            state["subtitle"].set_text(
                pane["term"].get_window_title() or tab["cwd"])

    def _pane_title(_term, tab) -> None:
        pane = state.get("pane")
        if pane is not None and pane["tab"] is tab:
            t = pane["term"].get_window_title() or ""
            tab["title"] = t
            tab["label"].set_text(t[:30] or fish_label(tab["cwd"]))
            if state["subtitle"] is not None:
                state["subtitle"].set_text(t)

    def on_pane_exit(_term, _status, pane) -> None:
        tab = pane["tab"]
        if len(tab["panes"]) > 1:
            unmount_pane(tab, pane)
        else:
            close_page(tab["page"])

    # ------------------------------------------------------------ splits
    def split(orientation: Gtk.Orientation, side: str = "left") -> None:
        """Split the focused pane: side-by-side (E) or stacked (O).
        Pane boxes get nested inside Gtk.Paned hierarchies, replacing
        themselves in place — sibling splits stay untouched."""
        tab = cur_tab()
        pane = cur_pane()
        if tab is None or pane is None:
            return
        paned = Gtk.Paned(orientation=orientation)
        paned.set_wide_handle(False)
        other = _make_pane(tab, inherit_cwd())
        parent = pane["box"].get_parent()
        if isinstance(parent, Gtk.Box):
            parent.remove(pane["box"])
            parent.pack_start(paned, True, True, 0)
        elif isinstance(parent, Gtk.Paned):
            first = parent.get_child1() is pane["box"]
            parent.remove(pane["box"])
            if first:
                parent.pack1(paned, True, True)
            else:
                parent.pack2(paned, True, True)
        if side == "left":
            paned.pack1(pane["box"], True, False)
            paned.pack2(other["box"], True, False)
        else:
            paned.pack2(pane["box"], True, False)
            paned.pack1(other["box"], True, False)
        paned.connect("size-allocate", _half_position)
        paned.show_all()
        other["term"].grab_focus()

    def _half_position(paned, alloc) -> None:
        """First allocation: give each half its share (then leave it alone)."""
        if getattr(paned, "_glass_halved", False):
            return
        paned._glass_halved = True  # noqa: SLF001 — python-signal bookkeeping
        span = alloc.width if paned.get_orientation() == Gtk.Orientation.HORIZONTAL \
            else alloc.height
        try:
            paned.set_position(max(1, int(span / 2)))
        except Exception:
            pass

    def unmount_pane(tab: dict, pane: dict) -> None:
        """One of several panes died: detach it, keep siblings. The parent
        Paned collapses into its survivor, at any nesting depth."""
        box = pane["box"]
        parent = box.get_parent()
        tab["panes"].remove(pane)
        if state.get("pane") is pane:
            state["pane"] = tab["panes"][0] if tab["panes"] else None
        if parent is None:
            return
        if isinstance(parent, Gtk.Box):
            parent.remove(box)
            if not parent.get_children() and tab["panes"]:
                parent.pack_start(tab["panes"][0]["box"], True, True, 0)
        elif isinstance(parent, Gtk.Paned):
            first = parent.get_child1() is box
            keep = parent.get_child2() if first else parent.get_child1()
            parent.remove(box)
            if keep is None:
                return
            grand = parent.get_parent()
            if isinstance(grand, Gtk.Box):
                if parent in grand.get_children():
                    grand.remove(parent)
                grand.pack_start(keep, True, True, 0)
            elif isinstance(grand, Gtk.Paned):
                was_first = grand.get_child1() is parent
                grand.remove(parent)
                if was_first:
                    grand.pack1(keep, True, False)
                else:
                    grand.pack2(keep, True, False)
        if tab["panes"]:
            tab["panes"][0]["term"].grab_focus()
        _refocus_soon()

    def _refocus_soon() -> None:
        pane = state.get("pane")
        if pane is not None:
            GLib.idle_add(lambda: pane["term"].grab_focus() or False)

    # ------------------------------------------------------------ closing
    def close_page(page) -> None:
        nb = state["nb"]
        idx = nb.page_num(page)
        if idx < 0:
            return
        for tab in list(tabs):
            if tab["page"] is page:
                tabs.remove(tab)
        nb.remove_page(idx)
        if not tabs:
            state["win"].destroy()

    def close_tab() -> None:
        tab = cur_tab()
        if tab:
            close_page(tab["page"])

    # --------------------------------------------------------- navigation
    def switch(delta: int) -> bool:
        nb = state["nb"]
        if nb.get_n_pages():
            nb.set_current_page((nb.get_current_page() + delta) % nb.get_n_pages())
            pane = cur_pane()
            if pane:
                pane["term"].grab_focus()
            return True
        return False

    def jump(page_num: int) -> bool:
        nb = state["nb"]
        if 0 <= page_num < nb.get_n_pages():
            nb.set_current_page(page_num)
            pane = cur_pane()
            if pane:
                pane["term"].grab_focus()
            return True
        return False

    def cycle_panes(delta: int) -> bool:
        tab = cur_tab()
        if not tab or len(tab["panes"]) < 2:
            return False
        pane = state.get("pane") or tab["panes"][0]
        try:
            idx = tab["panes"].index(pane)
        except ValueError:
            idx = 0
        target = tab["panes"][(idx + delta) % len(tab["panes"])]
        state["pane"] = target
        target["term"].grab_focus()
        return True

    # ------------------------------------------------------------ sidecar
    def toggle_sidecar() -> None:
        if no_nlt or state["revealer"] is None:
            return
        revealing = not state["revealer"].get_reveal_child()
        state["revealer"].set_reveal_child(revealing)
        if revealing and not state["side_spawned"]:
            state["side_spawned"] = True
            argv = sidecar_argv()
            if argv:
                pane = cur_pane()
                _run_shell(state["side_vte"], argv, pane["cwd"] if pane else cwd)
                state["side_vte"].grab_focus()
        elif revealing:
            state["side_vte"].grab_focus()

    def side_exited(_term, _status) -> None:
        state["side_spawned"] = False
        if state["revealer"] is not None:
            state["revealer"].set_reveal_child(False)

    # ------------------------------------------------------------ opacity
    def shift_opacity(delta: float) -> bool:
        state["opacity"] = max(OPACITY_MIN, min(1.0, state["opacity"] + delta))
        tab_paint()
        _apply_css(glass_css(state.get("theme", theme), state["opacity"]))
        for pane in [p for tab in tabs for p in tab["panes"]]:
            try:
                pane["term"].set_opacity(state["opacity"])
            except Exception:
                pass
        return True

    # -------------------------------------------------------------- keyboard
    def on_key(_win, ev) -> bool:
        name = Gdk.keyval_name(ev.keyval) or ""
        ctrl = bool(ev.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(ev.state & Gdk.ModifierType.SHIFT_MASK)
        alt = bool(ev.state & Gdk.ModifierType.MOD1_MASK)
        pane = cur_pane()
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
            elif low == "e":
                split(Gtk.Orientation.HORIZONTAL)
                eat = True
            elif low == "o":
                split(Gtk.Orientation.VERTICAL)
                eat = True
            elif low == "bracketleft":
                eat = shift_opacity(-OPACITY_STEP)
            elif low == "bracketright":
                eat = shift_opacity(OPACITY_STEP)
            elif low == "0":
                state["size"] = size0
                apply_font()
                eat = True
            elif low == "c" and pane:
                pane["term"].copy_clipboard()
                eat = True
            elif low == "v" and pane:
                pane["term"].paste_clipboard()
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
        elif alt and not ctrl and not shift:
            if name in tuple("123456789"):
                eat = jump(int(name) - 1)
            elif name in ("Left", "Up"):
                eat = cycle_panes(-1)
            elif name in ("Right", "Down"):
                eat = cycle_panes(1)
        elif name == "F1":
            toggle_sidecar()
            eat = True
        return eat

    # ---------------------------------------------------------------- ui
    def activate(_app) -> None:
        Gtk.Settings.get_default().set_property(
            "gtk-application-prefer-dark-theme", True)
        _apply_css(glass_css(theme, opacity))

        win = Gtk.ApplicationWindow(application=app)
        win.set_title("nlt-glass")
        win.set_default_size(960, 620)
        state["win"] = win

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.set_title("nlt-glass")
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        subtitle = Gtk.Label(label=cwd)
        subtitle.get_style_context().add_class("subtitle")
        subtitle.set_ellipsize(Pango.EllipsizeMode.END)
        extra_status = Gtk.Label(label="")
        extra_status.get_style_context().add_class("subtitle")
        title_box.pack_start(subtitle, False, False, 0)
        title_box.pack_start(extra_status, False, False, 0)
        hb.set_custom_title(title_box)
        state["subtitle"] = subtitle
        state["subtitle_extra"] = extra_status

        plus = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.MENU)
        plus.set_tooltip_text("new tab — ctrl+shift+t (inherits this tab's directory)")
        plus.connect("clicked", lambda _b: new_tab())
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
        hint = Gtk.Label(label="nlt — chat · F1 hides · ctrl-g rescue works in tabs · "
                               "e/o split · [ ] opacity")
        hint.get_style_context().add_class("nlt-side-label")
        hint.set_halign(Gtk.Align.START)
        side_vte = Vte.Terminal()
        side_vte.set_size_request(-1, 250)
        side_vte.connect("child-exited", side_exited)
        s_scroll = Gtk.Scrollbar(orientation=Gtk.Orientation.VERTICAL,
                                 adjustment=side_vte.get_vadjustment())
        side_h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        side_h.pack_start(side_vte, True, True, 0)
        side_h.pack_end(s_scroll, False, False, 0)
        side_vte.set_font(font_desc())
        _paint_terminal(side_vte, state.get("theme", theme), state["opacity"])
        side_box.pack_start(hint, False, False, 0)
        side_box.pack_start(side_h, True, True, 0)
        revealer.add(side_box)
        state["revealer"] = revealer
        state["side_vte"] = side_vte
        vbox.pack_end(revealer, False, False, 0)
        win.add(vbox)

        win.connect("key-press-event", on_key)
        win.connect("destroy", lambda _w: app.quit())
        new_tab(cwd_arg=cwd)
        ctx = bridge.GlassContext(win, hb, nb, state, s, app)
        state["ctx"] = ctx
        bridge.load_plugins(plugin_names, ctx)
        win.show_all()

    app.connect("activate", activate)
    app.run([])
    return 0
