# Arch Package Manager GUI

A modern, simple, and transparent graphical package manager for Arch Linux.

## Overview

This application is a native GTK4 + libadwaita GUI for managing packages on Arch Linux. It aims to make checking installed applications and managing them easier, while remaining transparent about what is actually happening under the hood.

It should work well on **Hyprland**, **KDE Plasma**, and other desktops.

## Goals

- Fast and pleasant way to browse installed packages
- Clear and transparent package operations (install, remove, update)
- Support for official repositories and the AUR
- Modern, clean interface that feels good on Wayland
- Minimal "magic" — show real commands and output
- Useful for both beginners and more experienced Arch users

## Tech Stack

- **Language**: Python 3
- **GUI**: GTK4 + libadwaita (via PyGObject)
- **Package backend**:
  - `pacman` for official repositories
  - Optional AUR helpers: `yay` or `paru` (detect which one is available)
- **Target**: Arch Linux (and Arch-based distributions)

## Core Features

### 1. Installed Packages View
- Fast loading and listing of all installed packages
- Live fuzzy search
- Filters:
  - All installed
  - Explicitly installed
  - Official repositories
  - AUR
  - Foreign / local
  - Orphans
- Useful columns: Name, Version, Size, Install Date, Origin
- Clear origin badges (core / extra / multilib / AUR / foreign)

### 2. Package Details Panel
When a package is selected, show:
- Description
- Version and available version (if upgradable)
- Size (download + installed)
- Homepage, licenses, architecture
- Dependencies
- Reverse dependencies ("required by" / "why is this installed?")
- List of installed files
- Origin / repository

### 3. Package Operations
- Install packages (from official repos or AUR)
- Remove packages (with option for recursive / dependency removal)
- System update (`pacman -Syu` + AUR updates if helper is present)
- Individual package updates
- Show the **exact command** that will be executed before running it
- Live terminal-style output of the operation
- Confirmation dialogs that show what will actually happen

### 4. Search Available Packages
- Search official repositories and AUR
- Show whether a package is already installed
- Quick install from search results

### 5. System Maintenance Tools
- Orphaned packages detection and cleanup
- Package cache cleaning (with size preview)
- Simple view of pending updates

## Quality-of-Life Features

- Dark theme that follows the system (libadwaita)
- Keyboard shortcuts for common actions
- Remember last window size and filter preferences
- Notifications when long operations finish
- Batch operations / simple queue
- Responsive and fast UI even with many packages

## Nice-to-Have Features (Later)

- Visual dependency graph (simple)
- Recently installed packages view
- Disk usage overview by packages
- Mirror ranking integration
- AUR voting / out-of-date flagging
- Optional Flatpak support

## Design Principles

1. **Transparency first** — Never hide what pacman/yay is doing. Show real commands and real output.
2. **Speed** — The installed package list should feel instant.
3. **Clarity over magic** — Prefer explicit actions over hidden automation.
4. **Safety** — Always show what will be changed before confirming destructive actions.
5. **Simple by default** — Advanced options should be available but not in the way.

## Suggested UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Header bar: Search | Update System | Menu             │
├──────────┬──────────────────────────────┬───────────────┤
│ Sidebar  │  Package list                │  Details      │
│          │                              │  panel        │
│ - Installed                             │               │
│ - Updates                               │               │
│ - Search                                │               │
│ - Orphans                               │               │
│ - Tools                                 │               │
│                                         │               │
└──────────┴──────────────────────────────┴───────────────┘
```

- Sidebar for navigation
- Main area for the package list with search and filters
- Right-side (or bottom) details panel
- Operations should open a dialog or bottom panel with live output

## Architecture Suggestions

```
app/
├── main.py                 # Application entry point
├── window.py               # Main Adw.ApplicationWindow
├── views/
│   ├── installed.py
│   ├── search.py
│   ├── updates.py
│   └── tools.py
├── widgets/
│   ├── package_list.py
│   ├── package_details.py
│   └── operation_dialog.py
├── backend/
│   ├── pacman.py           # Wrappers around pacman commands
│   ├── aur.py              # yay / paru detection and calls
│   └── parser.py           # Parse package info output
├── models/
│   └── package.py          # Package data class
└── utils/
    └── preferences.py
```

### Backend Notes
- Prefer parsing structured output when possible (`pacman -Q --info`, etc.)
- Run long operations in a background thread or async so the UI stays responsive
- Detect available AUR helper at startup
- Use `pkexec` or a polkit helper for privileged operations when needed

## Dependencies

Runtime:
- `python`
- `python-gobject`
- `gtk4`
- `libadwaita`
- `pacman`
- Optional: `yay` or `paru`

## Packaging Target

- Should be packagable as an AUR package
- Include a `.desktop` file
- Proper application ID (e.g. `com.example.ArchPkgManager`)

## Out of Scope (for now)

- Replacing pacman
- Full repository configuration GUI
- Complex transaction history
- Supporting non-Arch distributions

## Success Criteria

The application is successful if:
- A user can quickly see what is installed and search it
- Installing, removing, and updating packages feels clear and safe
- The real commands and output are visible
- It works smoothly on both Hyprland and KDE Plasma
- It feels faster and more transparent than existing GUI alternatives

---

## Development Notes for AI Assistants

- Prefer clean, readable Python
- Use type hints
- Keep the UI responsive (never block the main thread with package operations)
- Follow libadwaita design patterns
- Handle missing AUR helpers gracefully
- Add proper error handling around subprocess calls
- Make the code easy to extend later
