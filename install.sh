#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="user"
ACTION="install"

usage() {
  cat <<'EOF'
Install Lumina on Arch Linux.

Usage:
  ./install.sh              Install for the current user
  ./install.sh --system     Install for all users under /usr/local
  ./install.sh --uninstall  Remove the current-user install
  ./install.sh --system --uninstall
                            Remove the /usr/local install

The script installs Arch packages that Lumina needs, then installs the
application, desktop entry, and icons. Waybar and the app launcher use
that desktop entry.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      MODE="user"
      ;;
    --system)
      MODE="system"
      ;;
    --uninstall)
      ACTION="uninstall"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ ! -f /etc/os-release ]] || ! grep -Eq '^ID(_LIKE)?=.*arch' /etc/os-release; then
  echo "This installer is for Arch Linux." >&2
  exit 1
fi

if [[ "$MODE" == "system" && "${EUID}" -ne 0 ]]; then
  args=(--system)
  if [[ "$ACTION" == "uninstall" ]]; then
    args+=(--uninstall)
  fi
  exec sudo "$0" "${args[@]}"
fi

if [[ "$MODE" == "system" ]]; then
  BIN_DIR="/usr/local/bin"
  SHARE_DIR="/usr/local/share"
else
  BIN_DIR="${HOME}/.local/bin"
  SHARE_DIR="${HOME}/.local/share"
fi

APP_DIR="${SHARE_DIR}/lumina"
DESKTOP_FILE="${SHARE_DIR}/applications/com.github.lumina.desktop"
METAINFO_FILE="${SHARE_DIR}/metainfo/com.github.lumina.metainfo.xml"
ICON_NAME="com.github.lumina.png"
SIZES=(16x16 24x24 32x32 48x48 64x64 128x128 256x256 512x512)

remove_install() {
  rm -f "${BIN_DIR}/lumina"
  rm -rf "${APP_DIR}"
  rm -f "${DESKTOP_FILE}" "${METAINFO_FILE}"
  for size in "${SIZES[@]}"; do
    rm -f "${SHARE_DIR}/icons/hicolor/${size}/apps/${ICON_NAME}"
  done
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${SHARE_DIR}/applications" >/dev/null 2>&1 || true
  fi
  if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -f -t "${SHARE_DIR}/icons/hicolor" >/dev/null 2>&1 || true
  fi
  echo "Removed Lumina from ${BIN_DIR} and ${SHARE_DIR}."
}

if [[ "$ACTION" == "uninstall" ]]; then
  remove_install
  exit 0
fi

PACKAGES=(
  python
  python-gobject
  gtk4
  libadwaita
  gdk-pixbuf2
  libjxl
  polkit
  hicolor-icon-theme
  desktop-file-utils
)
missing=()
for package in "${PACKAGES[@]}"; do
  if ! pacman -Qi "$package" >/dev/null 2>&1; then
    missing+=("$package")
  fi
done
if ((${#missing[@]})); then
  echo "Installing packages: ${missing[*]}"
  sudo pacman -S --needed --noconfirm "${missing[@]}"
fi

rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}" "${BIN_DIR}" "${SHARE_DIR}/applications" "${SHARE_DIR}/metainfo"
cp -a "${ROOT}/lumina" "${APP_DIR}/lumina"
find "${APP_DIR}" -type d -name __pycache__ -prune -exec rm -rf {} + || true
find "${APP_DIR}" -type f -name '*.pyc' -delete || true

cat > "${BIN_DIR}/lumina" <<EOF
#!/usr/bin/env python3
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "share" / "lumina"
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from lumina.main import main

raise SystemExit(main())
EOF
chmod 755 "${BIN_DIR}/lumina"

for size in "${SIZES[@]}"; do
  install -Dm644 \
    "${ROOT}/lumina/icons/hicolor/${size}/apps/${ICON_NAME}" \
    "${SHARE_DIR}/icons/hicolor/${size}/apps/${ICON_NAME}"
done

cat > "${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Name=Lumina
Comment=Transparent package manager for Arch Linux
Exec=${BIN_DIR}/lumina
Icon=com.github.lumina
Terminal=false
Type=Application
Categories=System;PackageManager;
Keywords=pacman;aur;packages;arch;
StartupNotify=true
StartupWMClass=com.github.lumina
EOF
chmod 644 "${DESKTOP_FILE}"

install -Dm644 "${ROOT}/data/com.github.lumina.metainfo.xml" "${METAINFO_FILE}"

if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
  gtk4-update-icon-cache -f -t "${SHARE_DIR}/icons/hicolor" >/dev/null 2>&1 || true
elif command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "${SHARE_DIR}/icons/hicolor" >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${SHARE_DIR}/applications" >/dev/null 2>&1 || true
fi

echo "Lumina installed."
echo "Command: ${BIN_DIR}/lumina"
if [[ "$MODE" == "user" && ":${PATH}:" != *":${HOME}/.local/bin:"* ]]; then
  echo "Add ${HOME}/.local/bin to PATH if the lumina command is not found."
fi
echo "Restart Waybar, then launch Lumina from the app menu."
