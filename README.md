# Lumina

<img src="docs/logo.png" alt="" width="64">

Package manager for Arch. pacman for the official repos. paru for the AUR, or yay if you don't have paru.

Install, remove, and update show the command first. You confirm it, then the output shows up in the window. `--noconfirm` is added only after that.

![Installed packages, with origin and a details panel](docs/installed.png)

## Install

From the AUR:

```sh
yay -S lumina-pacman-git
```

`paru -S lumina-pacman-git` works too. The package name is not `lumina`. That name is already used.

On Arch, from this checkout:

```sh
./install.sh
```

That installs the libraries Lumina needs, the `lumina` command, the desktop entry, and the icon. `./install.sh --system` installs for every user under `/usr/local`. `./install.sh --uninstall` removes it.

## Run

```sh
lumina
```

From a checkout, without installing:

```sh
python -m lumina
```

## What's in the window

Installed lists name, version, size, and origin. Filters cover explicit, official, AUR, and orphans. The side panel has the description, dependencies, required-by, homepage, and licenses.

Updates shows pending upgrades from the repos and the AUR. You can update the system, sync the databases, or upgrade one package. The line is whatever pacman or your helper would run.

![Discover, with apps from the official repos and the AUR](docs/discover.png)

Discover is a short list of common apps, with icons, grouped into web, creative, games, media, and development. Search is there if you already know the package name.

![Tools, with storage, orphans, and cache](docs/tools.png)

Tools shows orphans, cache size, and a disk bar. Removing orphans or cleaning the cache shows the command first.

![Install dialog](docs/install.png)

![Remove dialog](docs/remove.png)

Window size and the last filter are saved in `~/.config/lumina/config.json`.

## Shortcuts

`Ctrl+F` search, `F5` refresh, `Delete` remove the selected package (ignored while typing), `Ctrl+Q` quit.

## Requirements

Arch Linux, `python`, `python-gobject`, `gtk4`, `libadwaita`, `pacman`, and `polkit` (`pkexec`, plus a graphical agent). `paru` or `yay` is optional. Official repos work without a helper.

Removal needs a running polkit agent. On Hyprland that is often `polkit-kde-agent`.

## Tests

```sh
python -m unittest discover -s tests
```
