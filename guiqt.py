#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" GUI in Qt6"""
import os
import re
import sys
import json
import html
import shutil
import difflib
import logging
import datetime
import time


from custom_path import Path
from general import (read_config_file, write_config_file, write_config_file_values,
                     is_empty, clean_line, clean_text, snapshot, get_raw,
                     URL_RE)
from output import Output
from logger import Logger
from todolist import ToDoList
from version import version_nb

from PyQt6.QtGui import (
    QFont, QIcon, QAction, QActionGroup, QDesktopServices,
    QPainter, QPolygon,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QMainWindow, QPlainTextEdit, QSizePolicy, QTextEdit, QTextBrowser,
    QSystemTrayIcon, QMenu, QFileDialog, QMessageBox,
    QDialog, QDialogButtonBox, QSlider, QLineEdit, QComboBox,
    QCheckBox, QSpinBox, QStyle,
)
from PyQt6.QtCore import Qt, QLocale, QTimer, QUrl, QPoint, pyqtSignal

QUADRANT_KEYS = {
    "Urgent & Important":       ("U&I",   "U&I_done"),
    "Not Urgent & Important":   ("NU&I",  "NU&I_done"),
    "Urgent & Unimportant":     ("U&Un",  "U&Un_done"),
    "Not Urgent & Unimportant": ("NU&Un", "NU&Un_done"),
}

# Reverse lookups for the right-click menus (move to other quadrant, etc.)
_ACTIVE_LOCS = [loc for loc, _ in QUADRANT_KEYS.values()]
_LOC_TO_DISPLAY = {loc: display for display, (loc, _) in QUADRANT_KEYS.items()}
_LOC_TO_DONE = dict(QUADRANT_KEYS.values())
_DONE_TO_LOC = {done: loc for loc, done in QUADRANT_KEYS.values()}
_DONE_LIMIT = 10  # max items kept in any "done" quadrant

# Native display names for the language menu. QLocale.nativeLanguageName()
# tends to include a country variant ("American English", "español de España")
# so we override the common codes; unknown codes fall back to QLocale.
_NATIVE_LANG_NAMES = {
    "en": "English",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "ja": "日本語",
    "zh": "中文",
}

_QM_RE = re.compile(r"^eitodo_([a-zA-Z_]+)\.qm$")

# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------


def _task_data(path: str) -> dict | None:
    """Return the task quadrants of a JSON file, excluding sync metadata
    (version/updated_at/last_writer). Returns None if it can't be read/parsed."""
    try:
        with open(path, "r", encoding="utf8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return {k: v for k, v in data.items() if k not in ToDoList._META_KEYS}


def _latest_backup(save_folder: str, name: str) -> str | None:
    """Return the path of the most recent timestamped backup of <name>.json in
    save_folder, or None if there is none. The YYYY_MM_DD_HHMMSS_ prefix sorts
    chronologically, so the lexically-greatest match is the newest."""
    pattern = re.compile(rf"^\d{{4}}_\d{{2}}_\d{{2}}_\d{{6}}_{re.escape(name)}\.json$")
    try:
        candidates = sorted(f for f in os.listdir(save_folder) if pattern.match(f))
    except OSError:
        return None
    return os.path.join(save_folder, candidates[-1]) if candidates else None


# ---------------------------------------------------------------------------
# Tracked editor — debounce + auto-format + save to todolist
# ---------------------------------------------------------------------------

def _looks_like_edit(old: str, new: str) -> bool:
    """True if display line `new` plausibly is `old` after in-place typing
    (append, truncate, or a small edit) rather than a fresh overwrite. Compared
    on the item text only — the shared '• ' bullet is stripped, so short items
    aren't judged similar just because they carry the same bullet."""
    a = get_raw(old)
    b = get_raw(new)
    a = a[0] if a else ""
    b = b[0] if b else ""
    if not a or not b:
        return False
    if b.startswith(a) or a.startswith(b):
        return True
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.6


class TrackedTextEdit(QPlainTextEdit):
    items_erased = pyqtSignal(list)        # raw items removed by typing/deletion
    mark_done_requested = pyqtSignal(str)  # raw item → move to corresponding _done
    move_to_requested = pyqtSignal(str, str)  # raw item, target active loc

    def __init__(self, todolist: ToDoList, loc: str, debounce_ms: int, parent=None):
        super().__init__(parent)
        self.todolist = todolist
        self.loc = loc
        self._snap: dict[int, str] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._flush)
        self.textChanged.connect(lambda: self._timer.start())
        self._last_mouse_pos = None
        # Needed to receive mouse-move events without a button pressed (link hover)
        self.viewport().setMouseTracking(True)

    def set_content(self, items: list[str]):
        """Load items (raw, without '• ') into the editor and reset snapshot."""
        self.blockSignals(True)
        self.setPlainText(clean_text("\n".join(items)))
        self._snap = snapshot(self.toPlainText())
        self.blockSignals(False)

    def _flush(self):
        text = self.toPlainText()
        cursor = self.textCursor()
        block_num = cursor.blockNumber()
        col = cursor.positionInBlock()
        raw_lines = text.splitlines()

        # Reformat lines, but if the cursor sits on an empty line (the user
        # just pressed Enter to start a new item) keep it as a "• " placeholder
        # so the cursor stays on a fresh bullet instead of being yanked into
        # the next existing item.
        cleaned_lines: list[str] = []
        new_block_num = 0
        new_col = 0
        cursor_placed = False
        for i, line in enumerate(raw_lines):
            is_cursor_line = (i == block_num)
            if is_empty(line):
                if is_cursor_line:
                    cleaned_lines.append("• ")
                    new_block_num = len(cleaned_lines) - 1
                    new_col = 2
                    cursor_placed = True
            else:
                cleaned_lines.append(clean_line(line))
                if is_cursor_line:
                    s = line.lstrip()
                    after_bullet = s[1:].lstrip() if s.startswith("•") else s
                    content_start = len(line) - len(after_bullet)
                    content_col = max(0, col - content_start)
                    new_block_num = len(cleaned_lines) - 1
                    new_col = 2 + content_col
                    cursor_placed = True
        if not cursor_placed and raw_lines and block_num >= len(raw_lines):
            # Cursor on a phantom empty block past the last raw line (Enter at
            # the very end of the text). Preserve as a "• " placeholder too.
            cleaned_lines.append("• ")
            new_block_num = len(cleaned_lines) - 1
            new_col = 2
            cursor_placed = True
        if not cursor_placed:
            new_block_num = max(0, len(cleaned_lines) - 1)
            new_col = 0
        cleaned = ("\n".join(cleaned_lines) + "\n") if cleaned_lines else ""

        if cleaned != text:
            self.blockSignals(True)
            self.setPlainText(cleaned)
            block = self.document().findBlockByNumber(new_block_num)
            if not block.isValid():
                block = self.document().lastBlock()
            new_col = min(new_col, max(0, block.length() - 1))
            new_cursor = self.textCursor()
            new_cursor.setPosition(block.position() + new_col)
            self.setTextCursor(new_cursor)
            self.blockSignals(False)

        current = snapshot(self.toPlainText())
        if current != self._snap:
            # Detect erasures via a line-level diff. A `delete` op removes items
            # outright. A `replace` op is ambiguous: typing into a line edits it
            # in place (keep it), but selecting one or more lines and typing over
            # them removes those lines (send them to 'done'). We tell the two
            # apart by content similarity instead of position: within a replace
            # op, each old line is paired with a new line it plausibly became
            # (append / truncate / small edit). Old lines with no such match —
            # and not merely reordered elsewhere — are the ones truly erased.
            old_lines = [v for _, v in sorted(self._snap.items())]
            new_lines = [v for _, v in sorted(current.items())]
            new_set = set(new_lines)
            truly_erased: list[str] = []
            sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "delete":
                    truly_erased.extend(item for item in old_lines[i1:i2]
                                        if item not in new_set)
                elif tag == "replace":
                    remaining = list(new_lines[j1:j2])
                    for item in old_lines[i1:i2]:
                        match = next((k for k, nl in enumerate(remaining)
                                      if _looks_like_edit(item, nl)), None)
                        if match is not None:
                            remaining.pop(match)
                        elif item not in new_set:
                            truly_erased.append(item)
            raw_erased = [get_raw(line)[0] for line in truly_erased if get_raw(line)]
            if raw_erased:
                self.items_erased.emit(raw_erased)
            self.todolist.set_quadrant(self.loc, get_raw(self.toPlainText()))
        self._snap = current

    def mousePressEvent(self, event):
        """Ctrl+click on a URL opens it instead of moving the cursor."""
        if (event.button() == Qt.MouseButton.LeftButton
                and Qt.KeyboardModifier.ControlModifier in event.modifiers()):
            url = self._url_at(self.cursorForPosition(event.position().toPoint()))
            if url:
                QDesktopServices.openUrl(QUrl(url))
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Track the cursor position and update the link-hover cursor."""
        self._last_mouse_pos = event.position().toPoint()
        ctrl = Qt.KeyboardModifier.ControlModifier in event.modifiers()
        self._update_link_cursor(ctrl)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._update_link_cursor(True)
        if Qt.KeyboardModifier.ControlModifier in event.modifiers():
            if event.key() == Qt.Key.Key_Up:
                self._move_line(-1)
                return
            if event.key() == Qt.Key.Key_Down:
                self._move_line(+1)
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._update_link_cursor(False)
        super().keyReleaseEvent(event)

    def _move_line(self, direction: int, block_num: int | None = None):
        """Swap the non-empty line at block_num with the closest non-empty line
        in `direction` (-1 up, +1 down). The text change is debounced and
        ultimately persisted by _flush; SequenceMatcher sees the swap as a
        delete+insert pair whose values are still present, so nothing is
        wrongly routed to the done panel."""
        cursor = self.textCursor()
        if block_num is None:
            block_num = cursor.blockNumber()
        lines = self.toPlainText().split("\n")
        if not (0 <= block_num < len(lines)) or is_empty(lines[block_num]):
            return
        target = block_num + direction
        while 0 <= target < len(lines) and is_empty(lines[target]):
            target += direction
        if not (0 <= target < len(lines)):
            return
        lines[block_num], lines[target] = lines[target], lines[block_num]
        self.setPlainText("\n".join(lines))
        new_block = self.document().findBlockByNumber(target)
        if new_block.isValid():
            new_cursor = self.textCursor()
            new_cursor.setPosition(new_block.position())
            self.setTextCursor(new_cursor)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.cursorForPosition(event.pos())
        line_text = cursor.block().text()
        raw_items = get_raw(line_text)
        raw = raw_items[0] if raw_items else None

        if raw:
            menu.addSeparator()

            url = self._url_at(cursor)
            if url:
                act_url = menu.addAction(self.tr("Open link: {}").format(url))
                act_url.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
                menu.addSeparator()

            block_num = cursor.blockNumber()
            act_up = menu.addAction(self.tr("Move up\tCtrl+Up"))
            act_up.triggered.connect(lambda: self._move_line(-1, block_num))
            act_down = menu.addAction(self.tr("Move down\tCtrl+Down"))
            act_down.triggered.connect(lambda: self._move_line(+1, block_num))

            menu.addSeparator()

            act_done = menu.addAction(self.tr("Mark as done"))
            act_done.triggered.connect(lambda: self.mark_done_requested.emit(raw))

            move_menu = menu.addMenu(self.tr("Move to quadrant"))
            for other_loc in _ACTIVE_LOCS:
                if other_loc == self.loc:
                    continue
                # `&` in QAction text is the mnemonic prefix; double it to show
                # a literal ampersand in "Urgent & Important" etc.
                label = self.tr(_LOC_TO_DISPLAY[other_loc]).replace("&", "&&")
                act = move_menu.addAction(label)
                act.triggered.connect(
                    lambda _, t=other_loc, r=raw: self.move_to_requested.emit(r, t)
                )

        menu.exec(event.globalPos())

    def _update_link_cursor(self, ctrl_held: bool):
        """Show a pointing-hand cursor when Ctrl is held over a URL at the last
        known mouse position, otherwise the normal text cursor."""
        on_link = bool(
            ctrl_held
            and self._last_mouse_pos is not None
            and self._url_at(self.cursorForPosition(self._last_mouse_pos))
        )
        self.viewport().setCursor(
            Qt.CursorShape.PointingHandCursor if on_link else Qt.CursorShape.IBeamCursor
        )

    def _url_at(self, cursor) -> str | None:
        """Return the URL of the whitespace-delimited token under the cursor,
        or None if it is not a link. 'www.' tokens get an https:// scheme."""
        text = cursor.block().text()
        pos = cursor.positionInBlock()
        if not text:
            return None
        start = pos
        while start > 0 and not text[start - 1].isspace():
            start -= 1
        end = pos
        while end < len(text) and not text[end].isspace():
            end += 1
        match = URL_RE.search(text[start:end])
        if not match:
            return None
        url = match.group(0).rstrip(".,;:!?)]}>\"'")
        if url.lower().startswith("www."):
            url = "https://" + url
        return url


# ---------------------------------------------------------------------------
# Done panel — read-only widget with strikethrough items and a context menu
# ---------------------------------------------------------------------------

class DoneTextEdit(QTextEdit):
    restore_requested = pyqtSignal(str)        # raw item → back to its active loc
    restore_to_requested = pyqtSignal(str, str)  # raw item, target active loc
    delete_requested = pyqtSignal(str)         # raw item → permanent removal

    def __init__(self, loc_done: str, parent=None):
        super().__init__(parent)
        self.loc_done = loc_done
        self._items: list[str] = []
        self.setReadOnly(True)

    def set_items(self, items: list[str]):
        """Render items as one strikethrough block per item so blockNumber
        maps directly to the item index (used by the right-click menu).

        Only the most recent _DONE_LIMIT items are displayed. The backing store
        may transiently hold more — loading a backup or a remote change are not
        capped — so this trims the view (and the context-menu mapping) without
        ever rewriting the stored data; the next completion (_on_erased) trims
        the file back to the limit."""
        self._items = [item for item in items if item][:_DONE_LIMIT]
        # Escape the task text: it is injected into rich text via setHtml(), so
        # raw '<', '>' or '&' would be parsed as markup and corrupt or hide the
        # item. self._items keeps the un-escaped text for the context menu.
        body = "".join(
            f"<div style='margin:0;padding:0;'><s>{html.escape(clean_line(item))}</s></div>"
            for item in self._items
        )
        self.setHtml(body)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.cursorForPosition(event.pos())
        block_num = cursor.blockNumber()
        if 0 <= block_num < len(self._items):
            item = self._items[block_num]
            menu.addSeparator()

            act_restore = menu.addAction(self.tr("Restore to active list"))
            act_restore.triggered.connect(lambda: self.restore_requested.emit(item))

            restore_menu = menu.addMenu(self.tr("Restore to quadrant"))
            from_loc = _DONE_TO_LOC.get(self.loc_done, "")
            for other_loc in _ACTIVE_LOCS:
                if other_loc == from_loc:
                    continue
                # `&` in QAction text is the mnemonic prefix; double it for a
                # literal ampersand in the quadrant label.
                label = self.tr(_LOC_TO_DISPLAY[other_loc]).replace("&", "&&")
                act = restore_menu.addAction(label)
                act.triggered.connect(
                    lambda _, t=other_loc, it=item: self.restore_to_requested.emit(it, t)
                )

            menu.addSeparator()

            act_del = menu.addAction(self.tr("Delete permanently"))
            act_del.triggered.connect(lambda: self.delete_requested.emit(item))

        menu.exec(event.globalPos())


# ---------------------------------------------------------------------------
# Font picker dialog
# ---------------------------------------------------------------------------

_STANDARD_FONTS = [
    ("DejaVu Sans",      "DejaVu Sans"),
    ("DejaVu Sans Mono", "DejaVu Sans Mono"),
    ("DejaVu Serif",     "DejaVu Serif"),
    ("Liberation Sans",  "Liberation Sans"),
    ("Liberation Serif", "Liberation Serif"),
    ("Liberation Mono",  "Liberation Mono"),
    ("FreeSans",         "FreeSans"),
    ("FreeSerif",        "FreeSerif"),
    ("FreeMono",         "FreeMono"),
    ("Noto Sans",        "Noto Sans"),
    ("Noto Serif",       "Noto Serif"),
    ("Noto Mono",        "Noto Mono"),
    ("Cantarell",        "Cantarell"),
    ("Ubuntu",           "Ubuntu"),
    ("Ubuntu Sans",      "Ubuntu Sans"),
    ("Ubuntu Mono",      "Ubuntu Mono"),
    ("Ubuntu Sans Mono", "Ubuntu Sans Mono"),
    ("Roboto",           "Roboto"),
    ("Courier",          "Courier"),
]

_SIZE_MIN, _SIZE_MAX = 7, 18


class FontPickerDialog(QDialog):
    def __init__(self, current_font: QFont, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Change font"))
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(self.tr("Font:")))
        self._combo = QComboBox()
        for label, _ in _STANDARD_FONTS:
            self._combo.addItem(label)
        current_family = current_font.family()
        for i, (_, fam) in enumerate(_STANDARD_FONTS):
            if fam == current_family:
                self._combo.setCurrentIndex(i)
                break
        layout.addWidget(self._combo)

        current_size = current_font.pointSize() if current_font.pointSize() > 0 else 11
        current_size = max(_SIZE_MIN, min(_SIZE_MAX, current_size))

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self.tr("Size:")))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(_SIZE_MIN, _SIZE_MAX)
        self._slider.setValue(current_size)
        self._size_edit = QLineEdit(str(current_size))
        self._size_edit.setFixedWidth(45)
        size_row.addWidget(self._slider, 1)
        size_row.addWidget(self._size_edit)
        layout.addLayout(size_row)

        layout.addWidget(QLabel(self.tr("Preview:")))
        self._preview = QLabel(self.tr("• Urgent and important task\n• Another example task"))
        self._preview.setStyleSheet("border: 1px solid gray; padding: 6px; background: white;")
        self._preview.setWordWrap(True)
        self._preview.setMinimumHeight(60)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._size_edit.editingFinished.connect(self._on_edit_finished)
        self._combo.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

    def _on_slider_changed(self, value: int):
        self._size_edit.blockSignals(True)
        self._size_edit.setText(str(value))
        self._size_edit.blockSignals(False)
        self._update_preview()

    def _on_edit_finished(self):
        try:
            v = max(_SIZE_MIN, min(_SIZE_MAX, int(self._size_edit.text())))
        except ValueError:
            v = self._slider.value()
        self._size_edit.setText(str(v))
        self._slider.setValue(v)
        self._update_preview()

    def _update_preview(self):
        self._preview.setFont(self.selected_font())

    def selected_font(self) -> QFont:
        family = _STANDARD_FONTS[self._combo.currentIndex()][1]
        return QFont(family, self._slider.value())


# ---------------------------------------------------------------------------
# Help dialog
# ---------------------------------------------------------------------------

class HelpDialog(QDialog):
    """Modeless help window. Loads docs/help_<lang>.md as Markdown into a
    QTextBrowser, falling back to docs/help_en.md when the requested
    catalog is missing (e.g. user is running a language with no help yet).
    Language is resolved by the caller from config.INI."""

    def __init__(self, lang: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Help"))
        self.resize(760, 720)

        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        docs_dir = os.path.join(base_dir, "docs")
        candidate = os.path.join(docs_dir, f"help_{lang}.md")
        fallback = os.path.join(docs_dir, "help_en.md")
        path = candidate if os.path.isfile(candidate) else fallback

        try:
            with open(path, "r", encoding="utf8") as f:
                browser.setMarkdown(f.read())
        except OSError as e:
            browser.setPlainText(
                self.tr("Help file not found:\n{0}").format(e))
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)


# A thin strip drawn under a horizontal QSlider that marks one "default" value
# with a small upward triangle. The x position is derived from the slider's own
# style metrics, so it stays aligned with the handle steps across resizes and
# themes. Sibling of the slider in the same layout column (same width).
class SliderDefaultMarker(QWidget):
    def __init__(self, slider: QSlider, value: int, parent=None):
        super().__init__(parent)
        self._slider = slider
        self._value = value
        self.setFixedHeight(10)

    def paintEvent(self, event):
        slider = self._slider
        style = slider.style()
        handle = style.pixelMetric(QStyle.PixelMetric.PM_SliderLength, None, slider)
        span = max(1, slider.width() - handle)
        pos = style.sliderPositionFromValue(
            slider.minimum(), slider.maximum(), self._value, span)
        cx = handle // 2 + pos
        h = self.height()
        half = h - 3  # base half-width: a clearly visible, slightly wide pip
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        # Accent colour so the default marker stands out from the slider groove.
        painter.setBrush(self.palette().highlight())
        painter.drawPolygon(QPolygon([
            QPoint(cx, 0), QPoint(cx - half, h - 1), QPoint(cx + half, h - 1)]))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    _remote_change = pyqtSignal(dict)

    def __init__(self, todolist: ToDoList, debounce_ms: int = 500,
                 width: int = 1000, height: int = 1000,
                 x: int = 0, y: int = 0, screen_name: str = "",
                 prompt_data_location: bool = False, default_json_name: str = "",
                 font: str = "DejaVu Sans", font_size: int = 10):
        super().__init__()
        self.todolist = todolist
        self._debounce_ms = debounce_ms
        self._editors: dict[str, TrackedTextEdit] = {}
        self._done_widgets: dict[str, DoneTextEdit] = {}
        # Relative default data path persisted when the user keeps the default
        # location (single source of truth: main._DEFAULT_PATH).
        self._default_json_name = default_json_name
        # Guards the shutdown save so it runs exactly once no matter how the app
        # is terminated (tray quit, SIGTERM, or desktop session end).
        self._shutdown_saved = False

        # Find target screen by name, fall back to primary
        target_screen = None
        if screen_name:
            for s in QApplication.screens():
                if s.name() == screen_name:
                    target_screen = s
                    break
        if target_screen is None:
            target_screen = QApplication.primaryScreen()

        sg = target_screen.geometry()
        clamped_x = max(sg.x(), min(x, sg.x() + sg.width() - width))
        clamped_y = max(sg.y(), min(y, sg.y() + sg.height() - height))
        self.setGeometry(clamped_x, clamped_y, width, height)

        self.setWindowTitle('Eisenhower Todo-List')
        icon = QIcon(Path.icon_path)
        self.setWindowIcon(icon)

        # Hide from taskbar (Tool windows don't get a taskbar button)
        self.setWindowFlag(Qt.WindowType.Tool)

        # System tray icon
        self._build_tray_icon(icon)

        # Route remote-file changes (background thread) safely to the main thread
        todolist.set_on_remote_change(self._remote_change.emit)
        self._remote_change.connect(self._on_remote_file_change)

        # Hourly backup: writes a new param backup, or just refreshes the
        # timestamp of the last one when nothing changed (see _backup_param).
        self._backup_timer = QTimer(self)
        self._backup_timer.setInterval(60 * 60 * 1000)  # 1 hour
        self._backup_timer.timeout.connect(self._hourly_backup)
        self._backup_timer.start()

        self._build_quadrants(font, font_size)

        # First launch or a missing data file: once the event loop is running,
        # ask where to store data (same flow as changing the location manually).
        if prompt_data_location:
            QTimer.singleShot(0, self._prompt_data_location)

    def _build_tray_icon(self, icon: QIcon):
        """Build the system tray icon and its context menu."""
        self._tray = QSystemTrayIcon(icon, self)
        tray_menu = QMenu()
        # Header: app name + version, disabled (informational only). The app
        # name and the 'V' marker are not localised — they read the same in
        # every language and match the version() string in the log.
        version_action = QAction(f"EiTodo V {version_nb()}", self)
        version_action.setEnabled(False)
        tray_menu.addAction(version_action)
        tray_menu.addSeparator()
        clear_done_action = QAction(QIcon.fromTheme("edit-clear"), self.tr("Clear all finished tasks"), self)
        clear_done_action.triggered.connect(self._clear_all_done)
        tray_menu.addAction(clear_done_action)
        tray_menu.addSeparator()
        load_backup_action = QAction(QIcon.fromTheme("document-open"), self.tr("Load a backup"), self)
        load_backup_action.triggered.connect(self._load_backup)
        tray_menu.addAction(load_backup_action)
        backup_limit_action = QAction(QIcon.fromTheme("document-save"),
                                      self.tr("Number of backups to keep…"), self)
        backup_limit_action.triggered.connect(self._change_backup_limit)
        tray_menu.addAction(backup_limit_action)
        open_backups_action = QAction(QIcon.fromTheme("folder-open"),
                                      self.tr("Open backups folder"), self)
        open_backups_action.triggered.connect(
            lambda: self._open_folder(Path.save_folder))
        tray_menu.addAction(open_backups_action)
        data_location_action = QAction(QIcon.fromTheme("folder-open"), self.tr("Data location…"), self)
        data_location_action.triggered.connect(self._show_data_location)
        tray_menu.addAction(data_location_action)
        change_font_action = QAction(QIcon.fromTheme("preferences-desktop-font"), self.tr("Change font…"), self)
        change_font_action.triggered.connect(self._change_font)
        tray_menu.addAction(change_font_action)
        responsiveness_action = QAction(QIcon.fromTheme("preferences-system"),
                                        self.tr("Interface responsiveness…"), self)
        responsiveness_action.triggered.connect(self._change_debounce)
        tray_menu.addAction(responsiveness_action)

        # Language submenu — populated dynamically from translations/eitodo_*.qm
        # plus 'en' (source language, no catalog needed). The check state
        # mirrors config.INI's resolved 'language' (always concrete after
        # _install_translators()). Language names are kept in their own
        # language (convention: no tr()).
        language_menu = QMenu(self.tr("Change language"), tray_menu)
        language_menu.setIcon(QIcon.fromTheme("preferences-desktop-locale"))
        try:
            current_lang = read_config_file(param="language").strip()
        except (ValueError, OSError):
            current_lang = ""
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        self._language_actions: dict[str, QAction] = {}
        for code, label in self._discover_languages():
            action = QAction(label, lang_group)
            action.setCheckable(True)
            action.setChecked(code == current_lang)
            action.triggered.connect(lambda _checked, c=code: self._change_language(c))
            language_menu.addAction(action)
            self._language_actions[code] = action
        tray_menu.addMenu(language_menu)

        tray_menu.addSeparator()
        start_hidden_action = QAction(self.tr("Hidden at startup"), self)
        start_hidden_action.setCheckable(True)
        start_hidden_action.setChecked(read_config_file(param="start_hidden").strip().lower() == "true")
        start_hidden_action.toggled.connect(lambda checked: (
            write_config_file("start_hidden", str(checked).lower()),
            Output.print(f"Start hidden: {checked}", level="info"),
        ))
        tray_menu.addAction(start_hidden_action)
        tray_menu.addSeparator()
        help_action = QAction(QIcon.fromTheme("help-contents"), self.tr("Help"), self)
        help_action.triggered.connect(self._show_help)
        tray_menu.addAction(help_action)
        quit_action = QAction(QIcon.fromTheme("application-exit"), self.tr("Quit"), self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)
        self._tray.setContextMenu(tray_menu)
        self._tray.setToolTip("Eisenhower Todo-List")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _build_quadrants(self, font: str, font_size: int):
        """Build the central widget holding the four Eisenhower quadrants."""
        todolist = self.todolist

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        top_row = QHBoxLayout()
        bottom_row = QHBoxLayout()
        main_layout.addLayout(top_row)
        main_layout.addLayout(bottom_row)

        quadrants = [
            ("Urgent & Important",       "Urgent & Important → Do it",            top_row,    "#ffd199"),
            ("Not Urgent & Important",   "Not Urgent & Important → Schedule",     top_row,    "#ffccc7"),
            ("Urgent & Unimportant",     "Urgent & Unimportant → Delegate",       bottom_row, "#d4f7b0"),
            ("Not Urgent & Unimportant", "Not Urgent & Unimportant → Recreation", bottom_row, "#c5deff"),
        ]

        self._editor_font = QFont(font, font_size)

        for key, title, row_layout, color in quadrants:
            loc, loc_done = QUADRANT_KEYS[key]

            square = QWidget()
            square.setObjectName("quadrantSquare")
            square.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # Scope to the square itself via the object name: a bare `QWidget`
            # selector cascades into every QWidget descendant — including the
            # QMenu instances that pop up for right-clicks, which then inherit
            # the colored background and become unreadable on hover.
            square.setStyleSheet(
                f"#quadrantSquare {{ border: 2px solid gray; "
                f"background-color: {color}; padding: 8px; }}"
            )
            square_layout = QVBoxLayout(square)

            label = QLabel(title)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-weight: bold; border: none;")
            square_layout.addWidget(label)

            editor = TrackedTextEdit(todolist, loc, self._debounce_ms)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # Class-scoped: without a selector the rules would leak into the
            # context QMenu (parented to the editor) and make hovered items
            # show white text on white background.
            editor.setStyleSheet("QPlainTextEdit { border: 1px solid gray; background-color: white; }")
            editor.setFont(self._editor_font)
            editor.set_content(todolist.todolist_dict.get(loc, []))
            self._editors[loc] = editor

            done_widget = DoneTextEdit(loc_done)
            done_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            # Class-scoped — same reason as the editor above.
            done_widget.setStyleSheet("QTextEdit { border: 1px solid gray; background-color: white; }")
            done_widget.setFont(self._editor_font)
            done_widget.set_items(todolist.todolist_dict.get(loc_done, []))
            self._done_widgets[loc_done] = done_widget

            editor.items_erased.connect(
                lambda items, ld=loc_done, dw=done_widget: self._on_erased(ld, dw, items)
            )
            editor.mark_done_requested.connect(
                lambda item, src=loc: self._on_mark_done(src, item)
            )
            editor.move_to_requested.connect(
                lambda item, target, src=loc: self._on_move_to(src, target, item)
            )
            done_widget.restore_requested.connect(
                lambda item, ld=loc_done: self._on_restore(ld, item)
            )
            done_widget.restore_to_requested.connect(
                lambda item, target, ld=loc_done: self._on_restore_to(ld, target, item)
            )
            done_widget.delete_requested.connect(
                lambda item, ld=loc_done: self._on_delete_permanent(ld, item)
            )

            square_layout.addWidget(editor)
            square_layout.addWidget(done_widget)
            row_layout.addWidget(square, 1)

    def _on_erased(self, loc_done: str, done_widget: "DoneTextEdit", raw_items: list[str]):
        current_done = list(self.todolist.todolist_dict.get(loc_done, []))
        for item in raw_items:
            if item not in current_done:
                current_done.insert(0, item)
        current_done = current_done[:_DONE_LIMIT]
        self.todolist.set_quadrant(loc_done, current_done)
        done_widget.set_items(current_done)

    def _on_mark_done(self, loc: str, item: str):
        """Right-click → 'Mark as done': remove from active loc, prepend to done."""
        loc_done = _LOC_TO_DONE[loc]
        active_items = list(self.todolist.todolist_dict.get(loc, []))
        if item in active_items:
            active_items.remove(item)
            self.todolist.set_quadrant(loc, active_items)
            self._editors[loc].set_content(active_items)
        self._on_erased(loc_done, self._done_widgets[loc_done], [item])

    def _on_move_to(self, src_loc: str, target_loc: str, item: str):
        """Right-click → 'Move to quadrant': move between active quadrants."""
        src_items = list(self.todolist.todolist_dict.get(src_loc, []))
        if item in src_items:
            src_items.remove(item)
            self.todolist.set_quadrant(src_loc, src_items)
            self._editors[src_loc].set_content(src_items)
        target_items = list(self.todolist.todolist_dict.get(target_loc, []))
        if item not in target_items:
            target_items.insert(0, item)
            self.todolist.set_quadrant(target_loc, target_items)
            self._editors[target_loc].set_content(target_items)

    def _on_restore(self, loc_done: str, item: str):
        """Right-click on done → 'Restore': back to the corresponding active loc."""
        target_loc = _DONE_TO_LOC[loc_done]
        self._on_restore_to(loc_done, target_loc, item)

    def _on_restore_to(self, loc_done: str, target_loc: str, item: str):
        """Right-click on done → 'Restore to quadrant': back to a chosen active loc."""
        done_items = list(self.todolist.todolist_dict.get(loc_done, []))
        if item in done_items:
            done_items.remove(item)
            self.todolist.set_quadrant(loc_done, done_items)
            self._done_widgets[loc_done].set_items(done_items)
        target_items = list(self.todolist.todolist_dict.get(target_loc, []))
        if item not in target_items:
            target_items.insert(0, item)
            self.todolist.set_quadrant(target_loc, target_items)
            self._editors[target_loc].set_content(target_items)

    def _on_delete_permanent(self, loc_done: str, item: str):
        """Right-click on done → 'Delete permanently': drop the item for good."""
        done_items = list(self.todolist.todolist_dict.get(loc_done, []))
        if item in done_items:
            done_items.remove(item)
            self.todolist.set_quadrant(loc_done, done_items)
            self._done_widgets[loc_done].set_items(done_items)

    def _on_remote_file_change(self, data: dict):
        """Slot for the remote-change signal: a *different* instance modified the
        shared data file. Logged here (unlike the internal UI refreshes that also
        call _on_remote_change), then the editors are refreshed on the main thread."""
        Output.print(f"Remote change received from another instance "
                     f"(version {data.get('version', '?')})", level="info")
        # Keep the ToDoList's in-memory state in sync with what we just received,
        # so a subsequent right-click op (which rebuilds a quadrant from
        # todolist_dict, not from the widget) doesn't revert this remote change.
        self.todolist.apply_remote_state(data)
        self._on_remote_change(data)

    def _on_remote_change(self, data: dict):
        """Update all editors and done-widgets from a remote file change (main thread)."""
        for loc, editor in self._editors.items():
            editor.set_content(data.get(loc, []))
        for loc, widget in self._done_widgets.items():
            widget.set_items(data.get(loc, []))

    def _clear_all_done(self):
        for loc_done, widget in self._done_widgets.items():
            self.todolist.set_quadrant(loc_done, [])
            widget.set_items([])
        Output.print("All finished tasks cleared", level="info")

    def _load_backup(self):
        """Pick a .json backup in the save folder and replace every quadrant
        (tasks and done lists) with its content."""
        # Snapshot the current state first so it can be recovered if needed.
        # Flush pending editor edits to disk so the backup is up to date.
        self._flush_editors()
        self._backup_param()

        start_dir = os.path.abspath(Path.save_folder) if Path.save_folder else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Load a backup"), start_dir, self.tr("JSON backups (*.json)")
        )
        if not file_path:
            return  # cancelled

        data = _task_data(file_path)
        if data is None:
            QMessageBox.warning(
                self, self.tr("Load a backup"),
                self.tr("Cannot read the backup:\n{0}").format(file_path),
            )
            return

        if self._invalid_quadrants(data):
            QMessageBox.warning(
                self, self.tr("Load a backup"),
                self.tr("Invalid backup: the file is malformed:\n"),
            )
            return

        if QMessageBox.question(
            self, self.tr("Load a backup"),
            self.tr("Replace all current tasks with the content of\n{0}?").format(
                os.path.basename(file_path)),
        ) != QMessageBox.StandardButton.Yes:
            return

        # Drop any pending debounced edits so they can't overwrite the load
        self._stop_editor_timers()

        # Persist every quadrant from the backup, then refresh the UI from it
        for loc in self.todolist.POSSIBLE_LOC:
            self.todolist.set_quadrant(loc, data.get(loc, []))
        self._on_remote_change(self.todolist.todolist_dict)

        Output.print(f"Backup loaded: {file_path}", level="info")

    def _invalid_quadrants(self, data: dict) -> list[str]:
        """Return quadrant keys missing from data or not stored as a list.
        An empty result means the file holds a complete, well-formed matrix."""
        return [loc for loc in self.todolist.POSSIBLE_LOC
                if not isinstance(data.get(loc), list)]

    def _prompt_data_location(self):
        """At first launch or when the configured data file is missing, surface
        the window and let the user either keep the default location or point to
        an existing data file. Same flow as changing the location manually."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.tr("Data location"))
        box.setText(self.tr("Where do you want to store the data?"))
        box.setInformativeText(self.tr(
            "Use the default location, or point to an existing data file?"
        ))
        default_btn = box.addButton(self.tr("Default location"), QMessageBox.ButtonRole.AcceptRole)
        locate_btn = box.addButton(self.tr("Pick a location…"), QMessageBox.ButtonRole.ActionRole)
        box.setDefaultButton(default_btn)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()

        if clicked is locate_btn:
            self._locate_data_file_dialog()
        else:
            self._use_default_data_location()

    def _locate_data_file_dialog(self):
        """Startup sub-choice after 'Pick a location…': point to an existing
        data file, or create a fresh default file (example tasks) in another
        folder than the default one."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.tr("Data location"))
        box.setText(self.tr("Pick a data location"))
        box.setInformativeText(self.tr(
            "Point to an existing data file, or create a new default file "
            "in another folder?"
        ))
        use_btn = box.addButton(self.tr("Existing file…"), QMessageBox.ButtonRole.AcceptRole)
        create_btn = box.addButton(self.tr("Create a default file…"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(self.tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(use_btn)
        box.exec()

        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is use_btn:
            self._use_existing_data_file(at_startup=True)
        elif clicked is create_btn:
            self._create_default_data_file_elsewhere()

    # ------------------------------------------------------------------
    # Data-location helpers shared by the move / create / use-existing flows
    # ------------------------------------------------------------------

    def _flush_editors(self):
        """Flush every editor's pending debounced edits to disk now."""
        for editor in self._editors.values():
            editor._flush()

    def _stop_editor_timers(self):
        """Cancel every editor's pending debounce timer (drop unsaved edits)."""
        for editor in self._editors.values():
            editor._timer.stop()

    def _ask_destination_path(self, title: str, start_path: str) -> str | None:
        """Save-as dialog for a .json data file. Returns the chosen path (with a
        .json extension and its parent folder created), or None on cancel/error."""
        dest, _ = QFileDialog.getSaveFileName(self, title, start_path, self.tr("JSON files (*.json)"))
        if not dest:
            return None
        if not dest.lower().endswith(".json"):
            dest += ".json"
        dest_dir = os.path.dirname(dest)
        try:
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, title,
                                self.tr("Cannot create the destination folder:\n{0}").format(e))
            return None
        return dest

    def _switch_to_data_file(self, path: str):
        """Persist path as the configured data file, switch the todolist to it,
        and refresh the UI from its content.

        The path is stored in config.INI in its portable form (relative when it
        lives inside the install folder), so a relocation that stays within a
        shared/synced install folder still works on every machine; the running
        session keeps the resolved absolute path in memory."""
        write_config_file(param="json_file_path", value=Path.to_portable(path), menu="PATH")
        Path.json_file_path = path
        self.todolist.set_path(path)
        self._on_remote_change(self.todolist.todolist_dict)

    def _is_pristine_default(self, path: str) -> bool:
        """True if path still holds exactly the default example tasks (an
        untouched startup starter), so it can be safely removed when unused."""
        data = _task_data(path)
        default_data = self.todolist._default_data
        return data is not None and all(
            data.get(loc, []) == default_data.get(loc, [])
            for loc in self.todolist.POSSIBLE_LOC
        )

    def _create_default_data_file_elsewhere(self):
        """Startup: create a fresh default data file (example tasks) at a location
        and name chosen by the user, persist it in config.INI, and use it. The
        unused pristine startup fallback is removed afterwards."""
        old_path = Path.json_file_path
        dest = self._ask_destination_path(
            self.tr("Create a data file"),
            os.path.join(Path.dir_path, self._default_json_name or "param.json"),
        )
        if dest is None:
            return

        old_was_pristine = self._is_pristine_default(old_path)
        self._stop_editor_timers()

        # Force a fresh default at dest (the save dialog already confirmed any
        # overwrite); set_path then seeds the missing file with the example tasks.
        if os.path.exists(dest):
            self._remove_data_file(dest)
        self._switch_to_data_file(dest)

        if old_was_pristine and os.path.abspath(old_path) != os.path.abspath(dest):
            self._remove_data_file(old_path)
        Output.print(f"Data file created: {dest}", level="info")

    def _use_default_data_location(self):
        """Record the default data file as the configured location. The todolist
        already points at the absolute fallback (set at startup), so this just
        persists the relative default in config.INI so the user is not prompted
        again on the next launch."""
        write_config_file(param="json_file_path", value=self._default_json_name, menu="PATH")
        Output.print(f"Using default data location: {self._default_json_name}", level="info")

    def _show_data_location(self):
        """Menu entry: show where the active data file lives, with buttons to
        open the containing folder or change the location."""
        abs_path = os.path.abspath(Path.json_file_path) if Path.json_file_path else ""
        shown = abs_path or self.tr("(not set)")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(self.tr("Data location"))
        box.setText(self.tr("Current data file:\n\n{0}\n").format(shown))
        open_btn = box.addButton(self.tr("Open folder"), QMessageBox.ButtonRole.ActionRole)
        open_btn.setEnabled(bool(abs_path))
        change_btn = box.addButton(self.tr("Change location…"), QMessageBox.ButtonRole.ActionRole)
        ok_btn = box.addButton(QMessageBox.StandardButton.Ok)
        box.setDefaultButton(ok_btn)
        box.exec()
        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is open_btn:
            self._open_folder(os.path.dirname(abs_path))
        elif clicked is change_btn:
            self._change_data_location_dialog()

    def _open_folder(self, path: str):
        """Open `path` in the system file manager (xdg-open under the hood).
        Warns the user if the path is empty or unreachable."""
        if not path or not os.path.isdir(path):
            QMessageBox.warning(
                self, self.tr("Open folder"),
                self.tr("Folder not found:\n{0}").format(path or "(empty)"))
            return
        # QUrl.fromLocalFile on a relative path yields a relative URL
        # (e.g. "file:save") that file managers reject ("Operation not
        # supported"); resolve to an absolute path first.
        path = os.path.abspath(path)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            Output.print(f"Could not open folder: {path}", level="warning")

    def _change_data_location_dialog(self):
        """Menu entry: let the user either point to an existing data file (and
        use it) or move the current data file to a new location/name."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(self.tr("Change data location"))
        box.setText(self.tr("What do you want to do?"))
        box.setInformativeText(self.tr(
            "Point to an existing data file to use, or move the current "
            "file to a new location and name?"
        ))
        use_btn = box.addButton(self.tr("Point to an existing file…"), QMessageBox.ButtonRole.AcceptRole)
        move_btn = box.addButton(self.tr("Move the current file…"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(self.tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(use_btn)
        box.exec()

        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is use_btn:
            self._use_existing_data_file()
        elif clicked is move_btn:
            self._move_data_file()

    def _move_data_file(self):
        """Move the current data file (keeping its content) to a new location and
        name chosen by the user, update config.INI, and keep using it."""
        title = self.tr("Move the data file")
        src = Path.json_file_path
        # Snapshot + flush pending edits so the file on disk is current/recoverable.
        self._flush_editors()
        self._backup_param()

        start_path = os.path.abspath(src) if src else self._default_json_name
        dest = self._ask_destination_path(title, start_path)
        if dest is None or os.path.abspath(dest) == os.path.abspath(src):
            return  # cancelled or same file

        # Stop pending timers and the watcher before moving the backing file.
        self._stop_editor_timers()
        self.todolist.stop_watcher()
        try:
            shutil.move(src, dest)
        except OSError as e:
            QMessageBox.warning(self, title, self.tr("Move failed:\n{0}").format(e))
            self.todolist.set_path(src)  # keep working with the original file
            return
        self._remove_data_file(src)  # src moved; clears its leftover .lock/.tmp

        self._switch_to_data_file(dest)
        Output.print(f"Data file moved: {src} → {dest}", level="info")

    def _use_existing_data_file(self, *, at_startup: bool = False):
        """Pick an existing param JSON file (any name), persist its path in
        config.INI, then load it. Same flow whether triggered from the menu or
        at startup (first launch / missing file) — except startup skips the
        pre-backup (no valid current data to save) and the confirmation."""
        title = self.tr("Change data location")
        if not at_startup:
            # Snapshot the current data first (flush pending edits to disk).
            self._flush_editors()
            self._backup_param()

        start_dir = (os.path.dirname(os.path.abspath(Path.json_file_path))
                     if Path.json_file_path else "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, title, start_dir, self.tr("JSON files (*.json)")
        )
        if not file_path:
            return  # cancelled

        data = _task_data(file_path)
        if data is None:
            QMessageBox.warning(self, title, self.tr("Cannot read the file:\n{0}").format(file_path))
            return

        if self._invalid_quadrants(data):
            QMessageBox.warning(
                self, title,
                self.tr("Invalid file: it does not contain a valid task matrix."),
            )
            return

        if not at_startup and QMessageBox.question(
            self, title,
            self.tr("Use this file as the new data location and load "
                    "its content?\n\n{0}").format(file_path),
        ) != QMessageBox.StandardButton.Yes:
            return

        # First launch / the startup fallback may have left a pristine starter
        # file; note it before switching so we can remove it when the user chose
        # a different location — without ever deleting real data.
        old_path = Path.json_file_path
        old_was_pristine = self._is_pristine_default(old_path)

        self._stop_editor_timers()
        self._switch_to_data_file(file_path)

        if (at_startup and old_was_pristine
                and os.path.abspath(old_path) != os.path.abspath(file_path)):
            self._remove_data_file(old_path)

        Output.print(f"Data location changed: {file_path}", level="info")

    @staticmethod
    def _remove_data_file(path: str):
        """Delete a data file and its .lock/.tmp companions (ignore if absent)."""
        base = os.path.splitext(path)[0]
        for p in (path, base + ".lock", base + ".tmp"):
            try:
                os.remove(p)
            except OSError:
                pass

    def _change_font(self):
        dlg = FontPickerDialog(self._editor_font, self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        font = dlg.selected_font()       # read before deleteLater (widget still alive)
        dlg.deleteLater()
        if not accepted:
            return
        self._editor_font = font
        for editor in self._editors.values():
            editor.setFont(self._editor_font)
        for widget in self._done_widgets.values():
            widget.setFont(self._editor_font)
        write_config_file(param="font", value=self._editor_font.family())
        write_config_file(param="font_size", value=str(self._editor_font.pointSize()))
        Output.print(f"Font changed: '{self._editor_font.family()}' {self._editor_font.pointSize()}pt",
                     level="info")

    @staticmethod
    def _discover_languages() -> list[tuple[str, str]]:
        """Scan translations/eitodo_*.qm and return a sorted (code, label)
        list for the language menu. 'en' is always included (source language,
        no catalog file needed). Labels come from _NATIVE_LANG_NAMES when the
        code is known, otherwise from QLocale.nativeLanguageName() (falls
        back to the bare code if Qt does not recognize it). Sorted by label
        for a stable, alphabetical menu order."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        translations_dir = os.path.join(base_dir, "translations")

        codes: set[str] = {"en"}
        if os.path.isdir(translations_dir):
            for fname in os.listdir(translations_dir):
                m = _QM_RE.match(fname)
                if m:
                    codes.add(m.group(1))

        def label_for(code: str) -> str:
            if code in _NATIVE_LANG_NAMES:
                return _NATIVE_LANG_NAMES[code]
            qname = QLocale(code).nativeLanguageName()
            return (qname[0].upper() + qname[1:]) if qname else code

        return sorted(((c, label_for(c)) for c in codes), key=lambda x: x[1])

    def _change_language(self, code: str):
        """Persist a new UI language and restart the app (after confirmation).

        Hot-swapping a QTranslator on a running window would require every
        widget's text to be re-applied through a retranslateUi() method,
        which we do not have. Restarting via os.execv is fast (<1 s) and
        the shutdown save guarantees no data loss across the swap.
        """
        try:
            current = read_config_file(param="language").strip()
        except (ValueError, OSError):
            current = ""
        if code == current:
            return  # exclusive group still fires triggered on the active item
        if QMessageBox.question(
            self, self.tr("Change language"),
            self.tr("Restart EiTodo to apply the new language?"),
        ) != QMessageBox.StandardButton.Yes:
            # Restore the check state to whatever is actually in effect.
            if current in self._language_actions:
                self._language_actions[current].setChecked(True)
            return
        write_config_file(param="language", value=code)
        Output.print(f"UI language changed from '{current}' to '{code}' — restarting",
                     level="info")
        self._restart_app()

    def _restart_app(self):
        """Save state and re-exec the same interpreter and script. os.execv
        replaces the current process, so no Qt teardown signals fire after
        this — _perform_shutdown_save() must run explicitly first.

        EITODO_LOG_CONTINUE points the next process at the current log file
        so the new session appends to it instead of opening a fresh one,
        avoiding the abrupt cut that os.execv would otherwise leave behind.

        The logind shutdown inhibitor is released explicitly so the
        transition is visible in the log; otherwise CLOEXEC would close
        the dup'd lock fd silently at execv. The new process acquires its
        own inhibitor during startup.

        logging.shutdown() flushes pending writes before the process is
        replaced (no atexit handlers run after execv).
        """
        if Logger.current_log_path:
            os.environ["EITODO_LOG_CONTINUE"] = Logger.current_log_path
        self._perform_shutdown_save()
        inhibitor = getattr(QApplication.instance(), "_shutdown_inhibitor", None)
        if inhibitor is not None:
            inhibitor.release()
        Output.print("Replacing process via os.execv — log continues below",
                     level="info")
        logging.shutdown()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _change_backup_limit(self):
        """Let the user set how many timestamped backups are kept in the save
        folder. Floor of 20 so an accidental tiny value cannot wipe weeks of
        history on the next cleanup; the 'Unlimited' checkbox stores -1, which
        clean_old_backups treats as 'keep everything'. Excess backups beyond
        the new limit are removed immediately via clean_old_backups (deferred
        import: main imports guiqt at module load, so a top-level import
        would be circular)."""
        try:
            current = int(str(read_config_file(param="backups_to_keep")))
        except (ValueError, OSError):
            current = 100
        unlimited = current <= 0
        spin_default = 100 if unlimited else max(20, current)

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Number of backups to keep"))
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            self.tr("Keep up to this many timestamped backups (minimum 20):")))

        spin = QSpinBox(dlg)
        spin.setRange(20, 2_147_483_647)
        spin.setValue(spin_default)
        layout.addWidget(spin)

        check = QCheckBox(self.tr("Unlimited (keep every backup)"), dlg)
        check.setChecked(unlimited)
        spin.setDisabled(unlimited)
        check.toggled.connect(lambda on: spin.setDisabled(on))
        layout.addWidget(check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        value = -1 if check.isChecked() else spin.value()   # read before deleteLater
        dlg.deleteLater()
        if not accepted:
            return
        write_config_file(param="backups_to_keep", value=str(value))
        from main import clean_old_backups
        clean_old_backups()
        Output.print(f"Backup limit set to {value}", level="info")

    def _change_debounce(self):
        """Tune editor responsiveness: the debounce delay before a typed change
        is auto-formatted and saved. Lower is snappier but does work more often;
        higher is lighter while idle. The slider runs in hundreds of
        milliseconds (2..10) so the handle can only land on a 100 ms cran
        between 200 and 1000 ms — no numeric value is shown. 'Restore defaults'
        resets to 400 ms. The chosen value is applied live to every open
        editor's timer and persisted to config."""
        try:
            current = int(str(read_config_file(param="debounce_ms")))
        except (ValueError, OSError):
            current = 400
        current = min(1000, max(200, round(current / 100) * 100))

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Interface responsiveness"))
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(self.tr(
            "Delay before typed changes are formatted and saved.\n"
            "Left: more responsive. Right: lighter on resources.")))

        # Slider in hundreds of milliseconds so every step is one 100 ms cran
        # and the handle cannot land between crans (no rounding needed).
        slider = QSlider(Qt.Orientation.Horizontal, dlg)
        slider.setRange(2, 10)
        slider.setValue(current // 100)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setTickInterval(1)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        layout.addWidget(slider)

        # Default marker (triangle under the 400 ms cran) + end captions, so the
        # otherwise value-less slider still reads at a glance.
        marker = SliderDefaultMarker(slider, 4, dlg)
        marker.setToolTip(self.tr("Default (400 ms)"))
        layout.addWidget(marker)

        captions = QHBoxLayout()
        left_caption = QLabel(self.tr("More responsive"), dlg)
        right_caption = QLabel(self.tr("Lighter"), dlg)
        for cap in (left_caption, right_caption):
            cap.setStyleSheet("color: gray; font-size: 11px;")
        captions.addWidget(left_caption, alignment=Qt.AlignmentFlag.AlignLeft)
        captions.addStretch()
        captions.addWidget(right_caption, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(captions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults,
            parent=dlg)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            lambda: slider.setValue(4))
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        value = slider.value() * 100     # read before deleteLater
        dlg.deleteLater()
        if not accepted:
            return
        write_config_file(param="debounce_ms", value=str(value))
        for editor in self._editors.values():
            editor._timer.setInterval(value)
        self._debounce_ms = value
        Output.print(f"Debounce set to {value} ms", level="info")

    def _show_help(self):
        """Open the help window in the language currently in effect.
        The dialog is modeless (show, not exec) so the user can keep
        editing tasks while reading. A previously opened instance is
        re-raised instead of being duplicated."""
        try:
            lang = read_config_file(param="language").strip() or "en"
        except (ValueError, OSError):
            lang = "en"
        existing = getattr(self, "_help_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        dlg = HelpDialog(lang, self)
        # Modeless: free it (and drop our reference) when closed, so repeated
        # open/close doesn't pile up retained dialogs as children of the window.
        dlg.finished.connect(dlg.deleteLater)
        dlg.finished.connect(lambda *_: setattr(self, "_help_dialog", None))
        self._help_dialog = dlg
        dlg.show()

    def _quit(self):
        self._perform_shutdown_save()
        QApplication.quit()

    def _perform_shutdown_save(self):
        """Persist data and geometry exactly once, regardless of how the app is
        being terminated: the tray 'Quit' action, a SIGTERM, or a desktop
        session end (logout / shutdown / reboot).

        On X11 a session end is delivered through the X Session Management
        Protocol, not as SIGTERM, so the SIGTERM handler never fires and Qt
        quits the event loop on its own — this is the path that left no backup.
        main.py wires this method to QApplication.commitDataRequest (the proper
        'session is ending, save now' hook, display still alive) and to
        aboutToQuit (catch-all for any other exit route); the guard below makes
        the repeated calls harmless.

        The data backup runs first because it is the critical operation;
        _save_geometry() touches the GUI and may fail if the display server is
        already gone during shutdown, so it is best-effort and must not abort
        the backup.
        """
        if self._shutdown_saved:
            return
        self._shutdown_saved = True
        self._stop_editor_timers()
        self._flush_editors()
        self._backup_param()
        try:
            self._save_geometry()
        except Exception as e:
            Output.print(f"Geometry save skipped during shutdown: {e}",
                         level="warning")

    def _hourly_backup(self):
        """Flush pending editor changes to disk, then back up — but only if the
        data actually changed (locally or from another instance) since the last
        backup, so an idle app does no periodic disk work."""
        self._flush_editors()
        if self.todolist.consume_updated_since_backup():
            self._backup_param()

    def _backup_param(self):
        """Save a timestamped copy of the param JSON into the save folder.

        Source path is Path.json_file_path (set at startup from config.INI),
        destination is Path.save_folder with name YYYY_MM_DD_HHMMSS_<name>.json.

        If the task data is unchanged since the most recent backup (sync
        metadata excluded), no backup is made: the existing one keeps its real
        timestamp (no duplicate, no artificial rename).
        """
        src = Path.json_file_path
        if not os.path.isfile(src):
            Output.print(f"Param backup skipped: file not found: {src}", level="error")
            return
        name = os.path.splitext(os.path.basename(src))[0]
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
        dest = os.path.join(Path.save_folder, f"{timestamp}_{name}.json")

        last = _latest_backup(Path.save_folder, name)
        src_data = _task_data(src)
        if last is not None and src_data is not None and src_data == _task_data(last):
            # Identical content already backed up: no duplicate, and keep the
            # existing backup's real timestamp (no artificial rename).
            return

        # Changed data: this second's backup must never overwrite an earlier
        # one. If the file already exists (two backups within the same second),
        # wait for the next second and recompute the name so each backup keeps
        # its own file.
        while os.path.exists(dest):
            time.sleep(0.25)
            timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
            dest = os.path.join(Path.save_folder, f"{timestamp}_{name}.json")

        try:
            shutil.copy2(src, dest)
            Output.print(f"Param backup: {dest}", level="info")
        except OSError as e:
            Output.print(f"Param backup failed: {e}", level="error")

    def _save_geometry(self):
        # One read + one write of config.INI for all geometry keys, instead of
        # five read+rewrite cycles (one per write_config_file call).
        screen = self.screen()
        write_config_file_values({
            "window_width":  str(self.width()),
            "window_height": str(self.height()),
            "window_x":      str(self.x()),
            "window_y":      str(self.y()),
            "window_screen": screen.name() if screen else "",
        })

    def _on_tray_activated(self, reason):
        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        # Hide only when already in the foreground; otherwise bring to front.
        # On window managers where a tray click steals focus, isActiveWindow()
        # is False here, so this gracefully degrades to "always show" — hide
        # then happens via the window's close (X) button.
        if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()  # also restores from a minimized state
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event):
        self._save_geometry()
        # Hide to tray instead of closing; quit from the tray menu to exit
        event.ignore()
        self.hide()
