# Ubuntu Emoji & Clipboard Picker

A Windows **Win + .** style popup for Ubuntu. Press **Super + .** (the Windows key + period) and get two tabs:

- **😀 Emoji**: about 450 emoji in 7 categories, plus a "Recently used" row and keyword search.
- **📋 History**: every piece of text you copy. Pin items to keep them forever; the newest 100 unpinned items are kept.

Pick an item and it goes onto the clipboard. On an Xorg session it is also pasted into the window you were in.

## Requirements

- Ubuntu 20.04 or newer, or another GNOME-based distro. Other desktops work, but you bind the shortcut yourself.
- Python 3 with GTK 3 bindings. The installer adds these with `apt` if they're missing, which needs `sudo`.

## Install

On the Ubuntu machine, open a terminal and run:

```bash
sudo apt install -y git
git clone https://github.com/CarolDsillva/ubuntu-emoji-clipboard.git
cd ubuntu-emoji-clipboard
./install.sh
```

Then press **Super + .** 🎉

The installer:
1. Installs `python3-gi`, `gir1.2-gtk-3.0`, `xdotool` and `fonts-noto-color-emoji`. These are usually already present.
2. Copies the app to `~/.local/share/clipboard-picker` and adds a launcher at `~/.local/bin/clipboard-picker`.
3. Sets the app to start at login (in the background) and starts it right away.
4. Binds **Super + .** as a GNOME custom shortcut. Ubuntu's built-in IBus emoji picker also uses this key, so the installer turns that one off.

To use a different key, run `SHORTCUT='<Super>v' ./install.sh` instead.

### Update

```bash
cd ubuntu-emoji-clipboard && git pull && ./install.sh
```

### Uninstall

```bash
./uninstall.sh
```

Add `--purge` to also delete the saved history. Uninstalling also gives Super + . back to IBus.

## Keyboard

| Key | Action |
|---|---|
| Super + . | Open / close |
| Type anything | Search (both tabs) |
| ↓ / arrows | Move into the results |
| Enter | Pick the first result (or the focused one) |
| Ctrl + Tab, Ctrl + 1 / 2 | Switch tabs |
| Del | Delete the focused history item |
| Esc | Clear the search, then close |

## Wayland vs Xorg

Ubuntu uses **Wayland** by default. Wayland doesn't let background apps read the clipboard. To get around this, the launcher runs the app through XWayland (`GDK_BACKEND=x11`), which normally can still see clipboard changes. Under Wayland:

- The popup opens in the middle of the screen, not at the mouse.
- **Auto-paste doesn't work** in native Wayland apps. The item is still copied, so just press **Ctrl + V**.

For the full Windows-like behaviour (opens at the mouse, pastes automatically), choose **"Ubuntu on Xorg"** from the ⚙ gear on the login screen. To check which session you're on, run:

```bash
echo $XDG_SESSION_TYPE
```

Terminals paste with Ctrl + Shift + V, so auto-paste won't work in them. Press Ctrl + Shift + V yourself.

## Settings

Edit the constants at the top of `clipboard_picker.py` (`MAX_HISTORY`, `AUTO_PASTE`, `WIDTH`/`HEIGHT`, and so on), then run `./install.sh` again. The installer also restarts the app.

To add emoji, add lines to `emoji_data.py`. Each line is an emoji followed by its search keywords.

## Preview on Windows / macOS

The app itself needs Linux, but you can try a browser mock-up of it anywhere:

```bash
python make_preview.py
```

Then open the `preview.html` it creates. The page reads `emoji_data.py` and the settings in `clipboard_picker.py`, so rebuild it after editing them. **Show code map** labels each part of the popup with the Python class or function that controls it. Layout and styling changes have to be made in both `clipboard_picker.py` and `preview_template.html`.

## Project layout

| File | What it is |
|---|---|
| `clipboard_picker.py` | The app (Python + GTK 3): background daemon, clipboard watcher, popup window |
| `emoji_data.py` | Emoji list and search keywords |
| `install.sh` / `uninstall.sh` | Per-user install: dependencies, launcher, autostart, keyboard shortcut |
| `make_preview.py` + `preview_template.html` | Build the browser preview |

## Privacy

History is saved in `~/.local/share/clipboard-picker/history.json` with permissions `600`, so only your user can read it. It never leaves your machine. Passwords you copy **will** be saved, so delete them with ✕ or **Clear all**.

## Troubleshooting

- **The shortcut does nothing:** run `clipboard-picker` in a terminal and read any error. Also check *Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts* for "Clipboard Picker" set to `Super+.`.
- **History stays empty on Wayland:** your GNOME version probably blocks XWayland clipboard access. Switch to "Ubuntu on Xorg" (see above).
- **`Permission denied` running `./install.sh`:** run `chmod +x install.sh uninstall.sh` first, or use `bash install.sh`.

## License

[MIT](LICENSE)
