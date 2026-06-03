#!/usr/bin/python3
# -*- coding: Utf-8 -*
""" Self-contained auto-update module.

Update detection compares the version number of EiTodo's ``version.py`` on
GitHub (branch ``master``) with the one installed locally; the update itself
downloads the source archive of that branch and deploys it over the install
folder, replacing the tracked files in place. All of it is kept independent
from the GUI (no Qt dependency) so it can be tested and reused on its own.

The local version number is provided by :func:`version.version_nb`; the remote
one is obtained by fetching the raw ``version.py`` file and pulling its version
number out with :func:`extract_version_nb`.
"""

# general import
import os
import re
import shutil
import tarfile
import tempfile
import urllib.request

# local import
from output import Output

# Raw GitHub URLs of single project files on the tracked branch. Fetching these
# tiny files is far cheaper than the GitHub API (rate-limited and heavier) or
# cloning/downloading the repo. requirements.txt is fetched to decide, before
# any in-place update, whether the dependency set changed (see perform_update).
_REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/vtflosa/EiTodo/master/version.py")
_REMOTE_REQUIREMENTS_URL = (
    "https://raw.githubusercontent.com/vtflosa/EiTodo/master/requirements.txt")
# Tarball of the whole tracked tree (same URL the installer uses). Used by
# perform_update to deploy a new release. To reuse this module on another
# project, only these three URLs (and the install_dir the caller passes) change.
_ARCHIVE_URL = (
    "https://github.com/vtflosa/EiTodo/archive/refs/heads/master.tar.gz")
# These files are tiny; cap the read so a bogus or oversized response can never
# be pulled wholesale into memory.
_MAX_RESPONSE_BYTES = 64 * 1024
# The source tarball is small (sources + translations + a PNG); cap it generously
# so a malicious/runaway response can't fill the disk.
_MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
# Short timeout so a dead or slow network fails fast instead of hanging the
# worker thread that runs this call.
_DEFAULT_TIMEOUT_S = 5.0
# Default seconds to wait after startup before the automatic update check, so
# the machine can finish booting first. Shared by main (config default) and the
# GUI (fallback when the config value is missing/corrupt).
STARTUP_CHECK_DEFAULT_DELAY_S = 600


def _fetch_text(url: str, timeout: float, max_bytes: int) -> str | None:
    """GET a single small text file over HTTPS and return its decoded body, or
    ``None`` on any failure (no network, timeout, HTTP error, non-UTF-8 body).
    Never raises; the read is capped at ``max_bytes``.

    The call is *blocking* and deliberately free of any Qt dependency, so the
    module stays standalone and testable. Run it off the GUI thread (a worker
    thread that marshals the result back via a ``pyqtSignal``, like the watchdog
    path in ``todolist.py``) to keep the UI responsive.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "EiTodo-update-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes)
        return raw.decode("utf-8")
    except (OSError, ValueError) as exc:
        # OSError covers URLError/HTTPError (both subclass it) and socket
        # timeouts; ValueError covers a malformed URL or a non-UTF-8 body.
        Output.print(f"Update: failed to fetch {url} ({exc})", level="warning")
        return None


def fetch_remote_version_py(timeout: float = _DEFAULT_TIMEOUT_S) -> str | None:
    """Fetch the raw ``version.py`` from the GitHub repo (tracked branch) and
    return its text, or ``None`` on any failure. One cheap GET of a single
    ~2 KB raw file — no clone, no API call, no auth. Callers treat ``None`` as
    "could not check", so a failed fetch never triggers a spurious update."""
    return _fetch_text(_REMOTE_VERSION_URL, timeout, _MAX_RESPONSE_BYTES)


def fetch_remote_requirements(timeout: float = _DEFAULT_TIMEOUT_S) -> str | None:
    """Fetch the raw ``requirements.txt`` from the tracked branch (same cheap
    raw-file GET as the version check), or ``None`` on any failure. The caller
    compares it to the local file via :func:`requirements_changed` to decide
    whether an in-place update is safe; ``None`` is treated as "cannot verify"
    and falls back to a manual update."""
    return _fetch_text(_REMOTE_REQUIREMENTS_URL, timeout, _MAX_RESPONSE_BYTES)


def update_to_latest(install_dir: str, timeout: float = _DEFAULT_TIMEOUT_S) -> bool:
    """Deploy EiTodo's own latest source archive over ``install_dir`` — a thin,
    project-specific shim over the generic :func:`perform_update` that supplies
    this project's :data:`_ARCHIVE_URL`. The GUI calls this so it never has to
    know the URL; the underlying :func:`perform_update` stays reusable with any
    archive URL."""
    return perform_update(_ARCHIVE_URL, install_dir, timeout)


# Matches a version line such as "V 1.7 : ..." and captures the dotted number.
# Strict shape: a 'V'/'v', optional spaces, a major.minor[.patch] number,
# optional spaces, then a ':'. Requiring at least a major.minor and the
# trailing colon keeps version-like tokens in free-text descriptions (e.g.
# "v2", "version 2", "branch v1.2-fixes") from being matched.
_VERSION_TOKEN_RE = re.compile(r"[Vv]\s*(\d+\.\d+(?:\.\d+)*)\s*:")


def _parse_version(version_nb: str) -> tuple[int, ...] | None:
    """Turn a dotted version number like ``'1.7'`` or ``'4.6.8'`` into a tuple
    of ints for ordered comparison, e.g. ``(1, 7)`` or ``(4, 6, 8)``.

    Comparing tuples of ints (not strings) makes ``1.10`` correctly newer than
    ``1.9``. Return ``None`` when the string is missing or is not made of
    integer parts, so callers can treat an unparseable version as "cannot
    decide" rather than risk acting on garbage.
    """
    if not version_nb:
        return None
    try:
        return tuple(int(part) for part in version_nb.strip().split("."))
    except ValueError:
        return None


def extract_version_nb(version_py_text: str) -> str:
    """Return the latest version number found in the text of a ``version.py``
    file, e.g. ``'1.7'``. Returns ``''`` when none is found.

    The file lists every release as ``"V X[.Y[.Z]] : description"`` lines, so
    the last matching token is the current version. This works both on the raw
    file source fetched from GitHub and on the string returned by
    :func:`version.version`.
    """
    matches = _VERSION_TOKEN_RE.findall(version_py_text)
    return matches[-1] if matches else ""


def is_update_available(local_version: str, remote_version: str) -> bool:
    """Return ``True`` if an update should be performed, i.e. ``remote_version``
    is strictly newer than ``local_version``; ``False`` otherwise.

    Both arguments are dotted version numbers as returned by
    :func:`version.version_nb`, e.g. ``'1.7'`` compared with ``'1.8'``. If
    either version cannot be parsed (malformed, empty, or an unreachable remote
    that yielded no number), this returns ``False`` so a bad read never
    triggers a spurious update.
    """
    local = _parse_version(local_version)
    remote = _parse_version(remote_version)
    if local is None or remote is None:
        return False
    return remote > local


def should_offer_update(installed_version: str, ignored_version: str,
                        remote_version: str) -> bool:
    """Return ``True`` if the user should be offered an update to
    ``remote_version``, ``False`` otherwise.

    Two gates must pass:

    - ``remote_version`` is strictly newer than ``installed_version`` — there is
      genuinely a newer release than what is installed (dotted numbers as
      returned by :func:`version.version_nb`); and
    - the release is not the one the user chose to ignore. ``ignored_version``
      is either ``""`` (nothing ignored) or a dotted number ``X.Y.Z``: if the
      remote equals that ignored number it is suppressed, but a remote strictly
      newer than it is offered again — an old "ignore" does not silence later
      releases.

    Pure decision, no I/O: the caller reads the three values (installed version,
    the ``ignored_version`` config entry, and the remote number from
    :func:`fetch_remote_version_py` + :func:`extract_version_nb`) and, on
    "ignore", writes ``remote_version`` into ``ignored_version`` (and clears it
    back to ``""`` once an update completes). An unreachable remote yields ``""``
    → ``False`` (no spurious prompt). An empty **or unparseable**
    ``ignored_version`` counts as "nothing ignored", so a corrupted marker fails
    open (the update is still offered) rather than silently blocking updates.
    """
    if not is_update_available(installed_version, remote_version):
        return False
    if _parse_version(ignored_version) is None:
        return True
    return is_update_available(ignored_version, remote_version)


def _normalize_requirements(text: str) -> set[str]:
    """The set of meaningful requirement lines: each trimmed, with blank lines
    and ``#`` comments dropped. Comparing sets makes the check order- and
    whitespace-insensitive."""
    return {line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")}


def requirements_changed(local_text: str, remote_text: str | None) -> bool:
    """Return ``True`` if the dependency set differs between the local and remote
    ``requirements.txt`` — or if ``remote_text`` is missing.

    A changed (or unverifiable) requirements file means an in-place file swap
    plus restart could boot into missing dependencies, so the caller must fall
    back to a manual update instead. ``None``/empty remote therefore counts as
    "changed" (fail-safe), and the comparison ignores ordering, blank lines and
    comments (see :func:`_normalize_requirements`)."""
    if not remote_text:
        return True
    return _normalize_requirements(local_text) != _normalize_requirements(remote_text)


def _copy_tree_over(src_root: str, dest_root: str):
    """Copy every file under ``src_root`` into ``dest_root`` keeping the same
    relative layout: missing subdirectories are created, and each file is
    written to a temporary name in its destination directory then moved into
    place with :func:`os.replace` (atomic per file, even over a file the running
    process is currently executing — fine on Linux). Files present in
    ``dest_root`` but absent from ``src_root`` are left untouched (no deletion).
    """
    for dirpath, _dirnames, filenames in os.walk(src_root):
        rel = os.path.relpath(dirpath, src_root)
        dest_dir = dest_root if rel == "." else os.path.join(dest_root, rel)
        os.makedirs(dest_dir, exist_ok=True)
        for name in filenames:
            dest = os.path.join(dest_dir, name)
            tmp = dest + ".new"
            shutil.copy2(os.path.join(dirpath, name), tmp)
            os.replace(tmp, dest)


def perform_update(archive_url: str, install_dir: str,
                   timeout: float = _DEFAULT_TIMEOUT_S) -> bool:
    """Download the project's source archive and deploy it over ``install_dir``,
    overwriting the tracked files in place. Return ``True`` only if download
    **and** extraction **and** copy all succeeded; ``False`` (with nothing
    overwritten) on any earlier failure.

    Safe by construction:

    - The GitHub tarball holds only tracked files, so gitignored runtime data
      (``config.INI``, ``param.json``, ``logs/``, ``save/``, the venv) is absent
      from it and never touched.
    - Files are copied over ``install_dir`` only after the archive is fully
      downloaded and extracted to a temp dir, so a partial/failed download can
      never corrupt the install.
    - ``extractall(filter="data")`` rejects unsafe members (absolute paths,
      ``..`` traversal, special files).
    - The downloaded archive and the extraction dir are always cleaned up.

    No rollback is kept: on a broken update the user can re-run the installer,
    and data/backups are intact regardless. No Qt dependency — the caller (GUI)
    restarts the app (e.g. ``os.execv``) once this returns ``True``.
    """
    tmp_archive = None
    tmp_extract = None
    try:
        # 1. Download the tarball to a temp file, capped to avoid filling disk.
        request = urllib.request.Request(
            archive_url, headers={"User-Agent": "EiTodo-update"})
        fd, tmp_archive = tempfile.mkstemp(suffix=".tar.gz",
                                           prefix="eitodo_update_")
        read = 0
        with os.fdopen(fd, "wb") as out, \
                urllib.request.urlopen(request, timeout=timeout) as response:
            while chunk := response.read(64 * 1024):
                read += len(chunk)
                if read > _MAX_ARCHIVE_BYTES:
                    raise ValueError("archive exceeds size cap")
                out.write(chunk)

        # 2. Extract into a temp dir; validate before anything is overwritten.
        tmp_extract = tempfile.mkdtemp(prefix="eitodo_update_")
        with tarfile.open(tmp_archive, "r:gz") as tar:
            tar.extractall(path=tmp_extract, filter="data")

        # 3. The tarball unpacks to a single "<repo>-<branch>/" top folder; copy
        #    its content over the install dir.
        tops = [e for e in os.listdir(tmp_extract)
                if os.path.isdir(os.path.join(tmp_extract, e))]
        if len(tops) != 1:
            raise ValueError(f"unexpected archive layout: {tops}")
        _copy_tree_over(os.path.join(tmp_extract, tops[0]), install_dir)
        Output.print(f"Update: deployed new files into {install_dir}",
                     level="info")
        return True
    except (OSError, ValueError, tarfile.TarError) as exc:
        Output.print(f"Update: failed to download/deploy archive ({exc})",
                     level="error")
        return False
    finally:
        # 4. Always clean up downloaded/extracted temporaries.
        if tmp_archive and os.path.exists(tmp_archive):
            try:
                os.remove(tmp_archive)
            except OSError:
                pass
        if tmp_extract and os.path.isdir(tmp_extract):
            shutil.rmtree(tmp_extract, ignore_errors=True)
