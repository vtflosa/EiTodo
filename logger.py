#!/usr/bin/python3
# coding: utf8
import logging
import os.path
import datetime

# local import
from output import Output


class Logger:
    def __init__(self, log_folder_path="logs", nb_of_logs_to_keep: int = 20):
        self.log_folder_path = log_folder_path
        self.log_to_keep = nb_of_logs_to_keep
        # start logging
        self.create_log()
        # delete old logs if needed
        self.delete_old_logs()

    def create_log(self):
        """ Create logging file and start logging"""
        # check if log folder exist
        if not os.path.isdir(self.log_folder_path):
            Logger.create_log_folder(self.log_folder_path)

        # start logging
        log_filename = os.path.join(self.log_folder_path, "{}.log".format(datetime.datetime.strftime
                                                                          (datetime.datetime.now(),
                                                                           "%Y-%m-%d-%H%M%S")))
        logging.basicConfig(format='%(levelname)s\t%(asctime)s |\t %(message)s',
                            datefmt='%d/%m/%Y %H:%M:%S',
                            filename=log_filename,
                            filemode='w',
                            level=20)

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
    