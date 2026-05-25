#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" GUI in Qt6"""
import os
import re
import json
import shutil
import datetime

from custom_path import Path
from general import (read_config_file, write_config_file,
                     is_empty, clean_line, clean_text, snapshot, get_raw)
from output import Output
from todolist import ToDoList

from PyQt6.QtGui import QFont, QIcon, QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QMainWindow, QPlainTextEdit, QSizePolicy, QTextEdit,
    QSystemTrayIcon, QMenu, QFileDialog, QMessageBox,
    QDialog, QDialogButtonBox, QSlider, QLineEdit, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal

_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

QUADRANT_KEYS = {
    "Urgent & Important":       ("U&I",   "U&I_done"),
    "Not Urgent & Important":   ("NU&I",  "NU&I_done"),
    "Urgent & Unimportant":     ("U&Un",  "U&Un_done"),
    "Not Urgent & Unimportant": ("NU&Un", "NU&Un_done"),
}

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

class TrackedTextEdit(QPlainTextEdit):
    items_erased = pyqtSignal(list)  # list of raw items fully removed from the text

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
        cleaned = clean_text(text)
        if cleaned != text:
            cursor = self.textCursor()
            block_num = cursor.blockNumber()
            col = cursor.positionInBlock()
            raw_lines = text.splitlines()

            # Map block_num in raw text → block_num in cleaned text (empty lines removed)
            new_block_num = sum(1 for l in raw_lines[:block_num] if not is_empty(l))

            # Map column: raw line has variable prefix, cleaned line always starts with "• "
            new_col = 2  # fallback: just after "• "
            if block_num < len(raw_lines):
                raw_line = raw_lines[block_num]
                if not is_empty(raw_line):
                    s = raw_line.lstrip()
                    leading = len(raw_line) - len(s)
                    after_bullet = s[1:].lstrip() if s.startswith("•") else s
                    content_start = len(raw_line) - len(after_bullet)
                    content_col = max(0, col - content_start)
                    new_col = 2 + content_col  # "• " prefix is always 2 chars

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
            current_vals = set(current.values())
            appeared = list(set(current.values()) - set(self._snap.values()))
            # Gone items ordered by original position (first line = most likely edited)
            gone_ordered = [v for _, v in sorted(
                (pos, val) for pos, val in self._snap.items() if val not in current_vals
            )]
            if gone_ordered:
                # Greedily pair gone items with appeared items via prefix relation (= edit)
                remaining = list(appeared)
                truly_erased = []
                for g in gone_ordered:
                    match = next((a for a in remaining if g.startswith(a) or a.startswith(g)), None)
                    if match is not None:
                        remaining.remove(match)
                    else:
                        truly_erased.append(g)
                raw_erased = [get_raw(line)[0] for line in truly_erased if get_raw(line)]
                if raw_erased:
                    self.items_erased.emit(raw_erased)
            self.todolist.set_quadrant(self.loc, get_raw(self.toPlainText()))
        self._snap = current

    def mousePressEvent(self, event):
        """Ctrl+click on a URL opens it instead of moving the cursor."""
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            url = self._url_at(self.cursorForPosition(event.position().toPoint()))
            if url:
                QDesktopServices.openUrl(QUrl(url))
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Track the cursor position and update the link-hover cursor."""
        self._last_mouse_pos = event.position().toPoint()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self._update_link_cursor(ctrl)
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._update_link_cursor(True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control:
            self._update_link_cursor(False)
        super().keyReleaseEvent(event)

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
        or None if it is not a link. 'www.' tokens get an http:// scheme."""
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
        match = _URL_RE.search(text[start:end])
        if not match:
            return None
        url = match.group(0).rstrip(".,;:!?)]}>\"'")
        if url.lower().startswith("www."):
            url = "http://" + url
        return url


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
        self.setWindowTitle("Changer la police")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Police :"))
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
        size_row.addWidget(QLabel("Taille :"))
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(_SIZE_MIN, _SIZE_MAX)
        self._slider.setValue(current_size)
        self._size_edit = QLineEdit(str(current_size))
        self._size_edit.setFixedWidth(45)
        size_row.addWidget(self._slider, 1)
        size_row.addWidget(self._size_edit)
        layout.addLayout(size_row)

        layout.addWidget(QLabel("Aperçu :"))
        self._preview = QLabel("• Tâche urgente et importante\n• Autre exemple de tâche")
        self._preview.setStyleSheet("border: 1px solid gray; padding: 6px; background: white;")
        self._preview.setWordWrap(True)
        self._preview.setMinimumHeight(60)
        layout.addWidget(self._preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
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
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    _remote_change = pyqtSignal(dict)

    def __init__(self, todolist: ToDoList, debounce_ms: int = 500,
                 width: int = 1000, height: int = 1000,
                 x: int = 0, y: int = 0, screen_name: str = "",
                 prompt_data_location: bool = False, default_json_name: str = "",
                 font: str = "", font_size: int = 11):
        super().__init__()
        self.todolist = todolist
        self._debounce_ms = debounce_ms
        self._editors: dict[str, TrackedTextEdit] = {}
        self._done_widgets: dict[str, QTextEdit] = {}
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
        clamped_x = max(sg.x(), min(x, sg.x() + sg.width()  - width))
        clamped_y = max(sg.y(), min(y, sg.y() + sg.height() - height))
        self.setGeometry(clamped_x, clamped_y, width, height)

        self.setWindowTitle('Eisenhower Todo-List')
        icon = QIcon(Path.icon_path)
        self.setWindowIcon(icon)

        # Hide from taskbar (Tool windows don't get a taskbar button)
        self.setWindowFlag(Qt.WindowType.Tool)

        # System tray icon
        self._tray = QSystemTrayIcon(icon, self)
        tray_menu = QMenu()
        clear_done_action = QAction(QIcon.fromTheme("edit-clear"), "Effacer toutes les tâches finies", self)
        clear_done_action.triggered.connect(self._clear_all_done)
        tray_menu.addAction(clear_done_action)
        tray_menu.addSeparator()
        load_backup_action = QAction(QIcon.fromTheme("document-open"), "Charger une sauvegarde", self)
        load_backup_action.triggered.connect(self._load_backup)
        tray_menu.addAction(load_backup_action)
        change_location_action = QAction(QIcon.fromTheme("folder-open"), "Changer l'emplacement des données", self)
        change_location_action.triggered.connect(self._change_data_location_dialog)
        tray_menu.addAction(change_location_action)
        change_font_action = QAction(QIcon.fromTheme("preferences-desktop-font"), "Changer la police…", self)
        change_font_action.triggered.connect(self._change_font)
        tray_menu.addAction(change_font_action)
        tray_menu.addSeparator()
        start_hidden_action = QAction("Caché au démarrage", self)
        start_hidden_action.setCheckable(True)
        start_hidden_action.setChecked(read_config_file(param="start_hidden").strip().lower() == "true")
        start_hidden_action.toggled.connect(lambda checked: (
            write_config_file("start_hidden", str(checked).lower()),
            Output.print(f"Start hidden: {checked}", level="info"),
        ))
        tray_menu.addAction(start_hidden_action)
        tray_menu.addSeparator()
        quit_action = QAction(QIcon.fromTheme("application-exit"), "Quitter", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)
        self._tray.setContextMenu(tray_menu)
        self._tray.setToolTip("Eisenhower Todo-List")
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        # Route remote-file changes (background thread) safely to the main thread
        todolist.set_on_remote_change(self._remote_change.emit)
        self._remote_change.connect(self._on_remote_file_change)

        # Hourly backup: writes a new param backup, or just refreshes the
        # timestamp of the last one when nothing changed (see _backup_param).
        self._backup_timer = QTimer(self)
        self._backup_timer.setInterval(60 * 60 * 1000)  # 1 hour
        self._backup_timer.timeout.connect(self._hourly_backup)
        self._backup_timer.start()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        top_row    = QHBoxLayout()
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
            square.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            square.setStyleSheet(f"QWidget {{ border: 2px solid gray; background-color: {color}; padding: 8px; }}")
            square_layout = QVBoxLayout(square)

            label = QLabel(title)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-weight: bold; border: none;")
            square_layout.addWidget(label)

            editor = TrackedTextEdit(todolist, loc, self._debounce_ms)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            editor.setStyleSheet("border: 1px solid gray; background-color: white;")
            editor.setFont(self._editor_font)
            editor.set_content(todolist.todolist_dict.get(loc, []))
            self._editors[loc] = editor

            done_widget = QTextEdit()
            done_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            done_widget.setStyleSheet("border: 1px solid gray; background-color: white;")
            done_widget.setFont(self._editor_font)
            done_widget.setReadOnly(True)
            self._fill_done_widget(done_widget, todolist.todolist_dict.get(loc_done, []))
            self._done_widgets[loc_done] = done_widget

            editor.items_erased.connect(
                lambda items, ld=loc_done, dw=done_widget: self._on_erased(ld, dw, items)
            )

            square_layout.addWidget(editor)
            square_layout.addWidget(done_widget)
            row_layout.addWidget(square, 1)

        # First launch or a missing data file: once the event loop is running,
        # ask where to store data (same flow as changing the location manually).
        if prompt_data_location:
            QTimer.singleShot(0, self._prompt_data_location)

    def _on_erased(self, loc_done: str, done_widget: QTextEdit, raw_items: list[str]):
        current_done = list(self.todolist.todolist_dict.get(loc_done, []))
        for item in raw_items:
            if item not in current_done:
                current_done.insert(0, item)
        current_done = current_done[:10]
        self.todolist.set_quadrant(loc_done, current_done)
        self._fill_done_widget(done_widget, current_done)

    def _on_remote_file_change(self, data: dict):
        """Slot for the remote-change signal: a *different* instance modified the
        shared data file. Logged here (unlike the internal UI refreshes that also
        call _on_remote_change), then the editors are refreshed on the main thread."""
        Output.print(f"Remote change received from another instance "
                     f"(version {data.get('version', '?')})", level="info")
        self._on_remote_change(data)

    def _on_remote_change(self, data: dict):
        """Update all editors and done-widgets from a remote file change (main thread)."""
        for loc, editor in self._editors.items():
            editor.set_content(data.get(loc, []))
        for loc, widget in self._done_widgets.items():
            self._fill_done_widget(widget, data.get(loc, []))

    def _clear_all_done(self):
        for loc_done, widget in self._done_widgets.items():
            self.todolist.set_quadrant(loc_done, [])
            self._fill_done_widget(widget, [])
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
            self, "Charger une sauvegarde", start_dir, "Sauvegardes JSON (*.json)"
        )
        if not file_path:
            return  # cancelled

        data = _task_data(file_path)
        if data is None:
            QMessageBox.warning(
                self, "Charger une sauvegarde",
                f"Impossible de lire la sauvegarde :\n{file_path}",
            )
            return

        if self._invalid_quadrants(data):
            QMessageBox.warning(
                self, "Charger une sauvegarde",
                "Sauvegarde invalide : le fichier est incorrect :\n",
            )
            return

        if QMessageBox.question(
            self, "Charger une sauvegarde",
            "Remplacer toutes les tâches actuelles par le contenu de\n"
            f"{os.path.basename(file_path)} ?",
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
        box.setWindowTitle("Emplacement des données")
        box.setText("Où souhaitez-vous stocker les données ?")
        box.setInformativeText(
            "Utiliser l'emplacement par défaut, ou indiquer un fichier de "
            "données existant ?"
        )
        default_btn = box.addButton("Emplacement par défaut", QMessageBox.ButtonRole.AcceptRole)
        locate_btn = box.addButton("Indiquer l'emplacement…", QMessageBox.ButtonRole.ActionRole)
        box.setDefaultButton(default_btn)
        box.exec()

        if box.clickedButton() is locate_btn:
            self._locate_data_file_dialog()
        else:
            self._use_default_data_location()

    def _locate_data_file_dialog(self):
        """Startup sub-choice for 'Indiquer l'emplacement': point to an existing
        data file, or create a fresh default file (example tasks) in another
        folder than the default one."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Emplacement des données")
        box.setText("Indiquer l'emplacement des données")
        box.setInformativeText(
            "Pointer vers un fichier de données existant, ou créer un nouveau "
            "fichier par défaut dans un autre dossier ?"
        )
        use_btn = box.addButton("Fichier existant…", QMessageBox.ButtonRole.AcceptRole)
        create_btn = box.addButton("Créer un fichier par défaut…", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(use_btn)
        box.exec()

        clicked = box.clickedButton()
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
        dest, _ = QFileDialog.getSaveFileName(self, title, start_path, "Fichiers JSON (*.json)")
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
                                f"Impossible de créer le dossier de destination :\n{e}")
            return None
        return dest

    def _switch_to_data_file(self, path: str):
        """Persist path as the configured data file, switch the todolist to it,
        and refresh the UI from its content."""
        write_config_file(param="json_file_path", value=path, menu="PATH")
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
            "Créer un fichier de données",
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

    def _change_data_location_dialog(self):
        """Menu entry: let the user either point to an existing data file (and
        use it) or move the current data file to a new location/name."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Changer l'emplacement des données")
        box.setText("Que voulez-vous faire ?")
        box.setInformativeText(
            "Indiquer un fichier de données existant à utiliser, ou déplacer "
            "le fichier actuel vers un nouvel emplacement et nom ?"
        )
        use_btn = box.addButton("Indiquer un fichier existant…", QMessageBox.ButtonRole.AcceptRole)
        move_btn = box.addButton("Déplacer le fichier actuel…", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(use_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is use_btn:
            self._use_existing_data_file()
        elif clicked is move_btn:
            self._move_data_file()

    def _move_data_file(self):
        """Move the current data file (keeping its content) to a new location and
        name chosen by the user, update config.INI, and keep using it."""
        title = "Déplacer le fichier de données"
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
            QMessageBox.warning(self, title, f"Échec du déplacement :\n{e}")
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
        title = "Changer l'emplacement des données"
        if not at_startup:
            # Snapshot the current data first (flush pending edits to disk).
            self._flush_editors()
            self._backup_param()

        start_dir = (os.path.dirname(os.path.abspath(Path.json_file_path))
                     if Path.json_file_path else "")
        file_path, _ = QFileDialog.getOpenFileName(
            self, title, start_dir, "Fichiers JSON (*.json)"
        )
        if not file_path:
            return  # cancelled

        data = _task_data(file_path)
        if data is None:
            QMessageBox.warning(self, title, f"Impossible de lire le fichier :\n{file_path}")
            return

        if self._invalid_quadrants(data):
            QMessageBox.warning(
                self, title,
                "Fichier invalide : il ne contient pas une matrice de tâches valide.",
            )
            return

        if not at_startup and QMessageBox.question(
            self, title,
            "Utiliser ce fichier comme nouvel emplacement des données et "
            f"charger son contenu ?\n\n{file_path}",
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
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._editor_font = dlg.selected_font()
        for editor in self._editors.values():
            editor.setFont(self._editor_font)
        for widget in self._done_widgets.values():
            widget.setFont(self._editor_font)
        write_config_file(param="font", value=self._editor_font.family())
        write_config_file(param="font_size", value=str(self._editor_font.pointSize()))
        Output.print(f"Font changed: '{self._editor_font.family()}' {self._editor_font.pointSize()}pt",
                     level="info")

    def _quit(self):
        self._perform_shutdown_save()
        QApplication.quit()

    def _perform_shutdown_save(self):
        """Persist data and geometry exactly once, regardless of how the app is
        being terminated: the tray 'Quitter' action, a SIGTERM, or a desktop
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
        """Flush any pending editor changes to disk, then run a backup."""
        self._flush_editors()
        self._backup_param()

    def _backup_param(self):
        """Save a timestamped copy of the param JSON into the save folder.

        Source path is Path.json_file_path (set at startup from config.INI),
        destination is Path.save_folder with name YYYY_MM_DD_HHMMSS_<name>.json.

        If the task data is unchanged since the most recent backup (sync
        metadata excluded), no duplicate is created: the existing backup is
        renamed to the new timestamp instead.
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
            # No change since last backup: refresh its timestamp instead of duplicating
            if os.path.abspath(last) != os.path.abspath(dest):
                try:
                    os.replace(last, dest)
                    Output.print(f"No change since last backup: "
                                 f"{os.path.basename(last)} → {os.path.basename(dest)}",
                                 level="info")
                except OSError as e:
                    Output.print(f"Failed to rename backup: {e}", level="error")
            return

        try:
            shutil.copy2(src, dest)
            Output.print(f"Param backup: {dest}", level="info")
        except OSError as e:
            Output.print(f"Param backup failed: {e}", level="error")

    def _save_geometry(self):
        write_config_file("window_width",  str(self.width()))
        write_config_file("window_height", str(self.height()))
        write_config_file("window_x",      str(self.x()))
        write_config_file("window_y",      str(self.y()))
        screen = self.screen()
        write_config_file("window_screen", screen.name() if screen else "")

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

    def _fill_done_widget(self, widget: QTextEdit, items: list):
        widget.setHtml("<br>".join(f"<s>{clean_line(item)}</s>" for item in items if item))
