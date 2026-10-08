# Ubuntu Emoji & Clipboard Picker

A Windows **Win + .** style popup for Ubuntu. Press **Super + .** (the Windows key + period) and get two tabs:

- **😀 Emoji**: about 450 emoji in 7 categories, plus a "Recently used" row and keyword search.
- **📋 History**: every piece of text you copy. Pin items to keep them forever; the newest 100 unpinned items are kept.

Pick an item and it goes onto the clipboard. On an Xorg session it is also pasted into the window you were in.

Works on Ubuntu 20.04 or newer, and other GNOME-based distros. On other desktops it works too, but you bind the shortcut yourself.

## Install

Pick **one** of these.

### Option A: Download the installer package (recommended)

1. Download **[clipboard-picker_all.deb](https://github.com/CarolDsillva/ubuntu-emoji-clipboard/releases/latest/download/clipboard-picker_all.deb)**.
2. Install it. Either open a terminal in your Downloads folder and run:
   ```bash
   sudo apt install ./clipboard-picker_all.deb
   ```
   or right-click the file and choose **Open With → Software Install** / **App Center**.
3. Open **Clipboard Picker** from your app menu once, or log out and back in.
4. Press **Super + .** (the Windows key + period) 🎉

The first time it runs for each user, it sets up the **Super + .** shortcut and shows a "ready" notification. After that it starts automatically at login.

**Update:** download and install the new `.deb` the same way.
**Uninstall:**
```bash
clipboard-picker --remove-setup --quit && sudo apt remove clipboard-picker
```

### Option B: One-line install (no admin rights needed)

Open a terminal and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/CarolDsillva/ubuntu-emoji-clipboard/main/install.sh | bash
```

This installs for your user only, in `~/.local`. It only asks for your password if a needed system package is missing, and on a standard Ubuntu desktop it usually isn't. To use a different key, put `SHORTCUT='<Super>v'` in front of `bash`, like this: `... | SHORTCUT='<Super>v' bash`.

**Update:** run the same command again.
**Uninstall:**
```bash
curl -fsSL https://raw.githubusercontent.com/CarolDsillva/ubuntu-emoji-clipboard/main/uninstall.sh | bash
```

Add `-s -- --purge` after `bash` to also delete your saved history.

### Option C: From a clone (for developers)

```bash
git clone https://github.com/CarolDsillva/ubuntu-emoji-clipboard.git
cd ubuntu-emoji-clipboard && ./install.sh
```

To update, run `git pull && ./install.sh`. To uninstall, run `./uninstall.sh`.

### Changing the shortcut later

Use *Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts → Clipboard Picker*, or run:

```bash
CLIPBOARD_PICKER_SHORTCUT='<Super>v' clipboard-picker --setup
```

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

Edit the constants at the top of `clipboard_picker.py` (`MAX_HISTORY`, `AUTO_PASTE`, `WIDTH`/`HEIGHT`, and so on), then run `./install.sh` again from your clone. The installer also restarts the app.

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
| `install.sh` / `uninstall.sh` | Per-user install (Options B and C) |
| `packaging/` | Launcher, app-menu and autostart entries, icon, `.deb` builder, CI smoke test |
| `.github/workflows/build.yml` | Builds the `.deb`, tests it on Ubuntu, and publishes releases |
| `make_preview.py` + `preview_template.html` | Build the browser preview |

## Releasing a new version (maintainer)

Every push to `main` builds the `.deb`, installs it on a fresh Ubuntu machine, and runs [`packaging/smoke-test.sh`](packaging/smoke-test.sh) on a virtual display. The run also saves screenshots of the popup. To publish a release that users can download, tag it:

```bash
git tag v1.0.0 && git push origin v1.0.0
```

The workflow then attaches `clipboard-picker_all.deb` to a GitHub Release. The download link in Option A always points to the newest release.

## Privacy

History is saved in `~/.local/share/clipboard-picker/history.json` with permissions `600`, so only your user can read it. It never leaves your machine. Passwords you copy **will** be saved, so delete them with ✕ or **Clear all**.

## Troubleshooting

- **The shortcut does nothing:** run `clipboard-picker` in a terminal and read any error. Also check *Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts* for "Clipboard Picker" set to `Super+.`.
- **History stays empty on Wayland:** your GNOME version probably blocks XWayland clipboard access. Switch to "Ubuntu on Xorg" (see above).
- **`Permission denied` running `./install.sh`:** run `chmod +x install.sh uninstall.sh` first, or use `bash install.sh`.

## License

[MIT](LICENSE)
