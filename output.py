#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" Handle the print wherever we want it

    Prevent from crash when print should be updated from different threads
"""

import queue
import logging


class Output:
    """ manage printing info wherever we want it :
            - print the text in standard output stdout
            - log the text in logging if a logger has been defined
            - add the text in the 'text_queue' as Queue object, so it can be retrieved from wherever we want it
                even from other threads.
                    usage of the queue :
                        ###  CODE  ###
                        while not Output.text_queue.empty():
                            new_text = Output.text_queue.get()
                            do_something_with(new_text)
                        ##############
    """
    text_queue = queue.Queue()

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

        # format the text to add it to the queue to be picked up in other part or thread of the program
        new_text = text + end
        Output.text_queue.put(new_text)
