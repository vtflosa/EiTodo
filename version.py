#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" Versioning of the program"""


def version_nb() -> str:
    """Return just the version number of the latest entry, e.g. '1.2' or
    '4.6.8'. Parses the line returned by version(), which is shaped
    'V X[.Y[.Z]] : description'."""
    parts = version().split(maxsplit=2)
    return parts[1] if len(parts) >= 2 else ""


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
              "V 0.8 : translation multilingue\n"
              "V 0.9 : in-app help dialog + menu to set backup retention limit\n"
              "V 1.0 : public release — installer hardening, autostart prompt, README\n"
              "V 1.1 : German and Spanish UI + help translations\n"
              "V 1.2 : docs corrected — cloud sync only, direct network shares not recommended\n"
              "V 1.3 : version number shown in tray menu header + update instructions in README\n"
              "V 1.4 : right-click menus on quadrants\n"
              "V 1.5 : open-folder & interface-responsiveness menus + Ctrl+click to open links\n"
              "V 1.6 : robustness fixes — sync right-click data loss, done-panel HTML escaping & display cap,"
              " backup name collisions, CWD-independent portable paths\n"
              "V 1.7 : efficiency/leak fixes — drop unused log queue, free modal dialogs,"
              " batch geometry config write, watchdog basename pre-filter, skip idle hourly backup\n"
              "V 1.8 : one-line curl install command + autostart selected by default\n"
              "V 1.9 : atomic task moves — single write for move/mark-done/restore (no item loss)\n"
              "V 2.0 : in-app auto-update — GitHub version check, ignore/later, delayed startup"
              " check, in-place file update + restart; tolerant config startup (recreate if corrupt)\n"
              "V 2.1 : data-loss safeguards — salvage data path on config recovery, retry failed writes, "
              "back up a file before overwrite"
              )
    return v_text.split("\n")[-1]
