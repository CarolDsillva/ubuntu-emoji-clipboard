#!/usr/bin/env bash
# CI smoke test for the *installed* app: runs it on a virtual X display with a private D-Bus
# session, checks first-run setup, clipboard history and picking, and saves screenshots.
#   packaging/smoke-test.sh [screenshot-dir]
# Needs: xvfb, dbus, xclip, xdotool, imagemagick, dconf (for gsettings to persist).
set -euo pipefail

if [[ -z "${SMOKE_INNER:-}" ]]; then
    export SMOKE_INNER=1
    exec xvfb-run -a -s "-screen 0 1024x768x24" dbus-run-session -- bash "$0" "$@"
fi

SHOTS="$(realpath -m "${1:-dist/screenshots}")"
mkdir -p "$SHOTS"
HIST="$HOME/.local/share/clipboard-picker/history.json"
KEYPATH=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/clipboard-picker/
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; exit 1; }
win() { xdotool search --onlyvisible --name '^Clipboard Picker$' 2>/dev/null | head -1; }
clip() { xclip -o -selection clipboard 2>/dev/null || true; }
shot() { sleep 0.8; import -window root "$SHOTS/$1.png"; echo "screenshot: $1.png"; }

rm -rf "$HOME/.local/share/clipboard-picker"

# 1. Daemon starts and does first-run setup
clipboard-picker --hidden &
DAEMON=$!
sleep 3
kill -0 "$DAEMON" 2>/dev/null || fail "daemon exited on start"
pass "daemon running"
[[ -f "$HOME/.local/share/clipboard-picker/setup-done" ]] || fail "first-run setup did not run"
if gsettings list-schemas | grep -qx org.gnome.settings-daemon.plugins.media-keys; then
    gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings | grep -q "$KEYPATH" \
        || fail "shortcut not registered"
    [[ "$(gsettings get "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEYPATH" binding)" == "'<Super>period'" ]] \
        || fail "shortcut is not Super+."
    [[ "$(gsettings get "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEYPATH" command)" == "'/usr/bin/clipboard-picker'" ]] \
        || fail "shortcut command is not /usr/bin/clipboard-picker"
    pass "Super+. shortcut bound"
fi
if gsettings list-schemas | grep -qx org.freedesktop.ibus.panel.emoji; then
    [[ "$(gsettings get org.freedesktop.ibus.panel.emoji hotkey)" == "@as []" ]] || fail "IBus hotkey not cleared"
    pass "IBus emoji hotkey cleared"
fi

# 2. Copied text lands in history
printf 'Meeting moved to 3:30 PM' | xclip -selection clipboard
sleep 2
printf 'hello from CI' | xclip -selection clipboard
sleep 2
grep -q 'hello from CI' "$HIST" 2>/dev/null || fail "copied text not recorded in history"
pass "clipboard history records copies"

# 3. Popup opens, searches, switches tabs
clipboard-picker
sleep 1.5
W="$(win)"; [[ -n "$W" ]] || fail "popup did not open"
xdotool windowfocus --sync "$W"
pass "popup opens"
shot 1-emoji-tab
xdotool type --delay 60 heart
shot 2-emoji-search
xdotool key Escape key ctrl+2
shot 3-history-tab

# 4. Enter picks the first emoji result and puts it on the clipboard
xdotool key ctrl+1 && xdotool type --delay 60 thumbs && sleep 0.5 && xdotool key Return
sleep 1
[[ -z "$(win)" ]] || fail "popup did not close after picking"
[[ "$(clip)" == "👍" ]] || fail "expected 👍 on the clipboard, got '$(clip)'"
pass "picking an emoji copies it and closes the popup"

# 5. Picking from history
clipboard-picker; sleep 1.5; W="$(win)"; xdotool windowfocus --sync "$W"
xdotool key ctrl+2 && xdotool type --delay 60 meeting && sleep 0.5 && xdotool key Return
sleep 1
[[ "$(clip)" == "Meeting moved to 3:30 PM" ]] || fail "history pick gave '$(clip)'"
pass "picking from history copies it"

# 6. Esc closes; --remove-setup --quit cleans up and stops the daemon
clipboard-picker; sleep 1.5; W="$(win)"; xdotool windowfocus --sync "$W"; xdotool key Escape; sleep 0.5
[[ -z "$(win)" ]] || fail "Esc did not close the popup"
pass "Esc closes the popup"
clipboard-picker --remove-setup --quit
sleep 1
! kill -0 "$DAEMON" 2>/dev/null || fail "daemon still running after --quit"
if gsettings list-schemas | grep -qx org.gnome.settings-daemon.plugins.media-keys; then
    ! gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings | grep -q "$KEYPATH" \
        || fail "shortcut still registered after --remove-setup"
fi
pass "--remove-setup --quit"
echo "All smoke tests passed."
