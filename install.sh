#!/usr/bin/env bash
# Installs Clipboard Picker for the current user and binds it to Super+. (override with SHORTCUT=...)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/clipboard-picker"
BIN="$HOME/.local/bin/clipboard-picker"
AUTOSTART="$HOME/.config/autostart/clipboard-picker.desktop"
SHORTCUT="${SHORTCUT:-<Super>period}"
KEY_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clipboard-picker/"
MEDIA_KEYS="org.gnome.settings-daemon.plugins.media-keys"

echo "==> Installing dependencies (may ask for your password)"
sudo apt-get install -y python3-gi gir1.2-gtk-3.0 xdotool fonts-noto-color-emoji

echo "==> Copying app to $APP_DIR"
mkdir -p "$APP_DIR" "$(dirname "$BIN")" "$(dirname "$AUTOSTART")"
install -m 644 "$SRC/clipboard_picker.py" "$SRC/emoji_data.py" "$APP_DIR/"

# GDK_BACKEND=x11: on GNOME Wayland this runs us through XWayland, which (unlike native
# Wayland) lets a background app see clipboard changes.
cat > "$BIN" <<EOF
#!/usr/bin/env bash
export GDK_BACKEND=x11
exec python3 "$APP_DIR/clipboard_picker.py" "\$@"
EOF
chmod +x "$BIN"

echo "==> Enabling autostart at login"
cat > "$AUTOSTART" <<EOF
[Desktop Entry]
Type=Application
Name=Clipboard Picker
Comment=Emoji and clipboard history popup (Super+.)
Exec=$BIN --hidden
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF

if gsettings list-schemas | grep -qx "$MEDIA_KEYS"; then
    echo "==> Binding keyboard shortcut $SHORTCUT"
    # IBus's own emoji picker uses Super+. by default — free it up.
    if [[ "$SHORTCUT" == "<Super>period" ]] && gsettings list-schemas | grep -qx org.freedesktop.ibus.panel.emoji; then
        gsettings set org.freedesktop.ibus.panel.emoji hotkey "[]"
    fi
    SCHEMA="$MEDIA_KEYS.custom-keybinding:$KEY_PATH"
    gsettings set "$SCHEMA" name "Clipboard Picker"
    gsettings set "$SCHEMA" command "$BIN"
    gsettings set "$SCHEMA" binding "$SHORTCUT"
    current="$(gsettings get "$MEDIA_KEYS" custom-keybindings)"
    updated="$(python3 - "$current" "$KEY_PATH" <<'PY'
import ast, sys
paths = ast.literal_eval(sys.argv[1].replace("@as ", "") or "[]")
if sys.argv[2] not in paths:
    paths.append(sys.argv[2])
print(paths)
PY
)"
    gsettings set "$MEDIA_KEYS" custom-keybindings "$updated"
else
    echo "!!  Not a GNOME desktop: bind a shortcut to '$BIN' in your keyboard settings manually."
fi

echo "==> Starting the background service"
"$BIN" --quit >/dev/null 2>&1 || true
nohup "$BIN" --hidden >/dev/null 2>&1 &
disown

echo
echo "Done! Press Super + .  (Windows key + period) to open Clipboard Picker."
