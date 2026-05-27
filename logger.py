#!/usr/bin/python3
# -*- coding: Utf-8 -*
import logging
import os.path
import datetime

# local import
from output import Output


class Logger:
    # Path of the currently active log file. Exposed as a class attribute so
    # other parts of the app (e.g. the language-change restart in guiqt) can
    # find it without holding a reference to the Logger instance.
    current_log_path: str = ""

    def __init__(self, log_folder_path="logs", nb_of_logs_to_keep: int = 20,
                 continue_from: str | None = None):
        self.log_folder_path = log_folder_path
        self.log_to_keep = nb_of_logs_to_keep
        self.continued = False  # set in create_log when an existing file is reused
        # start logging
        self.create_log(continue_from)
        # delete old logs if needed
        self.delete_old_logs()

    def create_log(self, continue_from: str | None = None):
        """Create the logging file and start logging.

        When continue_from points at an existing log file, append to it
        instead of opening a fresh one — used by the language-change restart
        so the new process's lines land in the same file as the old one's.
        """
        # check if log folder exist
        if not os.path.isdir(self.log_folder_path):
            Logger.create_log_folder(self.log_folder_path)

        if continue_from and os.path.isfile(continue_from):
            log_filename = continue_from
            self.continued = True
            mode = 'a'
        else:
            log_filename = os.path.join(self.log_folder_path, "{}.log".format(
                datetime.datetime.strftime(datetime.datetime.now(),
                                           "%Y-%m-%d-%H%M%S")))
            mode = 'w'

        logging.basicConfig(format='%(levelname)s\t%(asctime)s |\t %(message)s',
                            datefmt='%d/%m/%Y %H:%M:%S',
                            filename=log_filename,
                            filemode=mode,
                            level=20)
        Logger.current_log_path = log_filename

        if self.continued:
            Output.print("═══════════ Resumed after restart ═══════════",
                         level="info")

        # logging.getLogger("requests").setLevel(logging.WARNING)
        # logging.getLogger("urllib3").setLevel(logging.WARNING)

    def delete_old_logs(self):
        """return list of erased files"""
        file_list = []
        if os.path.isdir(self.log_folder_path):
            file_list = os.listdir(self.log_folder_path)
        else:
            return file_list

        file_list.sort()  # to sort logs by date
        # keep only X logs
        erased_files = []
        if len(file_list) > self.log_to_keep:
            erase_file_list = file_list[: len(file_list) - self.log_to_keep]
            for file in erase_file_list:
                try:
                    file_path = os.path.join(self.log_folder_path, file)
                    os.unlink(file_path)
                    Output.print(f"erase old log at {file_path}")
                    erased_files.append(file)
                except PermissionError as e:
                    Output.print("Permission denied to delete file : {}".format(e), level="error")
        return erased_files

    @staticmethod
    def create_log_folder(folder_path):
        try:
            os.mkdir(folder_path)
        except FileExistsError:
            print(f"Directory '{folder_path}' already exists.")
        except PermissionError:
            print(f"Permission denied: Unable to create '{folder_path}'.")
        except Exception as e:
            print(f"An error occurred creating folder at {folder_path}: {e}")
    