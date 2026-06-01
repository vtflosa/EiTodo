#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" Handle the print wherever we want it

    Prevent from crash when print should be updated from different threads
"""

import logging


class Output:
    """ manage printing info wherever we want it :
            - print the text in standard output stdout
            - log the text in logging if a logger has been defined
    """

    @staticmethod
    def print(*args, level="info", end="\n"):
        text = ""
        for arg in args:
            text += str(arg)

        # Normal print of the text in the console
        print(text, end=end)

        logger = logging.getLogger()
        # Print the text in the logging file if a logger has been instantiated

        if logger.hasHandlers():  # a logger has been instantiated
            if level.upper() == "INFO":
                logging.info(text)
            elif level.upper() == "WARNING":
                logging.warning(text)
            elif level.upper() == "ERROR":
                logging.error(text)
            elif level.upper() == "NOLOG":
                pass
            else:
                logging.debug(text)
