#!/usr/bin/env bash
# Installs Clipboard Picker for the current user (no root needed unless dependencies are missing).
#
#   Without cloning:  curl -fsSL https://raw.githubusercontent.com/CarolDsillva/ubuntu-emoji-clipboard/main/install.sh | bash
#   From a checkout:  ./install.sh
#
# SHORTCUT='<Super>v' picks another key (default Super+.). CLIPBOARD_PICKER_REF picks the
# branch or tag to download (default main).
set -euo pipefail

REPO="CarolDsillva/ubuntu-emoji-clipboard"
REF="${CLIPBOARD_PICKER_REF:-main}"
SHORTCUT="${SHORTCUT:-<Super>period}"
APP_ID="io.github.ClipboardPicker"
FILES=(clipboard_picker.py emoji_data.py packaging/clipboard-picker
       packaging/$APP_ID.desktop packaging/clipboard-picker-autostart.desktop packaging/$APP_ID.svg)

APP_DIR="$HOME/.local/share/clipboard-picker"
BIN="$HOME/.local/bin/clipboard-picker"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
AUTOSTART="$HOME/.config/autostart"
TMP=""

# Everything runs from main() so a half-downloaded `curl | bash` never runs a partial script.
main() {
    local src
    src="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)"
    if [[ ! -f "$src/clipboard_picker.py" || ! -d "$src/packaging" ]]; then
        TMP="$(mktemp -d)"
        trap 'rm -rf "$TMP"' EXIT
        echo "==> Downloading Clipboard Picker ($REF)"
        for f in "${FILES[@]}"; do
            mkdir -p "$TMP/$(dirname "$f")"
            curl -fsSL "https://raw.githubusercontent.com/$REPO/$REF/$f" -o "$TMP/$f"
        done
        src="$TMP"
    fi

    local missing=()
    for pkg in python3-gi gir1.2-gtk-3.0 xdotool fonts-noto-color-emoji; do
        dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
    done
    if ((${#missing[@]})); then
        echo "==> Installing ${missing[*]} (may ask for your password)"
        sudo apt-get install -y "${missing[@]}"
    fi

    echo "==> Installing to $APP_DIR"
    mkdir -p "$APP_DIR" "$(dirname "$BIN")" "$APPS" "$ICONS" "$AUTOSTART"
    install -m 644 "$src/clipboard_picker.py" "$src/emoji_data.py" "$APP_DIR/"
    sed "s|@APP_DIR@|$APP_DIR|g" "$src/packaging/clipboard-picker" > "$BIN"
    chmod 755 "$BIN"
    # ~/.local/bin may not be on PATH until the next login, so point the desktop files at it directly.
    sed "s|^Exec=clipboard-picker|Exec=$BIN|" "$src/packaging/$APP_ID.desktop" > "$APPS/$APP_ID.desktop"
    sed "s|^Exec=clipboard-picker|Exec=$BIN|" "$src/packaging/clipboard-picker-autostart.desktop" \
        > "$AUTOSTART/clipboard-picker.desktop"
    install -m 644 "$src/packaging/$APP_ID.svg" "$ICONS/"

    echo "==> Starting it and binding $SHORTCUT"
    "$BIN" --quit >/dev/null 2>&1 || true
    sleep 1
    CLIPBOARD_PICKER_SHORTCUT="$SHORTCUT" nohup "$BIN" --setup </dev/null >/dev/null 2>&1 &

    echo
    echo "Done! Press Super + .  (Windows key + period) to open Clipboard Picker."
}

main "$@"
