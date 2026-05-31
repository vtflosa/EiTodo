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

    # path to script directory
    dir_path = os.path.dirname(os.path.abspath(__file__))

    # default user path
    user_path = os.path.expanduser("~")

    icon_path = os.path.join(dir_path, "EiTodo.png")
    check_file(icon_path)

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
