# Lumina — Feature & Build Plan

**App:** Lumina (`com.github.lumina`)  
**Stack:** Python 3 + GTK4 + libadwaita (PyGObject)  
**Privileges:** `pkexec pacman …`  
**AUR:** detect `yay` / `paru` at startup  
**Repo state:** greenfield (only `PROJECT.md` at plan time)

---

## 1. Product principles (non-negotiable)

1. Show the **exact command** before any destructive/privileged op
2. Stream **real stdout/stderr** in a terminal-style view
3. Never block the GTK main thread (threads + idle callbacks / GLib)
4. Graceful degradation if no AUR helper
5. Type hints, clear modules, easy to extend

---

## 2. Feature plan (phased)

### Phase 0 — Project skeleton (buildable empty app)

- Package layout, entry point, `Adw.Application` + main window
- Sidebar shell + placeholder pages
- Runnable via `python -m lumina`
- `.desktop`, metainfo stub, README
- App ID: `com.github.lumina`

### Phase 1 — MVP (first shippable)

| Feature | Details |
|--------|---------|
| **Installed packages list** | Load via `pacman -Q` / `-Qi` parsing; efficient list |
| **Fuzzy search** | Filter list as you type (name + description) |
| **Filters** | All · Explicit · Official · AUR/foreign · Orphans |
| **Columns / rows** | Name, version, size, origin badge |
| **Details panel** | Description, version, size, deps, required-by, origin, homepage, license |
| **Remove** | Confirm dialog with exact command; `pkexec pacman -R` / `-Rs` option; live output |
| **AUR detection** | Startup: prefer `paru` then `yay` (or first found); show in About/status |
| **AUR origin** | Mark foreign packages; optional helper info when useful |
| **Prefs** | Window size; last filter (GSettings or simple JSON) |

**MVP success:** open app → see packages instantly → search/filter → select → details → remove with visible command + live log.

### Phase 2 — Core operations

- Search official repos (`pacman -Ss`) + AUR (helper)
- Install from search (`pkexec pacman -S` / helper)
- System update (`pacman -Syu` + AUR helper `-Syu`)
- Per-package upgrade when newer version exists
- Pending updates view
- Batch queue (simple serial queue)

### Phase 3 — Maintenance tools

- Orphans list + cleanup
- Cache clean with size preview (`paccache` / `pacman -Sc`)
- Notifications on long op finish
- Keyboard shortcuts

### Phase 4 — Nice-to-have (later)

- Dependency graph, recently installed, disk-by-package, mirrors, AUR votes, Flatpak

---

## 3. Target architecture

```
lumina/
├── meson.build                 # optional; or pyproject + scripts
├── data/
│   ├── com.github.lumina.desktop
│   ├── com.github.lumina.metainfo.xml
│   └── com.github.lumina.gschema.xml   # if GSettings
├── lumina/
│   ├── __init__.py
│   ├── __main__.py             # python -m lumina
│   ├── main.py                 # Adw.Application
│   ├── window.py               # Adw.ApplicationWindow + NavigationSplitView
│   ├── models/
│   │   └── package.py          # Package dataclass
│   ├── backend/
│   │   ├── pacman.py           # query + command builders
│   │   ├── aur.py              # helper detect + thin wrappers
│   │   ├── parser.py           # parse -Qi / -Si style blocks
│   │   └── runner.py           # async subprocess + pkexec
│   ├── views/
│   │   ├── installed.py
│   │   ├── search.py           # Phase 2 stub
│   │   ├── updates.py          # Phase 2 stub
│   │   └── tools.py            # Phase 3 stub
│   ├── widgets/
│   │   ├── package_list.py
│   │   ├── package_details.py
│   │   ├── filter_bar.py
│   │   └── operation_dialog.py # command preview + live log
│   └── utils/
│       ├── preferences.py
│       └── threading.py        # run_in_thread helpers
├── tests/
│   ├── test_parser.py
│   └── fixtures/               # sample pacman -Qi output
├── PROJECT.md
├── PLAN.md
└── README.md
```

### UI shell (libadwaita)

```
Adw.ApplicationWindow
└── Adw.NavigationSplitView (or Leaflet/BreakpointBin for narrow)
    ├── Sidebar: Adw.ViewStack sidebar list
    │     Installed | Updates | Search | Orphans | Tools
    └── Content:
          Header: search entry + primary actions
          Center: PackageList (Gtk.ListView + Gio.ListStore / custom filter model)
          End: PackageDetails (Adw.Clamp + preferences-group style rows)
```

Operations → modal `Adw.Dialog` / `Adw.AlertDialog`:

1. Summary of changes
2. Exact command monospaced
3. Confirm → spawn process, append log to `Gtk.TextView`
4. Done / error state

---

## 4. Backend design

### Package model

```python
@dataclass
class Package:
    name: str
    version: str
    description: str = ""
    repo: str | None = None      # core/extra/multilib/None
    origin: Origin               # OFFICIAL | AUR | FOREIGN | LOCAL
    install_date: datetime | None = None
    installed_size: int | None = None   # bytes
    depends: list[str] = field(default_factory=list)
    required_by: list[str] = field(default_factory=list)
    explicit: bool = False
    orphan: bool = False
```

### Query strategy (speed)

1. **Fast path:** `pacman -Q` → names+versions for list
2. **Enrich:** `pacman -Qi` (batch or on-demand) for details; cache in memory
3. **Classification:**
   - Explicit: `pacman -Qe`
   - Foreign/AUR-ish: `pacman -Qm`
   - Orphans: `pacman -Qdt`
   - Repo origin: parse `Repository` from `-Qi`
4. Details on selection: full `-Qi` if not cached (background thread)

### Commands (MVP remove)

| Action | Command pattern |
|--------|-----------------|
| Remove | `pkexec pacman -R --noconfirm {pkgs}` |
| Remove + deps | `pkexec pacman -Rs --noconfirm {pkgs}` |
| Queries | unprivileged `pacman -Q…` |

**Note:** `--noconfirm` only after user confirmed in GUI. Never hide the full argv.

### AUR (Phase 1 light + Phase 2 ops)

- `shutil.which("paru")` then `yay`
- Phase 1: label foreign pkgs; optional helper `-Qi` for richer info
- Phase 2: `{helper} -Ss`, `-S`, `-Syu` (helpers often prompt; may need helper-specific flags later)

### Runner

- `subprocess.Popen` in worker thread
- Line-buffered read → `GLib.idle_add` to UI
- Capture exit code; map common pacman failures to short messages
- Cancel: best-effort terminate (document limits with pkexec)

---

## 5. Implementation order (ready to build)

| Step | Deliverable | Done when |
|------|-------------|-----------|
| **1** | Skeleton: `lumina` package, Adw app, window, sidebar placeholders | `python -m lumina` opens themed window |
| **2** | `parser.py` + `Package` + unit tests on fixtures | Parses real `-Qi` blocks |
| **3** | `pacman.py` list/classify APIs | Returns installed set + filters in REPL/tests |
| **4** | `PackageList` + fuzzy filter model | UI lists all installed packages, search works |
| **5** | `PackageDetails` | Selection fills details |
| **6** | `runner.py` + `OperationDialog` | Dry-run UI shows command; fake or real log |
| **7** | Remove flow end-to-end | Confirm → pkexec → live output → refresh list |
| **8** | `aur.py` detect + origin badges | Status shows helper; foreign marked |
| **9** | Preferences + desktop file | Window size persists; launchable from menu |
| **10** | README + run instructions | Clone → install deps → run |

Phase 2+ stays stub pages until MVP is solid.

---

## 6. Technical decisions

| Topic | Decision |
|-------|----------|
| App ID | `com.github.lumina` |
| Name | Lumina |
| Python packaging | `pyproject.toml` + `lumina` package; optional Meson later for AUR |
| UI toolkit | GTK4 + libadwaita only (no custom CSS unless needed) |
| List widget | `Gtk.ListView` + filter model for search/filters |
| Async | `threading` + `GLib.idle_add` (no asyncio required for MVP) |
| Config | JSON in `~/.config/lumina/` or GSettings schema |
| Privileges | `pkexec` only for mutating pacman; queries as user |
| Testing | Parser + pure backend unit tests; manual UI on Arch |
| i18n | Defer; keep strings in one place for later gettext |

---

## 7. Runtime dependencies

- `python`, `python-gobject`, `gtk4`, `libadwaita`, `pacman`, `polkit`
- Optional: `paru` or `yay`
- Dev: `pytest` for parser/backend

---

## 8. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Slow `-Qi` for thousands of pkgs | Two-phase load; details on demand; cache |
| pkexec auth UX on Hyprland | Document polkit agent requirement |
| AUR helpers interactive prompts | Phase 2: non-interactive flags where safe; else show guidance |
| Partial remove failures | Keep full log; refresh installed DB after exit |
| Fuzzy search lag | Debounce search entry; filter in Python on cached list first |

---

## 9. Out of scope until later

- Replacing pacman
- Full repository configuration GUI
- Complex transaction history
- Supporting non-Arch distributions
- Flatpak
- Dependency graphs

---

## 10. Definition of “ready to build”

Implementation starts at **Step 1** and targets a **runnable MVP (Steps 1–10)** first. Phase 2+ is planned but not implemented until MVP is solid.

**First implementation after this plan:** scaffold `lumina/` package + empty Adw window + README, then parser/backend, then installed view.
