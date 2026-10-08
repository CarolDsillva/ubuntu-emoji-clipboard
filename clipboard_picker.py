#!/usr/bin/env python3
"""Clipboard Picker — a Windows "Win + ." style popup for Ubuntu.

Two tabs: Emoji and clipboard History. Runs as a single background instance that
records everything you copy; running the command again toggles the popup.

    clipboard_picker.py            toggle the popup (starts the daemon if needed)
    clipboard_picker.py --hidden   start the background daemon without showing
    clipboard_picker.py --quit     stop the running daemon
"""
import json
import os
import shutil
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emoji_data import CATEGORIES  # noqa: E402

APP_ID = "io.github.ClipboardPicker"
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "clipboard-picker")
STATE_FILE = os.path.join(DATA_DIR, "history.json")

MAX_HISTORY = 100          # unpinned entries kept; pinned entries never expire
MAX_RECENT_EMOJI = 18
MAX_ITEM_CHARS = 100_000   # ignore huge copies (e.g. whole files)
POLL_MS = 1000             # fallback clipboard polling interval
AUTO_PASTE = True          # paste into the previous window after picking
WIDTH, HEIGHT = 380, 460

IS_X11_SESSION = os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11"

CSS = b"""
.picker { border: 1px solid alpha(@theme_fg_color, 0.18); }
.picker stackswitcher button { padding: 4px 10px; }
.category-bar button { padding: 2px 4px; min-width: 0; font-size: 15px; }
.section-title { font-weight: bold; font-size: 11px; opacity: 0.65; margin: 8px 4px 2px 4px; }
flowboxchild.emoji-cell { padding: 3px; border-radius: 6px; }
flowboxchild.emoji-cell:hover, flowboxchild.emoji-cell:focus {
    background-color: alpha(@theme_selected_bg_color, 0.30);
}
.emoji-cell label { font-size: 21px; }
.history-row { padding: 6px 4px 6px 8px; border-bottom: 1px solid alpha(@theme_fg_color, 0.08); }
.history-row.pinned { background-color: alpha(@theme_selected_bg_color, 0.12); }
.history-time { font-size: 10px; opacity: 0.6; }
.history-row button { padding: 0 4px; min-height: 0; min-width: 0; }
.dim { opacity: 0.6; }
"""


# --------------------------------------------------------------------------- storage

class Store:
    def __init__(self):
        self.history = []        # [{"text": str, "pinned": bool, "time": float}], newest first
        self.recent_emoji = []
        self._load()

    def _load(self):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self.history = [h for h in data.get("history", [])
                            if isinstance(h, dict) and isinstance(h.get("text"), str)]
            self.recent_emoji = list(data.get("recent_emoji", []))
        except (OSError, ValueError):
            pass

    def save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"history": self.history, "recent_emoji": self.recent_emoji}, f, ensure_ascii=False)
        os.chmod(tmp, 0o600)  # clipboard contents can be sensitive
        os.replace(tmp, STATE_FILE)

    def _find(self, text):
        return next((h for h in self.history if h["text"] == text), None)

    def add_text(self, text):
        """Add (or move to the top) a copied text. Returns True if history changed."""
        if not text or not text.strip() or len(text) > MAX_ITEM_CHARS:
            return False
        existing = self._find(text)
        if existing:
            self.history.remove(existing)
        self.history.insert(0, {"text": text, "pinned": bool(existing and existing["pinned"]),
                                "time": time.time()})
        unpinned = [h for h in self.history if not h["pinned"]]
        for old in unpinned[MAX_HISTORY:]:
            self.history.remove(old)
        self.save()
        return True

    def set_pinned(self, text, pinned):
        item = self._find(text)
        if item:
            item["pinned"] = pinned
            self.save()

    def remove(self, text):
        item = self._find(text)
        if item:
            self.history.remove(item)
            self.save()

    def clear_unpinned(self):
        self.history = [h for h in self.history if h["pinned"]]
        self.save()

    def add_recent_emoji(self, emoji):
        if emoji in self.recent_emoji:
            self.recent_emoji.remove(emoji)
        self.recent_emoji.insert(0, emoji)
        del self.recent_emoji[MAX_RECENT_EMOJI:]
        self.save()


# --------------------------------------------------------------------------- helpers

def time_ago(ts):
    secs = max(0, time.time() - ts)
    if secs < 60:
        return "just now"
    for unit, size in (("d", 86400), ("h", 3600), ("min", 60)):
        if secs >= size:
            return f"{int(secs // size)} {unit} ago"
    return ""


def paste_into_focused_window():
    """Simulate Ctrl+V in whatever window regained focus. Best effort."""
    if IS_X11_SESSION and shutil.which("xdotool"):
        subprocess.Popen(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
    elif shutil.which("ydotool"):
        # Linux keycodes: 29 = LeftCtrl, 47 = V (needs ydotoold running)
        subprocess.Popen(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return False  # one-shot GLib timeout


# --------------------------------------------------------------------------- emoji tab

class EmojiSection:
    def __init__(self, title, header, flowbox):
        self.title = title
        self.header = header
        self.flowbox = flowbox
        self.cells = []  # [(FlowBoxChild, emoji, keywords)]


class EmojiPage(Gtk.Box):
    def __init__(self, on_pick, store):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_pick = on_pick
        self.store = store
        self.query = ""
        self.keywords = {}

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=True)
        bar.get_style_context().add_class("category-bar")
        self.pack_start(bar, False, False, 0)

        self.scroller = Gtk.ScrolledWindow(vexpand=True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=6)
        self.scroller.add(self.content)
        self.pack_start(self.scroller, True, True, 0)

        self.recent = self._add_section("Recently used")
        self._add_bar_button(bar, "🕘", self.recent)
        self.sections = [self.recent]
        for name, icon, items in CATEGORIES:
            section = self._add_section(name)
            for emoji, keys in items:
                self.keywords[emoji] = f"{keys} {name}".lower()
                self._add_cell(section, emoji)
            self.sections.append(section)
            self._add_bar_button(bar, icon, section)
        self.refresh_recent()

    def _add_section(self, title):
        header = Gtk.Label(label=title, xalign=0)
        header.get_style_context().add_class("section-title")
        flowbox = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                              max_children_per_line=9, min_children_per_line=9,
                              activate_on_single_click=True)
        flowbox.connect("child-activated", lambda _fb, child: self.on_pick(child.get_child().get_text()))
        self.content.pack_start(header, False, False, 0)
        self.content.pack_start(flowbox, False, False, 0)
        return EmojiSection(title, header, flowbox)

    def _add_cell(self, section, emoji):
        child = Gtk.FlowBoxChild()
        child.get_style_context().add_class("emoji-cell")
        child.add(Gtk.Label(label=emoji))
        child.set_tooltip_text(self.keywords.get(emoji, "").split(" ")[0] or emoji)
        child.show_all()
        section.flowbox.add(child)
        section.cells.append((child, emoji, self.keywords.get(emoji, "")))

    def _add_bar_button(self, bar, icon, section):
        btn = Gtk.Button(label=icon, relief=Gtk.ReliefStyle.NONE, tooltip_text=section.title)
        btn.set_can_focus(False)
        btn.connect("clicked", lambda _b: self._scroll_to(section))
        bar.pack_start(btn, True, True, 0)

    def _scroll_to(self, section):
        if not section.header.get_visible():
            return
        self.scroller.get_vadjustment().set_value(section.header.get_allocation().y)

    def refresh_recent(self):
        for child, _e, _k in self.recent.cells:
            child.destroy()
        self.recent.cells = []
        for emoji in self.store.recent_emoji:
            self._add_cell(self.recent, emoji)
        self.filter(self.query)

    def filter(self, query):
        self.query = q = query.strip().lower()
        for section in self.sections:
            any_visible = False
            for child, emoji, keys in section.cells:
                visible = not q or q in keys or q == emoji
                child.set_visible(visible)
                any_visible = any_visible or visible
            show = any_visible and not (q and section is self.recent)  # no duplicates while searching
            section.header.set_visible(show)
            section.flowbox.set_visible(show)
        if q:
            self.scroller.get_vadjustment().set_value(0)

    def _first_visible(self):
        for section in self.sections:
            if section.flowbox.get_visible():
                for child, emoji, _k in section.cells:
                    if child.get_visible():
                        return child, emoji
        return None, None

    def focus_first(self):
        child, _ = self._first_visible()
        if child:
            child.grab_focus()

    def activate_first(self):
        _, emoji = self._first_visible()
        if emoji:
            self.on_pick(emoji)


# --------------------------------------------------------------------------- history tab

class HistoryRow(Gtk.ListBoxRow):
    def __init__(self, item, page):
        super().__init__()
        self.text = item["text"]
        ctx = self.get_style_context()
        ctx.add_class("history-row")
        if item["pinned"]:
            ctx.add_class("pinned")

        preview = " ".join(self.text.strip().split())  # collapse whitespace/newlines
        if len(preview) > 400:
            preview = preview[:400] + "…"
        lines = self.text.strip().count("\n") + 1

        label = Gtk.Label(label=preview, xalign=0, wrap=True, lines=3,
                          ellipsize=Pango.EllipsizeMode.END, max_width_chars=40)
        label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        meta = time_ago(item.get("time", 0))
        if lines > 1:
            meta += f" · {lines} lines"
        meta_label = Gtk.Label(label=meta, xalign=0)
        meta_label.get_style_context().add_class("history-time")

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        text_box.pack_start(label, False, False, 0)
        text_box.pack_start(meta_label, False, False, 0)

        pin = Gtk.ToggleButton(label="📌", active=item["pinned"], relief=Gtk.ReliefStyle.NONE,
                               tooltip_text="Unpin" if item["pinned"] else "Pin (never expires)")
        pin.set_can_focus(False)
        if not item["pinned"]:
            pin.get_style_context().add_class("dim")
        pin.connect("toggled", lambda b: page.set_pinned(self.text, b.get_active()))

        delete = Gtk.Button(label="✕", relief=Gtk.ReliefStyle.NONE, tooltip_text="Delete (Del)")
        delete.set_can_focus(False)
        delete.connect("clicked", lambda _b: page.delete(self.text))

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.pack_start(text_box, True, True, 0)
        box.pack_start(pin, False, False, 0)
        box.pack_start(delete, False, False, 0)
        self.add(box)
        self.set_tooltip_text(self.text[:1000])


class HistoryPage(Gtk.Box):
    def __init__(self, on_pick, store):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_pick = on_pick
        self.store = store
        self.query = ""

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, margin=6)
        self.count_label = Gtk.Label(xalign=0)
        self.count_label.get_style_context().add_class("dim")
        clear = Gtk.Button(label="Clear all", tooltip_text="Delete everything except pinned items")
        clear.set_can_focus(False)
        clear.connect("clicked", lambda _b: self._clear())
        toolbar.pack_start(self.count_label, True, True, 0)
        toolbar.pack_end(clear, False, False, 0)
        self.pack_start(toolbar, False, False, 0)

        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, activate_on_single_click=True)
        self.listbox.set_filter_func(lambda row: not self.query or self.query in row.text.lower())
        self.listbox.connect("row-activated", lambda _lb, row: self.on_pick(row.text))
        placeholder = Gtk.Label(label="Nothing copied yet.\nCopy some text and it will show up here.",
                                justify=Gtk.Justification.CENTER, margin=24)
        placeholder.get_style_context().add_class("dim")
        placeholder.show()
        self.listbox.set_placeholder(placeholder)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.listbox)
        self.pack_start(scroller, True, True, 0)

    def refresh(self):
        for row in self.listbox.get_children():
            row.destroy()
        items = [h for h in self.store.history if h["pinned"]] + \
                [h for h in self.store.history if not h["pinned"]]
        for item in items:
            self.listbox.add(HistoryRow(item, self))
        self.listbox.show_all()
        pinned = sum(1 for h in items if h["pinned"])
        self.count_label.set_text(f"{len(items)} items" + (f" · {pinned} pinned" if pinned else ""))

    def filter(self, query):
        self.query = query.strip().lower()
        self.listbox.invalidate_filter()

    # Row buttons destroy their own row, so defer the rebuild until the handler returns.
    def set_pinned(self, text, pinned):
        self.store.set_pinned(text, pinned)
        GLib.idle_add(self.refresh)

    def delete(self, text):
        self.store.remove(text)
        GLib.idle_add(self.refresh)

    def _clear(self):
        self.store.clear_unpinned()
        self.refresh()

    def _visible_rows(self):
        return [r for r in self.listbox.get_children()
                if not self.query or self.query in r.text.lower()]

    def focus_first(self):
        rows = self._visible_rows()
        if rows:
            rows[0].grab_focus()

    def activate_first(self):
        rows = self._visible_rows()
        if rows:
            self.on_pick(rows[0].text)

    def delete_focused(self):
        row = self.listbox.get_focus_child()
        if isinstance(row, HistoryRow):
            index = row.get_index()
            self.store.remove(row.text)
            self.refresh()
            nxt = self.listbox.get_row_at_index(index) or self.listbox.get_row_at_index(index - 1)
            if nxt:
                nxt.grab_focus()
            return True
        return False


# --------------------------------------------------------------------------- window

class PickerWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app, title="Clipboard Picker")
        self.app = app
        self.shown_at = 0.0
        self.set_size_request(WIDTH, HEIGHT)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.get_style_context().add_class("picker")
        self.connect("delete-event", lambda *_: self.hide() or True)
        self.connect("key-press-event", self._on_key)
        self.connect("focus-out-event", self._on_focus_out)

        self.search = Gtk.SearchEntry(placeholder_text="Search emoji or clipboard…", margin=6)
        self.search.connect("search-changed", self._on_search)

        self.emoji_page = EmojiPage(app.pick_emoji, app.store)
        self.history_page = HistoryPage(app.pick_text, app.store)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE)
        self.stack.add_titled(self.emoji_page, "emoji", "😀  Emoji")
        self.stack.add_titled(self.history_page, "history", "📋  History")
        switcher = Gtk.StackSwitcher(stack=self.stack, halign=Gtk.Align.CENTER, margin_top=6)
        for button in switcher.get_children():
            button.set_can_focus(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(switcher, False, False, 0)
        box.pack_start(self.search, False, False, 0)
        box.pack_start(self.stack, True, True, 0)
        self.add(box)
        box.show_all()

    def current_page(self):
        return self.stack.get_visible_child()

    def _on_search(self, entry):
        text = entry.get_text()
        self.emoji_page.filter(text)
        self.history_page.filter(text)

    def _switch_tab(self):
        name = "history" if self.stack.get_visible_child_name() == "emoji" else "emoji"
        self.stack.set_visible_child_name(name)

    def _on_key(self, _w, event):
        key = event.keyval
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)

        if key == Gdk.KEY_Escape:
            if self.search.get_text():
                self.search.set_text("")
            else:
                self.hide()
            return True
        if ctrl and key in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
            self._switch_tab()
            return True
        if ctrl and key in (Gdk.KEY_1, Gdk.KEY_2):
            self.stack.set_visible_child_name("emoji" if key == Gdk.KEY_1 else "history")
            return True

        if self.search.has_focus():
            if key == Gdk.KEY_Down:
                self.current_page().focus_first()
                return True
            if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.current_page().activate_first()
                return True
            return False

        if key == Gdk.KEY_Delete and self.current_page() is self.history_page:
            return self.history_page.delete_focused()

        # Typing anywhere goes to the search box.
        char = Gdk.keyval_to_unicode(key)
        if not ctrl and char > 32 and char != 127:
            self.search.grab_focus_without_selecting()
            return self.search.handle_event(event)
        return False

    def _on_focus_out(self, *_):
        if time.monotonic() - self.shown_at > 0.4:  # ignore focus jitter while mapping
            self.hide()
        return False

    def _place(self):
        display = Gdk.Display.get_default()
        _screen, px, py = display.get_default_seat().get_pointer().get_position()
        monitor = display.get_monitor_at_point(px, py) or display.get_primary_monitor()
        area = monitor.get_workarea()
        if IS_X11_SESSION:  # pointer position is reliable: open next to the mouse like Win+.
            x, y = px - WIDTH // 2, py + 16
        else:               # under Wayland we only see the pointer over X windows; center instead
            x, y = area.x + (area.width - WIDTH) // 2, area.y + (area.height - HEIGHT) // 3
        x = min(max(x, area.x), area.x + area.width - WIDTH)
        y = min(max(y, area.y), area.y + area.height - HEIGHT)
        self.move(x, y)

    def _timestamp(self):
        # Fresh X server time lets the window manager grant focus despite focus-stealing prevention.
        try:
            gi.require_version("GdkX11", "3.0")
            from gi.repository import GdkX11
            gdk_window = self.get_window()
            if isinstance(gdk_window, GdkX11.X11Window):
                return GdkX11.x11_get_server_time(gdk_window)
        except (ImportError, ValueError):
            pass
        return Gtk.get_current_event_time()

    def toggle(self):
        if self.get_visible():
            self.hide()
            return
        self.search.set_text("")
        self.history_page.refresh()
        self.realize()
        self._place()
        self.shown_at = time.monotonic()
        self.show()
        self.present_with_time(self._timestamp())
        self.search.grab_focus()
        self.emoji_page.scroller.get_vadjustment().set_value(0)


# --------------------------------------------------------------------------- application

class PickerApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.store = Store()
        self.window = None
        self.clipboard = None
        self.last_clip = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # keep running in the background while the window is hidden
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = PickerWindow(self)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard.connect("owner-change", lambda *_: self._read_clipboard())
        GLib.timeout_add(POLL_MS, self._poll)  # fallback in case owner-change isn't delivered
        self._read_clipboard()

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if "--quit" in args:
            self.quit()
        elif "--hidden" not in args:
            self.window.toggle()
        return 0

    # -- clipboard watching
    def _poll(self):
        self._read_clipboard()
        return True

    def _read_clipboard(self):
        self.clipboard.request_text(self._on_text)

    def _on_text(self, _clipboard, text):
        if text and text != self.last_clip:
            self.last_clip = text
            if self.store.add_text(text) and self.window.get_visible():
                self.window.history_page.refresh()

    # -- picking
    def pick_emoji(self, emoji):
        self.store.add_recent_emoji(emoji)
        self.window.emoji_page.refresh_recent()
        self._deliver(emoji)

    def pick_text(self, text):
        self.store.add_text(text)  # move to top, like Windows
        self._deliver(text)

    def _deliver(self, text):
        self.last_clip = text  # don't record our own copies (keeps emojis out of history)
        self.clipboard.set_text(text, -1)
        self.window.hide()
        if AUTO_PASTE:
            GLib.timeout_add(200, paste_into_focused_window)


if __name__ == "__main__":
    sys.exit(PickerApp().run(sys.argv))
