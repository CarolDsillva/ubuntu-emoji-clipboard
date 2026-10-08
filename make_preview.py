"""Builds preview.html: a browser mock-up of Clipboard Picker, for trying it on Windows/macOS.

    python make_preview.py      # then open preview.html in a browser

It reads emoji_data.py and the settings at the top of clipboard_picker.py, so re-run it after
editing either file. The real app is GTK: layout/styling changes go in clipboard_picker.py
(the "Where to change things" panel in the page links each part to its code).
"""
import ast
import json
import pathlib

from emoji_data import CATEGORIES

HERE = pathlib.Path(__file__).parent
SETTINGS = ("MAX_HISTORY", "MAX_RECENT_EMOJI", "MAX_ITEM_CHARS", "AUTO_PASTE", "WIDTH", "HEIGHT")
CODE_MAP = [  # (code name, what it controls)
    ("CSS", "Colours, sizes, fonts, hover effects"),
    ("Store", "Saving history and recent emoji to disk"),
    ("Store.add_text", "What gets recorded and the history limit"),
    ("EmojiPage", "Emoji tab: category bar and sections"),
    ("EmojiPage.filter", "How emoji search matches"),
    ("HistoryRow", "One history item: preview text, 📌 and ✕"),
    ("HistoryPage", "History tab: toolbar, list, Clear all"),
    ("PickerWindow", "The popup window, tabs and search box"),
    ("PickerWindow._on_key", "Keyboard shortcuts inside the popup"),
    ("PickerWindow._place", "Where the popup opens on screen"),
    ("PickerApp._on_text", "Watching the clipboard"),
    ("PickerApp._deliver", "What happens when you pick something"),
    ("paste_into_focused_window", "Auto-paste (xdotool / ydotool)"),
]


def read_source():
    tree = ast.parse((HERE / "clipboard_picker.py").read_text(encoding="utf-8"))
    settings, lines = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                pairs = [(target.id, node.value)]
            elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):  # WIDTH, HEIGHT = ...
                pairs = [(t.id, v) for t, v in zip(target.elts, node.value.elts) if isinstance(t, ast.Name)]
            else:
                pairs = []
            for name, value in pairs:
                lines[name] = node.lineno
                if name in SETTINGS:
                    settings[name] = ast.literal_eval(value)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            lines[node.name] = node.lineno
            for sub in getattr(node, "body", []):
                if isinstance(sub, ast.FunctionDef):
                    lines[f"{node.name}.{sub.name}"] = sub.lineno
    code_map = [[name, desc, lines.get(name)] for name, desc in CODE_MAP]
    return settings, code_map


def main():
    settings, code_map = read_source()
    data = {"categories": CATEGORIES, "settings": settings, "codeMap": code_map}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (HERE / "preview_template.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    out = HERE / "preview.html"
    out.write_text(html, encoding="utf-8")
    count = sum(len(c[2]) for c in CATEGORIES)
    print(f"Wrote {out} ({count} emoji, settings: {settings})")


if __name__ == "__main__":
    main()
