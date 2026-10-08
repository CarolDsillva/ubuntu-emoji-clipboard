#!/usr/bin/env bash
# Removes Clipboard Picker. Pass --purge to also delete your saved clipboard history.
set -uo pipefail

BIN="$HOME/.local/bin/clipboard-picker"
KEY_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clipboard-picker/"
MEDIA_KEYS="org.gnome.settings-daemon.plugins.media-keys"

[[ -x "$BIN" ]] && "$BIN" --quit >/dev/null 2>&1

if gsettings list-schemas | grep -qx "$MEDIA_KEYS"; then
    current="$(gsettings get "$MEDIA_KEYS" custom-keybindings)"
    updated="$(python3 - "$current" "$KEY_PATH" <<'PY'
import ast, sys
paths = ast.literal_eval(sys.argv[1].replace("@as ", "") or "[]")
print([p for p in paths if p != sys.argv[2]])
PY
)"
    gsettings set "$MEDIA_KEYS" custom-keybindings "$updated"
    for key in name command binding; do
        gsettings reset "$MEDIA_KEYS.custom-keybinding:$KEY_PATH" "$key"
    done
    if gsettings list-schemas | grep -qx org.freedesktop.ibus.panel.emoji; then
        gsettings reset org.freedesktop.ibus.panel.emoji hotkey  # give Super+. back to IBus
    fi
fi

rm -f "$BIN" "$HOME/.config/autostart/clipboard-picker.desktop"
rm -f "$HOME/.local/share/clipboard-picker/"*.py
rm -rf "$HOME/.local/share/clipboard-picker/__pycache__"

if [[ "${1:-}" == "--purge" ]]; then
    rm -rf "$HOME/.local/share/clipboard-picker"
    echo "Removed Clipboard Picker and its history."
else
    rmdir "$HOME/.local/share/clipboard-picker" 2>/dev/null
    echo "Removed Clipboard Picker (history kept in ~/.local/share/clipboard-picker; use --purge to delete)."
fi
