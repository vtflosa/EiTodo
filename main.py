#!/usr/bin/python3
# coding: utf8
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
from PyQt6.QtCore import QTimer, QSocketNotifier

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


#   todo create a linux installer and publish it on github + on install, ask whether to add it to automatic startup

# todo vérifier comportement à l'extinction de l'ordi


# todo écrire un fichier d'aide

# todo faire la traduction en anglais

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
}

_DEFAULT_PATH = {
    "log_folder_path": "logs",
    "save_folder_path": "save",
    "json_file_path": "param.json"}

_DEFAULT_PARAM = {
    "version": 0,
    "updated_at": 0.0,
    "last_writer": "",
    "U&I": ["Ecrire les tâches à faire"], "U&I_done": ["Ici sont les tâches réalisées"],
    "NU&I": [], "NU&I_done": [],
    "U&Un": [], "U&Un_done": [],
    "NU&Un": [], "NU&Un_done": [],
}


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
            json.dump(_DEFAULT_PARAM, f, indent=4)

    write_config_file_menu(menu="CONFIG", data=_DEFAULT_CONFIG)
    write_config_file_menu(menu="PATH", data=_DEFAULT_PATH)

    # reset first_launch flag
    write_config_file(param="first_launch", value="False", menu="CONFIG")
    # The first-launch event is logged by the caller once the logger is up
    # (the logger needs the paths this function creates), so it lands in the file.
    return True


def main():

    # first_launch() creates the config file and working folders; only then can
    # set_and_check_paths() resolve Path.log_folder for the logger below.
    first_launch_start = first_launch()
    json_exists = set_and_check_paths()

    # Start logging as early as the paths allow, so every event below (including
    # the first-launch notice) is captured in the log file.
    log = Log(Path.log_folder, 20)
    Output.print(version())
    if first_launch_start:
        Output.print("First launch: working folders and default data file created",
                     level="info")

    # delete excess timestamped backups in the save folder
    clean_old_backups()

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
        todolist = ToDoList(Path.json_file_path, default_data=_DEFAULT_PARAM)
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

        app = QApplication([])
        app.setQuitOnLastWindowClosed(False)
        window = gui(todolist=todolist, debounce_ms=debounce_ms,
                     width=win_width, height=win_height,
                     x=win_x, y=win_y, screen_name=win_screen,
                     prompt_data_location=prompt_data_location,
                     default_json_name=_DEFAULT_PATH["json_file_path"],
                     font=font, font_size=font_size)

        # Handle OS-level termination (system shutdown, kill, session end).
        # Python signal handlers only fire between bytecodes, not while Qt owns
        # the event loop — the QTimer below wakes Python every 500 ms so the
        # handlers can run.
        def _handle_os_signal(signum, _frame):
            sig_name = signal.Signals(signum).name
            Output.print(f"OS signal received ({sig_name}) — saving and quitting",
                         level="info")
            window._quit()

        signal.signal(signal.SIGTERM, _handle_os_signal)
        signal.signal(signal.SIGHUP, _handle_os_signal)

        _sig_poll = QTimer()
        _sig_poll.setInterval(500)
        _sig_poll.start()
        _sig_poll.timeout.connect(lambda: None)

        if not start_hidden:
            window.show()
            window.raise_()
            window.activateWindow()
        app.exec()

        # #################### END OF MAIN LOGIC ######################

    except Exception as e:  # if an error is raised in the main logic
        Output.print(f"{get_timestamp_with_date()} - EXCEPTION RAISED IN MAIN : {e}\n {traceback.format_exc()}",
                     level="error")
    finally:
        Output.print(f"\n")
        Output.print(f"*******  END OF PROGRAM !   ******\n\n")

# ###########################  END OF MAIN  #############################


if __name__ == '__main__':

    main()
