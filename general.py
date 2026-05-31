#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" general helper functions"""

# general import
import re
import datetime
import configparser
import subprocess

# local import
from custom_path import Path
from output import Output

# A whitespace-delimited web link: 'http(s)://...' or 'www....'. Shared with the
# GUI so link detection and capitalization stay consistent.
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


def ping(host: str) -> bool:
    """ Return True if the host is up and false otherwise"""
    command = ["ping", "-c", "2", host]
    return subprocess.run(args=command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def get_hour() -> int:
    """Return hour of the day as 23h55 = 23"""
    hour = datetime.datetime.strftime(datetime.datetime.now(), "%H")
    if len(hour) == 2 and hour[0] == '0':
        hour = hour[1]
    return int(f'{hour}')


def get_date() -> str:
    """ return date as '20211125'
    """
    return f'{datetime.datetime.strftime(datetime.datetime.now(), "%Y%m%d")}'


def get_timestamp() -> str:
    """ return timestamp as '23h12 15s - '
    """
    return f'{datetime.datetime.strftime(datetime.datetime.now(), "%Hh%M %Ss - ")}'


def get_timestamp_with_date() -> str:
    """ return timestamp as '20211125 - 23h12 15s'
        """
    return f'{datetime.datetime.strftime(datetime.datetime.now(), "%Y%m%d - %Hh%M %Ss")}'


# ##################################################################################################
# ####################### config.INI read and write  ###############################################

def read_config_file_menu(menu: str = "CONFIG") -> dict:
    config = configparser.ConfigParser()
    with open(Path.config_file_path, "r", encoding="utf8") as f:
        config.read_file(f)
        if menu in config:
            return dict(config[menu].items())
        else:
            Output.print(f"Menu '{menu}' not found in config file", level="error")
            raise ValueError(f"{menu} is not a valid menu option in config file")


def read_config_file(menu: str = "CONFIG", param: str = "") -> str:
    """ read the config file and return the value
    """
    config = read_config_file_menu(menu)
    if param in config:
        return config[param]
    else:
        Output.print(f"Parameter '{param}' not found in menu '{menu}' of config file",
                     level="error")
        raise ValueError(f"{param} is not a valid param in config file")


def write_config_file(param: str, value: str, menu: str = "CONFIG"):
    """ read the config file, modify the parma with the new value and save it"""
    config = configparser.ConfigParser()
    with open(Path.config_file_path, "r", encoding="utf8") as f:
        config.read_file(f)
    config[menu][param] = value
    with open(Path.config_file_path, "w", encoding="utf8") as f:
        config.write(f)


def write_config_file_menu(data: dict, menu: str = "CONFIG") -> None:
    config = configparser.ConfigParser()
    with open(Path.config_file_path, "r", encoding="utf8") as f:
        config.read_file(f)
        config[menu] = data
    with open(Path.config_file_path, "w", encoding="utf8") as f:
        config.write(f)


# ####################### END OFconfig.INI read and write  #########################################
# ##################################################################################################


# ##################################################################################################
# ####################### text / bullet helpers  ###################################################
#
# Quadrant items are rendered in the editor as "• Text" but stored in param.json
# as raw strings (no bullet, no leading whitespace). These helpers translate
# between the two forms and let the editor diff successive states to detect
# edits vs. erasures. A "• " alone (or whitespace around it) counts as empty —
# the user has not yet typed an item on that line.

def is_empty(line: str) -> bool:
    """True if the line has no content besides whitespace and bullet chars."""
    return not line.strip().replace("•", "").strip()


def clean_line(line: str) -> str:
    """Normalize one line to the display form '• Capitalized text', or '' if empty."""
    s = line.lstrip()
    if s.startswith("•"):
        s = s[1:].lstrip()
    if not s:
        return ""
    # Don't capitalize the first character when the line starts with a web link,
    # so URLs are left intact (e.g. 'https://...' must not become 'Https://...').
    if URL_RE.match(s):
        return "• " + s
    return "• " + s[0].upper() + s[1:]


def clean_text(text: str) -> str:
    """Apply clean_line to every non-empty line; join with '\\n' and a trailing newline."""
    lines = [clean_line(line) for line in text.splitlines() if not is_empty(line)]
    return ("\n".join(lines) + "\n") if lines else ""


def snapshot(text: str) -> dict[int, str]:
    """Map line-index -> line for non-empty lines, used to diff edits against the previous state."""
    return {i: l for i, l in enumerate(text.splitlines()) if not is_empty(l)}


def get_raw(text: str) -> list[str]:
    """Return items stripped of the '• ' prefix (raw storage format for param.json)."""
    result = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("•"):
            s = s[1:].lstrip()
        if s:
            result.append(s)
    return result


# ####################### END OF text / bullet helpers  ############################################
# ##################################################################################################


if __name__ == '__main__':
    pass
