# ✦ nlt-glass — the glass around the brain

[![tests](https://github.com/virat013S/nlt-glass/actions/workflows/tests.yml/badge.svg)](https://github.com/virat013S/nlt-glass/actions/workflows/tests.yml)

A **fish-first terminal window** built to host [nlt](https://github.com/virat013S/nlt) —
the Natural Language Terminal. Real terminal emulation via **GTK3 + VTE**
(the GNOME Terminal / tilix engine — fast, correct, Wayland + X11), a
beautiful **Glass theme with real transparency**, splits, and the nlt chat
sidecar one keypress away.

## The look

- Dark **Glass** chrome — quiet charcoal in kitty's spirit (or
  **Graphite**, darker still) — 12px breathing room, pill tabs with an
  accent underline, hairline scrollbar, custom pale cursor.
- **Real transparency** — `--opacity 0.8` makes chrome *and* cells see
  through; pair with Hyprland/KWin blur for actual frosted glass.
  Adjust live with `Ctrl+Shift+[` / `Ctrl+Shift+]` (down to 15%).
- Font zoom `Ctrl+Shift+ +/-`, reset `Ctrl+Shift+0`; nice monospace fonts
  are auto-detected (JetBrains/Iosevka…).

## The features

- **fish in every tab** (`--login` — your fish integration loads, so nlt's
  `ctrl-g` rescue works out of the box, zero wiring).
- **nlt sidecar** — `F1` slides a chat panel (`nlt chat`) up from the
  bottom; it opens in the focused tab's directory.
- **Splits**: `Ctrl+Shift+E` side-by-side, `Ctrl+Shift+O` stacked; cycle
  panes with `Alt+Arrow`; panes collapse on exit like they should.
- **Tabs that inherit directories**: new tabs open in the current tab's
  working directory (`Ctrl+Shift+T`).
- 10 000 lines of scrollback, silent (visual) bell, copy/paste, Alt+1..9
  tab jumps — the usual expectation set, minus config files.

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
| Ctrl+Shift+ +/- / 0    | font bigger / smaller / reset               |

## Settings

Zero config by default; every knob lives in one optional JSON file.
Precedence: **CLI flags > settings file > coded defaults**.

```bash
nlt-glass settings           # show the path + current values
nlt-glass settings init      # write the defaults file (--force overwrites)
nlt-glass settings edit      # open it in $EDITOR
```

`~/.config/nlt-glass/settings.json` (honors `XDG_CONFIG_HOME`):

```json
{
  "theme": "glass",
  "opacity": 0.88,
  "font": "",
  "shell": "",
  "dir": "",
  "no_nlt": false,
  "plugins": ["clock", "cheats", "theme", "sysinfo"],
  "scrollback": 10000
}
```

- `opacity` — 0.15–1.0; with Hyprland/KWin blur you get real frosted glass
- `font` / `shell` — empty strings mean auto-detect (JetBrainsMono/Iosevka…, fish)
- `plugins` — which of the builtins run, disable any by removing it
- broken JSON never bricks the terminal — defaults kick in

## Plugins

Inbuilt, small, honest — a plugin is any module with `register(ctx)`:

| builtin   | what it does                                                |
|-----------|-------------------------------------------------------------|
| `clock`   | quiet HH:MM tick in the header status strip                 |
| `sysinfo` | load-average badge (λ) next to the clock (Linux)            |
| `theme`   | one click cycles glass ⇄ graphite **and saves the setting** |
| `cheats`  | `⌨` button opens the keybindings cheat sheet                |

Your own plugins go in `~/.config/nlt-glass/plugins/`:

```python
# ~/.config/nlt-glass/plugins/hello.py
def register(ctx):
    ctx.status("hello", "hi")        # shows in the header strip
```

Every `*.py` in that folder is auto-loaded; names in the `plugins` list can
reference user files too (a user file shadows an inbuilt of the same name).
Plugin surface: `ctx.window`, `ctx.headerbar`, `ctx.notebook`, `ctx.state`,
`ctx.settings`, `ctx.app`, `ctx.retheme(name)`, `ctx.status(key, text)`.
A broken plugin is skipped with a stderr note — the terminal never dies.

nlt itself is **optional** — without it, nlt-glass is simply a beautiful
transparent fish terminal.

## Install

Linux (GTK3 + VTE + PyGObject — pacman names below):

```bash
sudo pacman -S --needed gtk3 vte3 python-gobject   # arch — apt/brew equivalents exist
pip install --user git+https://github.com/virat013S/nlt-glass
# or from a clone:
python3 -m pip install --user .
```

Run it:

```bash
nlt-glass                        # reads ~/.config/nlt-glass/settings.json on start
nlt-glass settings               # view knobs: theme, opacity, font, shell, plugins…
nlt-glass --opacity 0.8          # flag overrides — frosted with compositor blur
nlt-glass --theme graphite       # darker, calmer
nlt-glass --dir ~/projects       # open somewhere specific
nlt-glass --shell zsh            # other shells keep working
nlt-glass --font "Iosevka 12"
nlt-glass --no-nlt               # pure terminal mode
```

For the full brain: `pipx install nlt` and `nlt fish install` — then
`ctrl-g` inside any nlt-glass tab rescues your last failed command.

## Files & home cleanliness

No config files, no home clutter. Your fish integration still lives where
nlt puts it: `~/.config/fish/conf.d/nlt.fish`.

## Platform

| platform | status                                                    |
|----------|-----------------------------------------------------------|
| Linux    | ✅ the real deal (Wayland + X11, transparency included)   |
| macOS    | 🟡 pure-logic CI green; GUI is best-effort via brew gtk+vte |
| Windows  | 🟡 pure-logic CI green; GUI via WSL/WSLg                  |

CI runs the pure logic on ubuntu + macos + windows, plus a real GTK
bindings smoke test on ubuntu.

## Tests

```bash
python3 -m pytest tests -q
```

## License

MIT
