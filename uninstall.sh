#!/usr/bin/env bash
# Removes a per-user install of Clipboard Picker (made by install.sh).
# Pass --purge to also delete your saved clipboard history.
# Installed the .deb instead? Run:  clipboard-picker --remove-setup --quit && sudo apt remove clipboard-picker
set -uo pipefail

APP_ID="io.github.ClipboardPicker"
APP_DIR="$HOME/.local/share/clipboard-picker"
BIN="$HOME/.local/bin/clipboard-picker"

# Removes the shortcut, gives Super+. back to IBus and stops the background app.
[[ -x "$BIN" ]] && "$BIN" --remove-setup --quit >/dev/null 2>&1

rm -f "$BIN" "$HOME/.config/autostart/clipboard-picker.desktop" \
      "$HOME/.local/share/applications/$APP_ID.desktop" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg" \
      "$APP_DIR/"*.py
rm -rf "$APP_DIR/__pycache__"

if [[ "${1:-}" == "--purge" ]]; then
    rm -rf "$APP_DIR"
    echo "Removed Clipboard Picker and its history."
else
    echo "Removed Clipboard Picker (history kept in $APP_DIR; use --purge to delete it)."
fi
