# CLAUDE.md

Guidance for working in this repository. Follow it exactly.

## What EiTodo is

A Linux-only desktop app (PyQt6) implementing the Eisenhower matrix: four
task quadrants (urgent/important crossed with their negations), each with an
active list and a "done" list. It lives in the system tray, stores everything
in a single `param.json`, and can sync across machines through a cloud-synced
folder (it is multi-instance safe). **Linux only for now** — do not add
Windows/macOS branches or cross-platform shims; rely on Linux facilities
(`fcntl`, `systemd-logind`, inotify) directly.

## Golden rules

- **French for talking to user in console**
- **English only in the codebase.** All code, comments, and docstrings are in
  English. The two exceptions are documented below (quadrant titles, personal
  dev-notes) — do not introduce others.
- **Simple and efficient wins.** Prefer the straightforward, readable solution
  over a clever one. Keep the code resource-light: this app idles in the tray
  all day, so avoid needless timers, polling, allocations, or work done while
  nothing changed. When you touch a hot path, make sure it stays efficient.
- **PEP 8.** Follow it as closely as the surrounding code allows (4-space
  indent, snake_case, import grouping: stdlib / third-party / local). Match the
  existing style of the file you are editing.
- **No personal data leaks to GitHub** — see the dedicated section; check
  before every commit/push.

## Reuse: helpers and paths

Do not reinvent things that already exist.

- **`general.py`** holds the shared helpers — put new general-purpose helpers
  there and import them, rather than duplicating logic inline. It already
  provides:
  - config I/O: `read_config_file`, `read_config_file_menu`,
    `write_config_file`, `write_config_file_menu` (operate on `config.INI`).
  - timestamps/date: `get_date`, `get_timestamp`, `get_timestamp_with_date`,
    `get_hour`.
  - text/bullet helpers for quadrant items: `is_empty`, `clean_line`,
    `clean_text`, `snapshot`, `get_raw`.
- **`custom_path.py` (`Path` class)** is the single source of truth for every
  filesystem path. Use `Path.dir_path`, `Path.user_path`, `Path.icon_path`,
  `Path.config_file_path`, `Path.json_file_path`, `Path.log_folder`,
  `Path.save_folder`, `Path.translations_folder`, `Path.docs_folder`. Never
  hardcode a path or rebuild one with `os.path.join(__file__, ...)` — add it to
  `Path` if it is missing. Use `Path.check_file` / `Path.check_folder` to
  validate.

## Logging: use `Output`, not `print`

Route all user-visible/diagnostic output through `Output.print(...)` from
`output.py` — never bare `print()`. It mirrors to stdout, the log file (once
the logger is up), and a thread-safe queue. Pass an explicit level:
`level="info"` (default), `"warning"`, `"error"`, or `"nolog"` to skip the log
file. It is thread-safe, so it is also the correct call from watchdog's
background thread.

## Internationalisation (i18n)

Source language is **English**. Supported UI languages: **en, fr, de, es**.
Catalogs live in `translations/` as `eitodo_<lang>.ts` (source) and
`eitodo_<lang>.qm` (compiled, loaded at runtime). `eitodo.pro` lists the source
files and the target `.ts` files for the Qt tools.

**Whenever you add or change any UI-visible string, you must update the
translations** — otherwise non-English users see stale or English text. The
in-app help also exists per language as `docs/help_<lang>.md`; update all four
when the behaviour described changes.

Rules:
- Wrap every user-facing string in a widget/`QObject` with `self.tr("...")`
  (or `QCoreApplication.translate("Context", "...")` outside a `QObject`, as in
  `main._default_param`). Write the call out in full — `pylupdate6` extracts
  strings statically and cannot follow an alias.
- After editing strings, regenerate the catalogs:

  ```bash
  # 1. Extract new/changed strings into the .ts files (pylupdate6 from the venv)
  .venv/bin/pylupdate6 eitodo.pro

  # 2. Translate the new entries (edit the .ts files, or open them in Qt Linguist)

  # 3. Compile .ts -> .qm so the app picks them up at runtime
  lrelease eitodo.pro
  ```

  Commit the updated `.ts` **and** `.qm` files together.

### Two intentional non-English exceptions

- **Quadrant titles stay hardcoded English** in `guiqt.py` (the four Eisenhower
  labels). Do **not** wrap them in `tr()`.
- **Personal `# todo …` dev-notes stay French.** Some comments are the author's
  personal task list (notably the block at the top of `main.py`). Leave those in
  French. The English-only rule applies to production code, comments, and
  docstrings — not to these personal notes.

## Privacy: no personal data on GitHub

This is a public repo with the author's real todo data on the same machine.
Before committing or pushing, make sure none of it leaks:

- These are already in `.gitignore` and must stay ignored — never force-add
  them: `config.INI`, `param.json`, `param.lock`, `logs/`, `save/`, `.venv/`,
  `.idea/`, `source/`.
- `save/` and `logs/` contain real task text and machine details — never paste
  their contents into commits, the README, docs, or examples.
- When adding example data or screenshots, use invented placeholder tasks, not
  the author's real ones.
- `git user`/email and absolute home paths (`/home/<user>/...`) should not be
  written into tracked files.
- Run `git status` / `git diff --staged` before any commit and confirm only
  intended, data-free files are staged.

## Running the app

There is no automated test suite; verify changes by running the app and
exercising the affected behaviour.

```bash
.venv/bin/python main.py     # launch (uses the project virtualenv)
```

It starts in the tray (or hidden if `start_hidden=true`). Logs stream to stdout
and to `logs/`. First launch creates `config.INI`, `param.json`, `logs/`, and
`save/`. Do **not** enable autostart as a side effect of anything — autostart is
opt-in through the installer prompt only.

## Sensitive architecture — do not break

Two areas are subtle and load-bearing. Understand them before changing them.

- **Shutdown/exit save (`main.py`).** `param.json` must be backed up on every
  exit route. Three complementary layers funnel into the idempotent
  `MainWindow._perform_shutdown_save()`: (1) a `systemd-logind` *delay*
  inhibitor via QtDBus — the only thing that fires on a real reboot/poweroff;
  (2) Qt `commitDataRequest` (X11 logout) + `aboutToQuit`; (3) POSIX
  `SIGTERM`/`SIGHUP` bridged to the Qt loop via `set_wakeup_fd` + a
  `QSocketNotifier`. Keep the save idempotent and keep all layers wired.
- **Multi-instance sync (`todolist.py`).** Concurrent instances share one JSON
  file safely via: an exclusive `fcntl.flock`, atomic write (`.tmp` +
  `os.replace`), a monotonic `version` counter plus `updated_at`/`last_writer`
  for change detection, per-quadrant last-writer-wins merging inside the lock,
  and a `watchdog` (inotify) observer that calls back on remote changes. Remote
  callbacks arrive on a background thread — marshal to the GUI thread via the
  existing `pyqtSignal` (see `MainWindow._remote_change`); never touch widgets
  from the watchdog thread.

## Git

- Commit or push **only when asked.** When you do, keep the existing style:
  Conventional-Commits prefixes (`feat:`, `chore:`, `docs:`), often with the
  version, e.g. `feat: 1.4 — right-click menus on quadrants`.
- Bump the version by appending a new line in `version.py` (`version()`); the
  tray header and logs read from it. Mirror the bump in the commit subject when
  relevant.
