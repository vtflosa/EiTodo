#!/usr/bin/python3
# -*- coding: Utf-8 -*

""" Load all path that we need"""

# general import
import os


class Path:
    @staticmethod
    def check_folder(folder):
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Folder does not exist here : {folder}")

    @staticmethod
    def check_file(file):
        if not os.path.isfile(file):
            raise FileNotFoundError(f"File not found here : {file}")

    @staticmethod
    def resolve(path: str) -> str:
        """Resolve a config path to an absolute one: relative paths are joined
        with dir_path (the install folder) so the app does not depend on the
        process CWD; absolute paths are returned unchanged. Inverse of
        to_portable()."""
        return path if os.path.isabs(path) else os.path.join(Path.dir_path, path)

    @staticmethod
    def to_portable(path: str) -> str:
        """Return the value to store for a path in config.INI: relative to
        dir_path when the path lives inside the install folder, else absolute.
        Storing it relative keeps config.INI portable when the install folder is
        shared/synced across machines with different absolute home paths — the
        relative value resolves correctly on each one via resolve(). A path that
        is already relative is returned unchanged. Inverse of resolve()."""
        if not os.path.isabs(path):
            return path
        rel = os.path.relpath(path, Path.dir_path)
        if rel == os.pardir or rel.startswith(os.pardir + os.sep):
            return path  # outside the install folder → keep absolute
        return rel

    # path to script directory
    dir_path = os.path.dirname(os.path.abspath(__file__))

    # default user path
    user_path = os.path.expanduser("~")

    icon_path = os.path.join(dir_path, "EiTodo.png")
    check_file(icon_path)

    # Tracked dependency manifest, read by the in-app updater to detect a
    # dependency change before a file-swap update. Not check_file'd: it is only
    # consulted during an update, so its absence must degrade to a manual update,
    # not crash startup.
    requirements_path = os.path.join(dir_path, "requirements.txt")

    # ##########   Paths to be set and verified later  #################""
    # config_file
    config_file_path = os.path.join(dir_path, "config.INI")

    # json_file
    json_file_path: str = ""

    # path to log folder to save logs
    log_folder: str = ""

    save_folder: str = ""

    translations_folder = os.path.join(dir_path, "translations")
    check_folder(translations_folder)

    docs_folder = os.path.join(dir_path, "docs")
    check_folder(docs_folder)
