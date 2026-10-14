# Lumina

A transparent GTK4 + libadwaita package manager for Arch Linux.

Lumina lists installed packages, shows where they came from, and removes them only after displaying the exact `pkexec pacman` command. Output is streamed into the dialog.

## Requirements

- Arch Linux
- `python`
- `python-gobject`
- `gtk4`
- `libadwaita`
- `pacman`
- `polkit` (`pkexec`, plus a graphical authentication agent)
- Optional: `paru` or `yay` (detected at startup; `paru` is preferred)

## Run

From this directory:

```sh
python -m lumina
```

Or:

```sh
./bin/lumina
```

## What works now

- Installed package list with name, version, size, and origin
- Fuzzy search and filters: all, explicit, official, AUR/foreign, orphans
- Details: description, origin, dependencies, required-by, homepage, licenses
- Remove, with a dependency preview and the exact command before `pkexec` runs
- Live command output
- Window size and last filter saved in `~/.config/lumina/config.json`
- AUR helper detection

Search, updates, and maintenance tools are stub pages. See `PLAN.md`.

## Shortcuts

- `Ctrl+F` search
- `F5` refresh
- `Delete` remove the selected package (ignored while typing)
- `Ctrl+Q` quit

## Tests

```sh
python -m unittest discover -s tests
```

## Desktop entry

After installing the `lumina` command (for example `pip install --user -e .`):

```sh
install -Dm644 data/com.github.lumina.desktop ~/.local/share/applications/com.github.lumina.desktop
update-desktop-database ~/.local/share/applications || true
```

Removal needs a running polkit agent. On Hyprland that is often `polkit-kde-agent` or another agent started with the session.
