#!/usr/bin/python3
# coding: utf8

""" todolist class to manage the eisenhower todolist

    The matrix is as follows:
        - Urgent & Important     → do immediately
        - Not Urgent & Important → schedule on calendar
        - Urgent & Unimportant   → delegate
        - Not Urgent & Unimportant → delete or do at leisure
        ["U&I", "U&I_done", "NU&I", "NU&I_done", "U&Un", "U&Un_done", "NU&Un", "NU&Un_done"]

    Multi-instance synchronisation (Linux only):
        - Exclusive file lock via fcntl.flock() serialises concurrent writes.
        - Atomic write: serialise to .tmp then os.replace() so readers never
          see a partially written file.
        - A monotonic 'version' counter lets every instance detect stale local
          state without comparing the full payload.
        - 'updated_at' (UTC timestamp) and 'last_writer' (UUID) are stored for
          diagnostics and to skip re-notifying on own writes.
        - Inside the lock, only the quadrants touched by the current operation
          are kept from memory; all other quadrants are refreshed from disk.
          This confines conflicts to the quadrant(s) actually being modified
          (last-writer-wins per quadrant), leaving unrelated quadrants intact.
        - watchdog (inotify) fires on_remote_change() in a background thread
          whenever a different instance modifies the file.

    Requirements:
        pip install watchdog
"""

import fcntl
import json
import os
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from output import Output


# ===========================================================================
#  Internal watchdog handler
# ===========================================================================

class _StateChangeHandler(FileSystemEventHandler):
    """Calls on_remote_change(state_dict) when the shared file is modified
    by a *different* instance. Own writes are filtered out via instance_id."""

    def __init__(self, state_path: Path, instance_id: str,
                 on_remote_change: Callable[[dict], None]):
        super().__init__()
        self._state_path = state_path.resolve()
        self._instance_id = instance_id
        self._on_remote_change = on_remote_change
        self._last_seen_at: float = 0.0

    def on_modified(self, event):
        if Path(event.src_path).resolve() == self._state_path:
            self._process()

    def on_created(self, event):
        # MegaSync (and similar clients) rename from outside the watched
        # directory; inotify sees no IN_MOVED_FROM, so watchdog reports a
        # FileCreatedEvent instead of FileMovedEvent.
        if Path(event.src_path).resolve() == self._state_path:
            self._process()

    def on_moved(self, event):
        if Path(event.dest_path).resolve() == self._state_path:
            self._process()

    def _process(self):
        try:
            data = json.loads(self._state_path.read_text(encoding="utf8"))
        except (OSError, json.JSONDecodeError):
            return  # file transiently incomplete — ignore

        # Use updated_at (float timestamp) instead of the integer version
        # counter: two devices writing simultaneously both increment their
        # independent counters to the same value, making version-based
        # deduplication silently drop one side's changes. Timestamps from
        # different wall-clocks are far less likely to collide.
        updated_at = data.get("updated_at", 0.0)
        if updated_at <= self._last_seen_at:
            return  # already processed this write

        self._last_seen_at = updated_at

        if data.get("last_writer") == self._instance_id:
            return  # our own write — skip

        self._on_remote_change(data)

    def update_local_state(self, updated_at: float):
        """Called after a successful local write to suppress self-notification."""
        self._last_seen_at = updated_at


# ===========================================================================
#  ToDoList
# ===========================================================================

class ToDoList:
    """Eisenhower matrix todolist with multi-instance shared-file sync (Linux).

    JSON file layout:
    {
        "version":     42,
        "updated_at":  1716000000.123,
        "last_writer": "<uuid>",
        "U&I":         [...],
        "U&I_done":    [...],
        ...
    }

    A companion <file>.lock serialises concurrent writes via fcntl.flock().

    Conflict policy: last-writer-wins per quadrant.
    Inside the lock, only the quadrant(s) modified by the current operation
    are taken from memory; every other quadrant is read from the freshest
    on-disk state, so concurrent edits to different quadrants never interfere.
    """

    POSSIBLE_LOC = [
        "U&I", "U&I_done",
        "NU&I", "NU&I_done",
        "U&Un", "U&Un_done",
        "NU&Un", "NU&Un_done",
    ]

    _META_KEYS = {"version", "updated_at", "last_writer"}

    def __init__(self, path_to_list: str,
                 on_remote_change: Optional[Callable[[dict], None]] = None,
                 default_data: Optional[dict] = None):
        """
        Args:
            path_to_list:       Path to the shared JSON file.
            on_remote_change:   Callback invoked (in a background thread) when
                                a remote instance modifies the file.
                                Receives the full raw state dict as argument.
            default_data:       Quadrant content used to seed a freshly created
                                file (e.g. example tasks). Sync-metadata keys are
                                ignored; quadrants absent from it start empty.
        """
        self.path = Path(path_to_list)
        self._lock_path = self.path.with_suffix(".lock")
        self._tmp_path = self.path.with_suffix(".tmp")

        self.instance_id: str = str(uuid.uuid4())

        # Seed content for a freshly created file (example tasks), metadata-free.
        self._default_data: dict[str, list] = {
            k: list(v) for k, v in (default_data or {}).items()
            if k not in self._META_KEYS
        }

        self.todolist_dict: dict[str, list] = {}
        self._version: int = 0
        self._updated_at: float = 0.0
        self._last_writer: str = ""

        self._handler: Optional[_StateChangeHandler] = None
        self._observer: Optional[Observer] = None
        self._on_remote_change_cb: Optional[Callable[[dict], None]] = None

        self.load_initial_state()

        if on_remote_change is not None:
            self._start_watcher(on_remote_change)

    def __str__(self) -> str:
        lines = [f"[version={self._version}  writer={self._last_writer[:8]}]"]
        for key, value in self.todolist_dict.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def __del__(self):
        self.stop_watcher()

    # ------------------------------------------------------------------
    # Public — initialisation
    # ------------------------------------------------------------------

    def load_initial_state(self):
        """Read file from disk; seed a default list if file is missing or empty."""
        data = self._read_raw()
        if data:
            self._apply_raw(data)
        else:
            self._create_default_list()

    def set_path(self, path_to_list: str):
        """Switch the backing JSON file at runtime.

        Stops watching the old file, re-points path/lock/tmp to path_to_list,
        reloads state from it, then resumes watching with the previously
        registered remote-change callback (if any). Version tracking is reset
        and re-seeded from the new file so stale-state detection stays correct.
        """
        callback = self._on_remote_change_cb
        self.stop_watcher()
        self.path = Path(path_to_list)
        self._lock_path = self.path.with_suffix(".lock")
        self._tmp_path = self.path.with_suffix(".tmp")
        self._version = 0
        self._updated_at = 0.0
        self._last_writer = ""
        self.load_initial_state()
        if callback is not None:
            self._start_watcher(callback)

    # ------------------------------------------------------------------
    # Public — task operations
    # ------------------------------------------------------------------

    def add_item(self, loc: str, item: str):
        """Add item to quadrant loc (no-op if already present, case-insensitive)."""
        self._validate_loc(loc)
        self._refresh()
        self._add(loc, item)
        self._write_locked(modified_locs={loc})

    def remove_item(self, loc: str, item: str):
        """Remove item from quadrant loc."""
        self._validate_loc(loc)
        self._refresh()
        self._remove(loc, item)
        self._write_locked(modified_locs={loc})

    def move_item(self, loc: str, new_loc: str, item: str):
        """Move item from quadrant loc to new_loc in a single atomic write."""
        self._validate_loc(loc)
        self._validate_loc(new_loc)
        self._refresh()
        self._remove(loc, item)
        self._add(new_loc, item)
        self._write_locked(modified_locs={loc, new_loc})

    # ------------------------------------------------------------------
    # Public — watcher lifecycle
    # ------------------------------------------------------------------

    def stop_watcher(self):
        """Stop the background watchdog thread cleanly."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def set_on_remote_change(self, callback: Callable[[dict], None]):
        """Wire up (or replace) the remote-change callback and (re)start the watcher."""
        self.stop_watcher()
        self._start_watcher(callback)

    def set_quadrant(self, loc: str, items: list[str]):
        """Replace an entire quadrant's content with a single atomic write."""
        self._validate_loc(loc)
        self._refresh()
        self.todolist_dict[loc] = items
        self._write_locked(modified_locs={loc})

    # ------------------------------------------------------------------
    # Private — in-memory operations (no I/O)
    # ------------------------------------------------------------------

    def _add(self, loc: str, item: str):
        """In-memory add (case-insensitive duplicate check), no disk I/O."""
        if item.upper() not in [i.upper() for i in self.todolist_dict[loc]]:
            self.todolist_dict[loc].insert(0, item)

    def _remove(self, loc: str, item: str):
        """In-memory remove, no disk I/O."""
        if item not in self.todolist_dict[loc]:
            raise ValueError(f"Unknown item: {item!r} not in {self.todolist_dict[loc]}")
        self.todolist_dict[loc].remove(item)

    # ------------------------------------------------------------------
    # Private — watcher
    # ------------------------------------------------------------------

    def _start_watcher(self, on_remote_change: Callable[[dict], None]):
        self._on_remote_change_cb = on_remote_change
        self._handler = _StateChangeHandler(
            state_path=self.path,
            instance_id=self.instance_id,
            on_remote_change=on_remote_change,
        )
        self._handler.update_local_state(self._updated_at)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.path.parent), recursive=False)
        self._observer.start()

    # ------------------------------------------------------------------
    # Private — file I/O
    # ------------------------------------------------------------------

    def _create_default_list(self):
        """Create the file seeded with default_data (example tasks); quadrants
        absent from default_data start empty."""
        self.todolist_dict = {
            loc: list(self._default_data.get(loc, [])) for loc in self.POSSIBLE_LOC
        }
        Output.print(f"Creating default data file: {self.path}", level="info")
        self._write_locked(modified_locs=set(self.POSSIBLE_LOC))

    def _read_raw(self) -> dict:
        """Parse the JSON file. Returns {} when the file does not exist yet
        (normal — the caller seeds defaults). A file that exists but cannot be
        read or parsed is corruption: it is logged as an error before returning
        {} so the failure is visible instead of silently swallowed."""
        try:
            return json.loads(self.path.read_text(encoding="utf8"))
        except FileNotFoundError:
            return {}  # not created yet — caller will seed the default list
        except (OSError, json.JSONDecodeError) as e:
            Output.print(f"Data file unreadable or corrupt ({self.path}): {e}",
                         level="error")
            return {}

    def _apply_raw(self, data: dict):
        """Populate local state from a raw JSON dict."""
        self._version = data.get("version", 0)
        self._updated_at = data.get("updated_at", 0.0)
        self._last_writer = data.get("last_writer", "")
        self.todolist_dict = {k: v for k, v in data.items() if k not in self._META_KEYS}

    def _refresh(self):
        """Reload from disk if the on-disk state is newer than local state.
        Called before every write to avoid silently overwriting remote changes.
        Compares updated_at (cross-device) and version (local multi-instance)
        so that both sync scenarios are covered."""
        data = self._read_raw()
        if (data.get("updated_at", 0.0) > self._updated_at
                or data.get("version", 0) > self._version):
            self._apply_raw(data)

    def _build_payload(self) -> dict:
        """Assemble the full JSON payload: metadata + task lists."""
        self._version += 1
        self._updated_at = time.time()
        self._last_writer = self.instance_id
        return {
            "version": self._version,
            "updated_at": self._updated_at,
            "last_writer": self._last_writer,
            **self.todolist_dict,
        }

    def _write_locked(self, modified_locs: set[str]):
        """Write current state atomically under an exclusive fcntl lock.

        Sequence:
          1. Acquire LOCK_EX on the .lock file (blocks until available).
          2. Re-read disk state inside the lock. For every quadrant NOT in
             modified_locs, adopt the on-disk version so that concurrent edits
             to different quadrants never overwrite each other.
             For quadrants in modified_locs, keep the in-memory version
             (last-writer-wins on the same quadrant is unavoidable).
          3. Write payload to .tmp, then os.replace() for an atomic swap.
          4. Release lock (via finally).
          5. Inform the local watchdog handler of the new version so it does
             not fire on_remote_change() for our own write.
        """
        self._lock_path.touch(exist_ok=True)

        with open(self._lock_path, "r", encoding="utf8") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                fresh = self._read_raw()
                if fresh.get("version", 0) > self._version:
                    Output.print(
                        f"Concurrent change detected (disk version "
                        f"{fresh['version']} > {self._version}) — merging quadrants "
                        f"outside {sorted(modified_locs)}", level="warning")
                    self._version = fresh["version"]
                    # Merge: keep our in-memory data only for the quadrants we
                    # just modified; adopt the fresher on-disk data for all others.
                    for loc in self.POSSIBLE_LOC:
                        if loc not in modified_locs and loc in fresh:
                            self.todolist_dict[loc] = fresh[loc]

                payload = self._build_payload()

                self._tmp_path.write_text(
                    json.dumps(payload, indent=4, sort_keys=True, ensure_ascii=False),
                    encoding="utf8",
                )
                os.replace(self._tmp_path, self.path)

            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

        # Suppress self-notification in the watchdog handler
        if self._handler is not None:
            self._handler.update_local_state(self._updated_at)

    # ------------------------------------------------------------------
    # Private — validation
    # ------------------------------------------------------------------

    def _validate_loc(self, loc: str):
        if loc not in self.POSSIBLE_LOC:
            raise ValueError(f"Unknown location: {loc!r} — must be one of {self.POSSIBLE_LOC}")
