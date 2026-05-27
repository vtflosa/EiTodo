# EiTodo — Help

## The Eisenhower matrix

EiTodo organises tasks into the four quadrants of the Eisenhower
matrix, crossing two dimensions: **urgency** and **importance**.

|                 | Urgent     | Not urgent          |
| --------------- | ---------- | ------------------- |
| **Important**   | Do it now  | Schedule it         |
| **Unimportant** | Delegate   | Drop it / leisure   |

- **Urgent & Important** — fires you must handle yourself, now.
- **Not Urgent & Important** — the long-term work that matters most.
  Put it on a calendar before the urgent stuff crowds it out.
- **Urgent & Unimportant** — interruptions and other people's
  priorities. Delegate when you can; say no when you can't.
- **Not Urgent & Unimportant** — distractions. Drop them, or keep
  them for downtime.

Each quadrant has two zones: an editor on top for the live task
list, and a read-only area below it that keeps your last finished
tasks. When you delete a line from the editor, it shows up there
with a strikethrough. *Clear all finished tasks* in the tray menu
wipes those bottom areas for every quadrant at once.

## Where your data lives

Your tasks are stored as a single **JSON file** (default name
`param.json`), accompanied by a `save/` folder that holds the
timestamped backups. EiTodo never talks to a server — everything
stays on your disk.

The path of the data file is recorded in `config.INI`, under
`[PATH] → json_file_path`. You can view or change it through
**tray → Change data location**, which offers two choices:

- **Point to an existing file** — abandon the current file and
  start reading/writing from another `.json` file you already
  have. EiTodo keeps using that path until you change it again.
- **Move the current file** — physically move the current data
  file (with its content) to a new location and name, then keep
  using it from there.

On first launch, or if the recorded data file is missing, EiTodo
asks the same question before creating anything: keep the default
location, point to an existing file, or create a fresh default
file elsewhere.

Safety net: every time you change the data location or load a
backup, EiTodo first writes a backup of the *current* data into
the save folder. Nothing is lost if you change your mind.

## Sharing tasks across several computers

Because the data is a single JSON file, syncing it through any
file-synchronisation service (Dropbox, MEGA, Nextcloud, Syncthing,
Google Drive, etc.) is enough to share the same matrix between
several computers.

Alternatively, you can place the file on a folder shared across
the local network — a NAS share (Samba/NFS) or any other share
mounted on every machine. On a LAN, updates propagate almost
instantly: an edit on one computer appears on the others within
a second, without any cloud round-trip.

Setup:

1. Put the data file inside a synced folder — for example via
   **Change data location → Move the current file**.
2. On every other computer, install EiTodo and use **Change data
   location → Point to an existing file** to select the synced
   file.

Once running, EiTodo watches the data file for external changes.
When the sync service drops a new version on disk, the other
instances detect it within seconds and refresh their editors
automatically — there is no need to restart the app.

Concurrent edits on different machines:

- A `.lock` file next to the data file coordinates writes.
- Each save preserves the quadrants you did not touch, and only
  overwrites the quadrant you actually changed. If two computers
  edit *different* quadrants around the same time, both edits
  survive.
- If two computers edit the **same** quadrant at roughly the same
  moment, the most recent save wins for that quadrant — the
  previous version is still recoverable from `save/` (see below).
- Sync services usually take a few seconds to propagate a change.
  If you type on two machines at once, give the sync a moment
  before continuing on the other one.

## Automatic backups

EiTodo writes backups into the `save/` folder (path in
`config.INI` under `[PATH] → save_folder_path`). Files are named
`YYYY_MM_DD_HHMMSS_<datafile>.json`, so a plain alphabetical sort
already lists them chronologically.

Backups are written:

- **Every hour** while the app is running.
- **On shutdown**, whatever the cause: tray *Quit*, log-out,
  reboot, shutdown, or `SIGTERM`.
- **Before risky actions**: loading a backup, moving the data
  file, or pointing to a different data file.

To avoid filling the disk with identical copies when the matrix
hasn't changed, EiTodo deduplicates: if the current data matches
the most recent backup (sync metadata aside), the existing backup
is simply renamed with the new timestamp instead of being copied.

The number of backups kept is controlled by **tray → Number
of backups to keep…**: any value from **20** upward (default
**100**, no upper limit). The setting is stored in `config.INI`
under `[CONFIG] → backups_to_keep`. Excess backups beyond the
new limit are removed straight away when you change the value,
and the oldest backups are then deleted whenever the limit is
exceeded again.

To restore a backup, use **tray → Load a backup**: pick a `.json`
file from the save folder and confirm. Before replacing your
current tasks, EiTodo writes a fresh backup of the *current*
matrix, so the load itself is reversible.
