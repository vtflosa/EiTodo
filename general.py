#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" general helper functions"""

# general import
import os
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


def write_config_file_values(values: dict, menu: str = "CONFIG"):
    """Set several params in `menu` with a single read + write of config.INI.
    Use this instead of calling write_config_file once per key (which re-reads
    and rewrites the whole file each time). Only the given keys are updated;
    the rest of the section is left untouched (unlike write_config_file_menu,
    which replaces the whole section)."""
    config = configparser.ConfigParser()
    with open(Path.config_file_path, "r", encoding="utf8") as f:
        config.read_file(f)
    for param, value in values.items():
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


def config_is_usable() -> bool:
    """True if config.INI exists, parses, and holds the required CONFIG and PATH
    sections. False otherwise — missing file, empty, corrupt, or only partly
    written. Lets the startup path recreate a broken config instead of crashing
    when it is later read."""
    config = configparser.ConfigParser()
    try:
        with open(Path.config_file_path, "r", encoding="utf8") as f:
            config.read_file(f)
    except (OSError, configparser.Error):
        return False
    return "CONFIG" in config and "PATH" in config


def reset_config(sections: dict[str, dict]) -> None:
    """(Re)create config.INI from scratch with exactly `sections`, WITHOUT
    reading any existing (possibly corrupt) file. Used to reseed defaults when
    config_is_usable() is False."""
    config = configparser.ConfigParser()
    for menu, data in sections.items():
        config[menu] = data
    with open(Path.config_file_path, "w", encoding="utf8") as f:
        config.write(f)


# Tolerant line match for the [PATH] keys, used to salvage them from a config.INI
# that configparser rejects (the data-file location lives only in config.INI).
_PATH_SALVAGE_RE = re.compile(
    r"^\s*(json_file_path|log_folder_path|save_folder_path)\s*=\s*(.+?)\s*$")


def salvage_path_values() -> dict:
    """Best-effort recovery of the [PATH] values from a config.INI that
    config_is_usable() rejects (corrupt / partly written): read it line by line
    so the keys are found even when the [PATH] header is broken. Returns {} if
    nothing is found. Lets startup keep pointing at a relocated data file instead
    of losing it when the config is recreated."""
    values: dict[str, str] = {}
    try:
        with open(Path.config_file_path, "r", encoding="utf8") as f:
            for line in f:
                match = _PATH_SALVAGE_RE.match(line)
                if match:
                    values[match.group(1)] = match.group(2)
    except OSError:
        return {}
    return values


def backup_corrupt_config() -> None:
    """Rename an unusable config.INI aside (config.INI.bak-<timestamp>) before it
    is recreated, so its content (other settings) stays available for manual
    recovery. Best-effort: ignores errors and does nothing if the file is absent."""
    try:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.rename(Path.config_file_path, f"{Path.config_file_path}.bak-{stamp}")
    except OSError:
        pass


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
    """Normalize one line to the display form '• Capitalized text', or '' if empty.
    Collapses repeated leading bullets, so '• • text' becomes '• text'."""
    s = line.lstrip()
    while s.startswith("•"):
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
