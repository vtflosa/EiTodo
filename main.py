#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" main program manage Eisenhower TODO matrix
    the matrix is as follow :
        - Urgent & Important tasks/projects to be completed immediately
        - Not Urgent & Important tasks/projects to be scheduled on your calendar
        - Urgent & Unimportant tasks/projects to be delegated to someone else
        - Not Urgent & Unimportant tasks/projects to be deleted or done on leisure time
        ["U&I", "U&I_done", "NU&I", "NU&I_done", "U&Un", "U&Un_done", "NU&Un", "NU&Un_done"]
"""

# general imports
import os
import re
import json
import signal
import socket
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import (QCoreApplication, QLibraryInfo, QLocale, QObject,
                          QSocketNotifier, QTranslator, pyqtSlot)
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusReply

# local imports
from logger import Logger as Log
from custom_path import Path
from output import Output
from version import version
from general import (read_config_file, read_config_file_menu,
                     write_config_file, write_config_file_menu,
                     get_timestamp_with_date)
from todolist import ToDoList
from guiqt import MainWindow as gui


#  todo create a linux installer
#
#  todo     essayer install, et demander si a mettre en startup automatique

# todo vérifi install et mise à jour si nouveau fichier


# todo tout relire pour vérifier

_DEFAULT_CONFIG = {
    "first_launch": "True",
    "debounce_ms": "250",
    "window_width": "900",
    "window_height": "900",
    "window_x": "0",
    "window_y": "0",
    "window_screen": "",
    "start_hidden": "false",
    "backups_to_keep": "100",
    "font": "DejaVu Sans",
    "font_size": "10",
    # UI language code, e.g. 'fr', 'en'. Empty = auto-detect from system locale.
    "language": "",
}

_DEFAULT_PATH = {
    "log_folder_path": "logs",
    "save_folder_path": "save",
    "json_file_path": "param.json"}

def _default_param() -> dict:
    """Default task data, built lazily so the QTranslator (installed in main())
    is in place when the example task strings are looked up. The translate()
    call is written out in full (not via an alias) so pylupdate6 can extract
    these strings into the catalog."""
    return {
        "version": 0,
        "updated_at": 0.0,
        "last_writer": "",
        "U&I":      [QCoreApplication.translate("DefaultTasks", "Write tasks to do here")],
        "U&I_done": [QCoreApplication.translate("DefaultTasks", "Finished tasks appear here")],
        "NU&I": [], "NU&I_done": [],
        "U&Un": [], "U&Un_done": [],
        "NU&Un": [], "NU&Un_done": [],
    }


def _install_translators(app: QApplication) -> str:
    """Pick the UI language and install the matching QTranslator(s) on app.

    Resolution order:
      1. The 'language' code in config.INI [CONFIG], if a matching
         eitodo_<lang>.qm catalog exists.
      2. The system locale (QLocale.system()), if its catalog exists.
      3. English — the source language, no catalog needed.

    Loads Qt's own qtbase_<lang>.qm too so framework strings (Cancel button,
    file-dialog chrome…) match. Translator references are kept alive by
    attaching them to the app object.

    Returns the language code that was actually applied (always concrete,
    never empty). The caller persists it back to config.INI so the user
    sees which language is in effect.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    translations_dir = os.path.join(base_dir, "translations")

    try:
        requested = str(read_config_file(param="language")).strip()
    except (ValueError, OSError):
        requested = ""

    sys_name = QLocale.system().name()  # e.g. 'fr_FR' or '' if undefined
    sys_lang = sys_name.split("_")[0] if sys_name else ""

    # Ordered, deduplicated candidates: explicit choice first, then system.
    candidates: list[str] = []
    for c in (requested, sys_lang):
        if c and c not in candidates:
            candidates.append(c)

    for lang in candidates:
        if lang == "en":
            return "en"  # English source — no catalog needed
        app_translator = QTranslator(app)
        if app_translator.load(f"eitodo_{lang}", translations_dir):
            app.installTranslator(app_translator)
            app._eitodo_translator = app_translator  # prevent GC
            qt_translator = QTranslator(app)
            qt_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if qt_translator.load(f"qtbase_{lang}", qt_path):
                app.installTranslator(qt_translator)
                app._qtbase_translator = qt_translator  # prevent GC
            return lang

    return "en"


def set_and_check_paths() -> bool:
    """Set paths to the working folders/files from the config file and verify.

    The log and save folders are app-internal and must exist (raises if not).
    The json data file may be user-relocated, so its absence is not fatal: it
    is reported via the return value instead, letting the GUI prompt for a new
    location.

    Returns:
        True if the configured json data file exists, False otherwise.
    """
    try:
        cfg = read_config_file_menu(menu="PATH")
        Path.log_folder = cfg["log_folder_path"]
        Path.check_folder(Path.log_folder)

        Path.save_folder = cfg["save_folder_path"]
        Path.check_folder(Path.save_folder)

        Path.json_file_path = cfg["json_file_path"]
    except FileNotFoundError as e:
        Output.print(f"Path error: {e}", level="error")
        raise FileNotFoundError(f"Error in path : {e}")

    return os.path.isfile(Path.json_file_path)


_BACKUP_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_\d{6}_.*\.json$")


def clean_old_backups():
    """Delete excess timestamped backups in Path.save_folder, keeping only the
    most recent 'backups_to_keep' (config.INI). 0 (or less) means unlimited:
    keep everything. The YYYY_MM_DD_HHMMSS_ prefix sorts chronologically, so
    lexical sort gives oldest-first."""
    try:
        keep = int(str(read_config_file(param="backups_to_keep")))
    except ValueError:
        keep = int(_DEFAULT_CONFIG["backups_to_keep"])
        Output.print(f"'backups_to_keep' invalid in config.INI — using default: "
                     f"{keep}", level="warning")

    if keep <= 0:
        return  # unlimited — keep all backups

    backups = sorted(f for f in os.listdir(Path.save_folder) if _BACKUP_RE.match(f))
    to_delete = backups[:-keep]
    for old in to_delete:
        try:
            os.remove(os.path.join(Path.save_folder, old))
        except OSError as e:
            Output.print(f"Could not delete backup {old}: {e}", level="error")
    if to_delete:
        Output.print(f"Deleted {len(to_delete)} old backup(s) (limit: {keep})",
                     level="info")


def first_launch() -> bool:
    """If first_launch=True in config.INI: create the working folders and an
    initial param.json, then return True (otherwise False). All default
    folder/file names come from _DEFAULT_PATH, the single source of truth.
    """

    # check if this is the first launch
    if not os.path.isfile(Path.config_file_path):
        with open(Path.config_file_path, "w", encoding="utf8") as f:
            pass
        write_config_file_menu(menu="CONFIG", data=_DEFAULT_CONFIG)
        write_config_file_menu(menu="PATH", data=_DEFAULT_PATH)

    cfg = read_config_file_menu(menu="CONFIG")
    if cfg["first_launch"].strip().lower() != "true":
        return False

    # create necessary folders and the default data file
    os.makedirs(os.path.join(Path.dir_path, _DEFAULT_PATH["log_folder_path"]), exist_ok=True)
    os.makedirs(os.path.join(Path.dir_path, _DEFAULT_PATH["save_folder_path"]), exist_ok=True)
    Path.json_file_path = os.path.join(Path.dir_path, _DEFAULT_PATH["json_file_path"])

    # do not overwrite param.json if it already exists
    if not os.path.isfile(Path.json_file_path):
        with open(Path.json_file_path, "w", encoding="utf8") as f:
            json.dump(_default_param(), f, indent=4)

    write_config_file_menu(menu="CONFIG", data=_DEFAULT_CONFIG)
    write_config_file_menu(menu="PATH", data=_DEFAULT_PATH)

    # reset first_launch flag
    write_config_file(param="first_launch", value="False", menu="CONFIG")
    # The first-launch event is logged by the caller once the logger is up
    # (the logger needs the paths this function creates), so it lands in the file.
    return True


class ShutdownInhibitor(QObject):
    """Hold a systemd-logind *delay* inhibitor lock so EiTodo gets a guaranteed
    (bounded) window to back up param.json on reboot / shutdown.

    Why: on a real reboot NONE of the in-process hooks (SIGTERM, XSMP
    commitDataRequest, aboutToQuit) get a chance to run — logind sends SIGTERM
    then SIGKILL almost immediately and the process is gone before any Python
    handler executes (confirmed by the reboot-test log). A 'delay' lock flips
    the contract: logind emits PrepareForShutdown(true) and then *waits* for us
    to release the lock (up to InhibitDelayMaxSec, 5 s by default) before
    continuing. That wait IS our save window. The lock is just an open file
    descriptor: closing it (or the process dying) releases it, so it can NEVER
    block a shutdown indefinitely.
    """

    _SERVICE = "org.freedesktop.login1"
    _PATH    = "/org/freedesktop/login1"
    _IFACE   = "org.freedesktop.login1.Manager"

    def __init__(self, on_shutdown, parent=None):
        super().__init__(parent)
        self._on_shutdown = on_shutdown   # save callback (idempotent)
        self._lock_fd = -1                # OUR dup of the inhibitor fd
        self._bus = QDBusConnection.systemBus()
        if not self._bus.isConnected():
            Output.print("Shutdown inhibitor: no D-Bus system bus — "
                         "falling back to SIGTERM/XSMP hooks", level="warning")
            return
        self._bus.connect(self._SERVICE, self._PATH, self._IFACE,
                          "PrepareForShutdown", self._on_prepare_for_shutdown)
        self._acquire()

    def _acquire(self):
        """Take a 'delay' lock on 'shutdown' and keep the fd open."""
        manager = QDBusInterface(self._SERVICE, self._PATH, self._IFACE, self._bus)
        reply = QDBusReply(manager.call(
            "Inhibit", "shutdown", "EiTodo",
            "Back up param.json before shutdown", "delay"))
        if not reply.isValid():
            Output.print(f"Shutdown inhibitor: Inhibit() failed: "
                         f"{reply.error().message()}", level="warning")
            return
        qfd = reply.value()               # QDBusUnixFileDescriptor (owns its fd)
        # Dup into a fd WE own, so releasing the lock is a deterministic
        # os.close() instead of relying on Python GC of the Qt wrapper.
        self._lock_fd = os.dup(qfd.fileDescriptor())
        Output.print("Shutdown inhibitor: 'delay' lock acquired "
                     "(logind will wait for us before powering off)", level="info")

    @pyqtSlot(bool)
    def _on_prepare_for_shutdown(self, starting):
        # starting=False => a previously announced shutdown was cancelled: no-op.
        if not starting:
            return
        Output.print("Shutdown path: logind PrepareForShutdown", level="info")
        self._on_shutdown()               # _perform_shutdown_save() (idempotent)
        QApplication.quit()               # clean exit -> the finally logs END
        # Note: we do NOT release the lock here. We keep it until main()'s
        # finally so logind keeps waiting while we write END OF PROGRAM.

    def release(self):
        """Release the lock (idempotent). Called last, in main()'s finally."""
        if self._lock_fd >= 0:
            try:
                os.close(self._lock_fd)
            except OSError:
                pass
            self._lock_fd = -1
            Output.print("Shutdown inhibitor: lock released", level="info")


def main():

    # QApplication and translators must exist before first_launch(): the
    # default-task strings written into the initial param.json go through
    # QCoreApplication.translate() via _default_param(), and that lookup
    # only finds anything once a QTranslator is installed.
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    resolved_lang = _install_translators(app)

    # first_launch() creates the config file and working folders; only then can
    # set_and_check_paths() resolve Path.log_folder for the logger below.
    first_launch_start = first_launch()
    json_exists = set_and_check_paths()

    # Start logging as early as the paths allow, so every event below (including
    # the first-launch notice) is captured in the log file. EITODO_LOG_CONTINUE
    # is set by _restart_app() before os.execv so the new process appends to
    # the previous process's log; we pop it so an unrelated next launch starts
    # a fresh file.
    continue_log = os.environ.pop("EITODO_LOG_CONTINUE", None)
    log = Log(Path.log_folder, 20, continue_from=continue_log)
    Output.print(version())

    # Always log the active UI language at startup so the log file documents
    # which language the user actually sees, even when no fallback was needed.
    # Persist the resolved value to config.INI only when it differs from what
    # was requested (auto-detect, or fallback for a missing catalog).
    try:
        requested = str(read_config_file(param="language")).strip()
    except (ValueError, OSError):
        requested = ""
    req_display = requested if requested else "(auto)"
    Output.print(f"UI language: requested='{req_display}', resolved='{resolved_lang}'",
                 level="info")
    if requested != resolved_lang:
        try:
            write_config_file(param="language", value=resolved_lang)
        except (ValueError, OSError):
            pass

    if first_launch_start:
        Output.print("First launch: working folders and default data file created",
                     level="info")

    # delete excess timestamped backups in the save folder
    clean_old_backups()

    inhibitor = None  # set inside the try; referenced in finally to release it
    try:
        # ##################### MAIN LOGIC  ###########################
        # If the configured data file is missing, fall back to the in-app
        # default so the app can start without touching the user's folder.
        if not json_exists:
            Output.print(f"Configured data file not found: {Path.json_file_path}",
                         level="error")
            Path.json_file_path = os.path.join(Path.dir_path, _DEFAULT_PATH["json_file_path"])

        # On a first launch or a missing data file, the window asks the user to
        # keep the default location or point to an existing file (unified flow).
        prompt_data_location = first_launch_start or not json_exists

        Output.print(f"Loading data: {Path.json_file_path}", level="info")
        todolist = ToDoList(Path.json_file_path, default_data=_default_param())
        debounce_ms  = int(str(read_config_file(param="debounce_ms")))
        win_width    = int(str(read_config_file(param="window_width")))
        win_height   = int(str(read_config_file(param="window_height")))
        win_x        = int(str(read_config_file(param="window_x")))
        win_y        = int(str(read_config_file(param="window_y")))
        win_screen   = str(read_config_file(param="window_screen")).strip()
        start_hidden = str(read_config_file(param="start_hidden")).strip().lower() == "true"
        try:
            font = str(read_config_file(param="font")).strip()
        except ValueError:
            font = _DEFAULT_CONFIG["font"]
            write_config_file(param="font", value=font)
        try:
            font_size = int(str(read_config_file(param="font_size")))
        except ValueError:
            font_size = int(_DEFAULT_CONFIG["font_size"])
            write_config_file(param="font_size", value=_DEFAULT_CONFIG["font_size"])

        window = gui(todolist=todolist, debounce_ms=debounce_ms,
                     width=win_width, height=win_height,
                     x=win_x, y=win_y, screen_name=win_screen,
                     prompt_data_location=prompt_data_location,
                     default_json_name=_DEFAULT_PATH["json_file_path"],
                     font=font, font_size=font_size)

        # ---- Shutdown / exit save hooks --------------------------------------
        # EiTodo must back up param.json on the way out, whatever the exit route.
        # Different routes need different hooks, so three complementary layers are
        # installed, all funnelling into the idempotent _perform_shutdown_save()
        # (its _shutdown_saved guard makes the repeated calls harmless):
        #
        #   1. systemd-logind delay inhibitor  -> reboot / shutdown / poweroff
        #   2. XSMP commitDataRequest          -> graphical logout (X11)
        #      + aboutToQuit                    -> tray "Quit" and any other exit
        #   3. SIGTERM / SIGHUP                 -> `kill`, non-graphical termination
        #
        # Layer 1 is the one that actually fires on a real reboot: logind kills
        # the process too fast for any in-process handler to run, so we ask it to
        # wait for us first (see ShutdownInhibitor). The proof a save happened is
        # the "Param backup:" log line, so the messages below only name the route.

        # 1. logind delay inhibitor (primary reboot/shutdown path). Keep the
        # reference so it is not garbage-collected while the app runs, and
        # expose it on the app so the language-change restart in guiqt can
        # release it explicitly before os.execv (CLOEXEC would also release
        # it silently, but the explicit call logs the transition).
        inhibitor = ShutdownInhibitor(window._perform_shutdown_save)
        app._shutdown_inhibitor = inhibitor

        # 2. Graphical session end. Under X11 a logout is delivered via the X
        # Session Management Protocol, not as a signal: Qt emits commitDataRequest
        # (display still alive, "save now") and then quits its own event loop,
        # which also emits aboutToQuit as the catch-all for any other exit.
        def _on_commit_data(_mgr):
            Output.print("Shutdown path: commitDataRequest (XSMP session end)",
                         level="info")
            window._perform_shutdown_save()

        def _on_about_to_quit():
            Output.print("Shutdown path: aboutToQuit", level="info")
            window._perform_shutdown_save()

        app.commitDataRequest.connect(_on_commit_data)
        app.aboutToQuit.connect(_on_about_to_quit)

        # 3. POSIX signals (`kill`, or a systemd user session that signals its
        # processes). While app.exec() is idle it is blocked in Qt's C++ event
        # loop, so a pure-Python signal handler would not run until the
        # interpreter regains control. set_wakeup_fd() bridges that: CPython's
        # C-level handler writes the signal number into a socket, waking the
        # QSocketNotifier to run _dispatch_signal() in the main thread. A Python
        # handler must still be registered per signal, otherwise CPython does not
        # write to the wakeup fd.
        _sig_r, _sig_w = socket.socketpair()
        _sig_r.setblocking(False)
        _sig_w.setblocking(False)

        def _dispatch_signal():
            try:
                data = _sig_r.recv(256)
            except OSError:
                return
            for signum in data:  # set_wakeup_fd writes the signal number as one byte
                try:
                    sig_name = signal.Signals(signum).name
                except ValueError:
                    continue
                Output.print(f"Shutdown path: OS signal ({sig_name}) received",
                             level="info")
                window._quit()

        _sig_notifier = QSocketNotifier(_sig_r.fileno(), QSocketNotifier.Type.Read)
        _sig_notifier.activated.connect(lambda _fd: _dispatch_signal())

        def _handle_os_signal(_signum, _frame):
            pass  # the wake-up is done by set_wakeup_fd; the work is in _dispatch_signal

        signal.set_wakeup_fd(_sig_w.fileno())
        signal.signal(signal.SIGTERM, _handle_os_signal)
        signal.signal(signal.SIGHUP, _handle_os_signal)
        # ----------------------------------------------------------------------

        if not start_hidden:
            window.show()
            window.raise_()
            window.activateWindow()

        Output.print("Startup complete — idle in tray, event loop running",
                     level="info")
        app.exec()

        # #################### END OF MAIN LOGIC ######################

    except Exception as e:  # if an error is raised in the main logic
        Output.print(f"{get_timestamp_with_date()} - EXCEPTION RAISED IN MAIN : {e}\n {traceback.format_exc()}",
                     level="error")
    finally:
        Output.print(f"\n")
        Output.print(f"*******  END OF PROGRAM !   ******\n\n")
        if inhibitor is not None:
            inhibitor.release()  # last: logind has waited for us up to here

# ###########################  END OF MAIN  #############################


if __name__ == '__main__':

    main()
