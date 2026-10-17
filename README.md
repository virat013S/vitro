# ▶ Vitro — the glass terminal

[![tests](https://github.com/virat013S/vitro/actions/workflows/tests.yml/badge.svg)](https://github.com/virat013S/vitro/actions/workflows/tests.yml)

A **fish-first terminal** made of dark glass. Real terminal emulation via
**GTK3 + VTE** (the GNOME Terminal / tilix engine — fast, correct, Wayland +
X11), a kitty-dark palette, real transparency with a slider, splits, and the
[nlt](https://github.com/virat013S/nlt) brain one keypress away.

It greets you with **ourfetch** — its own fetch, typed out fast, showing
your OS logo (or an image you pick).

## The look

- **Kitty-dark glass**: quiet charcoal (`#131317`), pale cursor, dimmed
  accent — no neon, no noise. **Graphite** is darker still.
- **Real transparency** — chrome *and* cells go see-through; pair with
  Hyprland/KWin blur for actual frosted glass. Live **transparency bar** and
  **font-size bar** in the header (`88%` / `11` buttons → drag), or keys
  `Ctrl+Shift+[` / `]` and `Ctrl+ +` / `-` / `0`.
- Pill tabs with accent underline, hairline scrollbar, 12px breathing room.
- Own app icon + desktop entry: `vitro install-desktop`.

## The features

- **fish in every tab** (`--login` — your fish integration loads, so nlt's
  `ctrl-g` rescue works out of the box, zero wiring).
- **ourfetch greets the first tab** — typed-fast system info; set your own
  logo image with `ourfetch set-image photo.png`.
- **nlt sidecar** — `F1` slides a chat panel (`nlt chat`) up from the bottom;
  it opens in the focused tab's directory.
- **Splits**: `Ctrl+Shift+E` side-by-side, `Ctrl+Shift+O` stacked; cycle
  panes with `Alt+Arrow`; panes collapse on exit like they should.
- **Tabs that inherit directories**: new tabs open in the current tab's
  working directory (`Ctrl+Shift+T`).
- 10 000 lines of scrollback, silent bell, copy/paste, Alt+1..9 jumps —
  the usual expectation set, minus config sprawl.

## ourfetch

Fastfetch, but ours — pure python, no deps, sub-second:

```bash
ourfetch                    # the greeting (typing animation on a tty)
ourfetch --no-anim          # instant, for scripts
ourfetch --cols 48          # wider logo
ourfetch set-image cat.png  # your image becomes the logo (png; jpg via Pillow)
ourfetch clear-image        # back to the automatic OS logo
```

No image set? It draws the **real fastfetch logo** for your OS (taken
straight from fastfetch's collection — Arch's `/`, CachyOS's chad-shard,
colored in each distro's brand tones); anything unknown gets vitro's own
glass shard. Your image lives at `~/.config/vitro/image.png`, remembered
in `fetch.json`.

## Settings

Zero config by default; every knob lives in one optional JSON file.
Precedence: **CLI flags > settings file > coded defaults**.

```bash
vitro settings              # show the path + current values
vitro settings init         # write the defaults file (--force overwrites)
vitro settings edit         # open it in $EDITOR
```

`~/.config/vitro/settings.json` (honors `XDG_CONFIG_HOME`):

```json
{
  "theme": "glass",
  "opacity": 0.88,
  "font": "",
  "font_size": 0,
  "shell": "",
  "dir": "",
  "no_nlt": false,
  "fetch": true,
  "plugins": ["clock", "cheats", "theme", "sysinfo"],
  "scrollback": 10000
}
```

- `opacity` — 0.15–1.0; frosted with compositor blur
- `font_size` — 0 = follow the font string's size; any other value (e.g. 13.5)
  wins. The two header bars (`88%`, `11`) drag-set both of these live and
  save automatically when you close the bar
- `fetch` — the ourfetch greeting in the first tab (turn off if it annoys you)
- `font` / `shell` — empty strings mean auto-detect (JetBrainsMono/Iosevka…, fish)
- `plugins` — which builtins run, disable any by removing it
- broken JSON never bricks the terminal — defaults kick in

## Plugins

Inbuilt, small, honest — a plugin is any module with `register(ctx)`:

| builtin   | what it does                                                |
|-----------|-------------------------------------------------------------|
| `clock`   | quiet HH:MM tick in the header status strip                 |
| `sysinfo` | load-average badge (λ) next to the clock (Linux)            |
| `theme`   | one click cycles glass ⇄ graphite **and saves the setting** |
| `cheats`  | `⌨` button opens the keybindings cheat sheet                |

Your own plugins go in `~/.config/vitro/plugins/`:

```python
# ~/.config/vitro/plugins/hello.py
def register(ctx):
    ctx.status("hello", "hi")        # shows in the header strip
```

Every `*.py` in that folder is auto-loaded; names in the `plugins` list can
reference user files too (a user file shadows an inbuilt of the same name).
Plugin surface: `ctx.window`, `ctx.headerbar`, `ctx.notebook`, `ctx.state`,
`ctx.settings`, `ctx.app`, `ctx.retheme(name)`, `ctx.status(key, text)`.
A broken plugin is skipped with a stderr note — the terminal never dies.

## Keybindings

| keys                   | action                                      |
|------------------------|---------------------------------------------|
| `F1` / Ctrl+Shift+G    | hide/show the nlt sidecar                   |
| Ctrl+Shift+T / W       | new / close tab (new tab follows cwd)       |
| Ctrl+Shift+E / O       | split side-by-side / stacked                |
| Alt+Arrow              | move between panes                          |
| Ctrl+PgUp / PgDn       | previous / next tab                         |
| Alt+1..9               | jump to tab N                               |
| Ctrl+Shift+C / V       | copy / paste                                |
| Ctrl+Shift+[ / ]       | less / more transparency                    |
| Ctrl+ + / - / 0        | font bigger / smaller / reset (shift works too) |

Your regular fish/shell keys all pass through untouched.

## Install

Linux (GTK3 + VTE + PyGObject — pacman names below):

```bash
sudo pacman -S --needed gtk3 vte3 python-gobject   # arch — apt/brew equivalents exist
pip install --user git+https://github.com/virat013S/vitro
# or from a clone:
python3 -m pip install --user .
vitro install-desktop                     # app icon + launcher entry
```

Run it:

```bash
vitro                       # reads ~/.config/vitro/settings.json on start
vitro settings              # view knobs: theme, opacity, font, shell, plugins…
vitro --opacity 0.8         # flag overrides — frosted with compositor blur
vitro --theme graphite      # darker, calmer
vitro --dir ~/projects      # open somewhere specific
vitro --shell zsh           # other shells keep working
vitro --font "Iosevka 12"
vitro --no-nlt              # pure terminal mode
```

For the full brain: `pipx install nlt` and `nlt fish install` — then
`ctrl-g` inside any Vitro tab rescues your last failed command.

## Files

- Settings: `~/.config/vitro/settings.json` · ourfetch: `fetch.json` + `image.png`
- Plugins: `~/.config/vitro/plugins/*.py`
- Your fish integration still lives where nlt puts it: `~/.config/fish/conf.d/nlt.fish`

## Platform

| platform | status                                                    |
|----------|-----------------------------------------------------------|
| Linux    | ✅ the real deal (Wayland + X11, transparency included)   |
| macOS    | 🟡 pure-logic CI green; GUI is best-effort via brew gtk+vte |
| Windows  | 🟡 pure-logic CI green; GUI via WSL/WSLg                  |

CI runs the pure logic on ubuntu + macos + windows, plus a real GTK
bindings smoke test on ubuntu.
