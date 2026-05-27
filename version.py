#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" Versioning of the program"""


def version():
    """this function return only the last line. Add \n to the previous line"""
    v_text = ("V 0.0 : building structure of the project\n"
              "V 0.1 : first draft\n"
              "V 0.2 : version save and version location change\n"
              "V 0.3 : clean startup when file missing\n"
              "V 0.4 : cleanup logs and comments, translate in english\n"
              "V 0.5 : cleanup imports (drop unused + wildcard imports), no circular imports\n"
              "V 0.6 : added font selection\n"
              "V 0.7 : Save param en reboot or sigterm\n"
              "V 0.8 : translation multilingue"
              )
    return v_text.split("\n")[-1]
