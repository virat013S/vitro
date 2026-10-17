# ✦ nlt-glass — the glass around the brain

[![tests](https://github.com/virat013S/nlt-glass/actions/workflows/tests.yml/badge.svg)](https://github.com/virat013S/nlt-glass/actions/workflows/tests.yml)

A **fish-first terminal window** built to host [nlt](https://github.com/virat013S/nlt) —
the Natural Language Terminal. Alacritty is a great glass; this one is made
to be the *glass for the brain*: every tab speaks fish natively, and the
nlt chat sidecar is one keypress away.

## What it is

- Real terminal emulation via **GTK3 + VTE** (the same combo as GNOME
  Terminal / tilix) — fast, correct, Wayland- and X11-ready.
- **fish in every tab** (`--login` so your fish integration loads — which
  means nlt's `ctrl-g` rescue works out of the box, no extra wiring).
- **nlt sidecar** — press `F1` (or the `nlt` button) and a chat panel slides
  up from the bottom running `nlt chat`. Translate tasks in the sidecar while
  you keep working in the tab.
- The **Glass theme**: dark navy chrome, 12px breathing room, cyan-blue
  cursor, clean tabs, hairline scrollbar. Copy-paste, tab management, font
  zoom included.
- nlt itself is **optional** — without it, nlt-glass is simply a nice dark
  fish terminal.

## Keybindings

| keys               | action                                   |
|--------------------|------------------------------------------|
| `F1` / Ctrl+Shift+G| hide/show the nlt sidecar                |
| Ctrl+Shift+T       | new tab                                  |
| Ctrl+Shift+W       | close tab                                |
| Ctrl+PgUp / PgDn   | previous / next tab                      |
| Alt+1..9           | jump to tab N                            |
| Ctrl+Shift+C / V   | copy / paste                             |
| Ctrl+Shift+ + / -  | font bigger / smaller                    |

Your regular fish/shell keys all pass through untouched.

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
nlt-glass                     # window with fish in tab one
nlt-glass --dir ~/projects    # open somewhere specific
nlt-glass --shell zsh         # other shells keep working
nlt-glass --font "Iosevka 12"
nlt-glass --no-nlt            # pure terminal mode
```

For the full experience: `pipx install nlt` and `nlt fish install` — then
`ctrl-g` inside any nlt-glass tab rescues your last failed command.

## Files keys live

- No config files, no home clutter. (`~/.cache` only via GTK internals.)
- Your fish integration still lives where nlt puts it: `~/.config/fish/conf.d/nlt.fish`.

## Platform

| platform | status                                                    |
|----------|-----------------------------------------------------------|
| Linux    | ✅ the real deal (Wayland + X11)                          |
| macOS    | 🟡 pure-logic CI green; GUI is best-effort via brew gtk+vte    |
| Windows  | 🟡 pure-logic CI green; GUI via WSL/WSLg                  |

CI runs the pure logic on ubuntu + macos + windows, plus a real
`xvfb-run` smoke test that builds the actual GTK window on ubuntu.

## Tests

```bash
python3 -m pytest tests -q
```

## License

MIT
