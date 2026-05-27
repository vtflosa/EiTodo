# EiTodo - Guide d'installation et d'utilisation / Installation and User Guide

**🇫🇷 Français :** [Description](#description) | [🐧 Installation Linux](#-linux) | [Utilisation](#utilisation) | [Désinstallation](#désinstallation)
**🇬🇧 English :** [Description](#description-1) | [🐧 Linux installation](#-linux-1) | [Usage](#usage) | [Uninstallation](#uninstallation)

---

## Version Française

# EiTodo - Guide d'installation et d'utilisation

## Description

EiTodo est un gestionnaire de tâches inspiré de la matrice d'Eisenhower. Il vit dans la zone de notification (system tray) et organise vos tâches dans quatre cadrans selon leur urgence et leur importance. Toutes vos données restent sur votre disque (pas de serveur) ; pour partager les tâches entre plusieurs ordinateurs, il suffit de placer le fichier de données dans un dossier synchronisé (Dropbox, MEGA, Nextcloud, Syncthing, Google Drive…).

Conçu pour Linux uniquement (PyQt6, sauvegarde automatique au reboot via `systemd-logind`).

---

## 🐧 Linux

### Installation

Télécharger le fichier [install_EiTodo.sh](https://raw.githubusercontent.com/vtflosa/EiTodo/master/install_EiTodo.sh) (clic-droit → enregistrer la cible du lien sous…)

Ouvrir un terminal dans le dossier de téléchargement et exécuter :

```bash
bash install_EiTodo.sh
```

L'installateur demande au démarrage :

1. **Installer et lancer au démarrage** — EiTodo se lance automatiquement à chaque ouverture de session.
2. **Installer seulement** — lancement manuel depuis le menu des applications.

Il télécharge le code, installe les dépendances système nécessaires (`python3.X-venv`, `python3-pip`, `libxcb-cursor0`), crée un environnement virtuel Python, installe PyQt6 et `watchdog`, puis met en place un raccourci dans le menu des applications et sur le bureau.

### Mise à jour

Pour passer à une nouvelle version, il suffit de relancer l'installateur :

```bash
bash install_EiTodo.sh
```

Le script récupère la dernière version depuis GitHub. **Vos données, sauvegardes et préférences sont conservées** : le `.gitignore` du dépôt exclut `config.INI`, `param.json`, `logs/` et `save/`, donc l'archive téléchargée ne les contient pas et la décompression ne les écrase pas. L'environnement Python est reconstruit proprement (`venv --clear`) et les dépendances réinstallées.

L'installateur reposera la question de l'autostart au démarrage : vous pouvez confirmer ou changer votre choix précédent.

### Utilisation

#### La matrice d'Eisenhower

EiTodo affiche vos tâches dans quatre cadrans qui croisent **urgence** et **importance** :

|                   | Urgent       | Non urgent              |
| ----------------- | ------------ | ----------------------- |
| **Important**     | À faire      | À planifier             |
| **Non important** | À déléguer   | À supprimer / détente   |

Chaque cadran a deux zones : un éditeur en haut pour la liste active, et une zone en lecture seule en dessous qui conserve les dernières tâches terminées (avec le texte barré). Quand vous supprimez une ligne dans l'éditeur, elle apparaît automatiquement dans la zone du bas.

#### Lancer le programme

- Double-cliquer sur l'icône EiTodo sur le bureau
- Ou le lancer depuis le menu des applications (chercher « EiTodo »)
- Ou laisser l'autostart le faire (si choisi à l'installation)

L'application se loge dans la zone de notification. **Clic gauche** sur l'icône pour afficher/masquer la fenêtre, **clic droit** pour ouvrir le menu.

#### Synchronisation entre plusieurs ordinateurs

Les tâches sont stockées dans un unique fichier JSON. Pour partager la même matrice entre plusieurs machines :

1. Placer le fichier de données dans un dossier synchronisé via un service cloud (Dropbox, MEGA, Nextcloud, Syncthing, Google Drive…) — par exemple via **menu → Changer l'emplacement des données → Déplacer le fichier actuel**.
2. Sur chaque autre ordinateur, installer EiTodo puis utiliser **menu → Changer l'emplacement des données → Indiquer un fichier existant** pour pointer vers le fichier synchronisé.

Les modifications faites sur une machine apparaissent sur l'autre dans les secondes qui suivent, sans relancer l'application.

> ⚠️ **Les partages réseau directs (NAS Samba/NFS, dossier partagé d'un autre PC) ne sont pas recommandés.** La surveillance temps-réel d'EiTodo s'appuie sur les notifications du système de fichiers local, qui ne se déclenchent pas quand un autre poste écrit sur un partage réseau ; vous devriez relancer l'application sur chaque machine pour voir les changements. Un service cloud écrit sur votre disque local et déclenche donc la mise à jour correctement.

#### Sauvegardes automatiques

EiTodo écrit une sauvegarde horodatée dans `~/.local/share/eitodo/save/` :

- **toutes les heures** pendant que l'application tourne
- **à l'extinction** (logout, redémarrage, arrêt, SIGTERM)
- **avant chaque action à risque** (chargement d'une sauvegarde, déplacement du fichier…)

Pour restaurer une sauvegarde : **menu → Charger une sauvegarde**.

Le nombre de sauvegardes conservées se règle via **menu → Nombre de sauvegardes à conserver…** (minimum 20, pas de limite haute, 100 par défaut).

#### Aide intégrée

Une aide détaillée est accessible via **menu → Aide** (dans la langue active).

#### Conseils d'utilisation

- ✅ Multi-langues : français, anglais — changement via **menu → Changer la langue**
- ✅ Synchronisation transparente entre plusieurs machines
- ✅ Sauvegardes automatiques fréquentes et horodatées
- ✅ Aucun serveur — toutes les données restent sur votre disque
- ✅ Police personnalisable via **menu → Changer la police…**

### Désinstallation

Pour supprimer complètement EiTodo :

```bash
bash ~/.local/share/eitodo/uninstall.sh
```

Cela retire le dossier d'installation, le raccourci du menu, le raccourci du bureau et l'entrée d'autostart. **Les sauvegardes dans `~/.local/share/eitodo/save/` sont également supprimées** — copiez-les ailleurs avant si vous voulez les conserver.

---

## Informations techniques

- **Langage :** Python 3
- **Interface :** PyQt6
- **Synchronisation entre instances :** `watchdog` (inotify) + verrou `fcntl`
- **Sauvegarde au reboot :** délai d'inhibition `systemd-logind` via QtDBus
- **Stockage :** un fichier JSON unique + sauvegardes horodatées
- **Internationalisation :** Qt Linguist (`pylupdate6` / `lrelease`)

---

**[⬆ Retour en haut](#eitodo---guide-dinstallation-et-dutilisation--installation-and-user-guide)**

---
---

## English Version

# EiTodo - Installation and User Guide

## Description

EiTodo is a task manager based on the Eisenhower matrix. It lives in the system tray and organises your tasks across four quadrants by urgency and importance. All your data stays on your disk (no server); to share tasks between several computers, just put the data file inside a synced folder (Dropbox, MEGA, Nextcloud, Syncthing, Google Drive…).

Linux only (PyQt6, reboot-save via `systemd-logind`).

---

## 🐧 Linux

### Installation

Download the file [install_EiTodo.sh](https://raw.githubusercontent.com/vtflosa/EiTodo/master/install_EiTodo.sh) (right-click → save link as…)

Open a terminal in the download folder and run:

```bash
bash install_EiTodo.sh
```

At the start the installer asks:

1. **Install and launch at startup** — EiTodo launches automatically at every login.
2. **Install only** — launch manually from the applications menu.

It downloads the code, installs the required system packages (`python3.X-venv`, `python3-pip`, `libxcb-cursor0`), creates a Python virtual environment, installs PyQt6 and `watchdog`, and registers a shortcut in the applications menu and on the desktop.

### Updating

To switch to a new version, just re-run the installer:

```bash
bash install_EiTodo.sh
```

The script fetches the latest version from GitHub. **Your data, backups and preferences are preserved**: the repository's `.gitignore` excludes `config.INI`, `param.json`, `logs/` and `save/`, so the downloaded archive does not contain them and the extraction does not overwrite them. The Python environment is rebuilt cleanly (`venv --clear`) and dependencies reinstalled.

The installer will prompt again about autostart at the start — you can confirm or change your previous choice.

### Usage

#### The Eisenhower matrix

EiTodo lays out tasks in four quadrants crossing **urgency** and **importance**:

|                  | Urgent     | Not urgent          |
| ---------------- | ---------- | ------------------- |
| **Important**    | Do it now  | Schedule it         |
| **Unimportant**  | Delegate   | Drop it / leisure   |

Each quadrant has two zones: an editor on top for the live task list, and a read-only area below that keeps your last finished tasks (struck through). When you delete a line from the editor, it shows up in the area below automatically.

#### Launching the program

- Double-click the EiTodo icon on the desktop
- Or launch it from the applications menu (search for "EiTodo")
- Or let autostart do it (if chosen at install time)

The app lives in the system tray. **Left-click** the icon to show/hide the window, **right-click** to open the menu.

#### Multi-computer synchronisation

Tasks are stored in a single JSON file. To share the same matrix between several machines:

1. Put the data file inside a folder synced through a cloud service (Dropbox, MEGA, Nextcloud, Syncthing, Google Drive…) — for example via **menu → Change data location → Move the current file**.
2. On every other computer, install EiTodo and use **menu → Change data location → Point to an existing file** to select the synced file.

Edits made on one machine appear on the other within seconds, without restarting the app.

> ⚠️ **Direct network shares (NAS Samba/NFS, folders shared from another PC) are not recommended.** EiTodo's live watcher relies on local filesystem notifications, which do not fire when another computer writes to a network share — you would have to restart the app on each machine to see the other side's changes. A cloud-sync service writes to your local disk and therefore triggers the live update correctly.

#### Automatic backups

EiTodo writes a timestamped backup into `~/.local/share/eitodo/save/`:

- **every hour** while the app is running
- **on shutdown** (logout, reboot, power-off, SIGTERM)
- **before any risky action** (loading a backup, moving the data file…)

To restore a backup: **menu → Load a backup**.

The number of backups kept is configured through **menu → Number of backups to keep…** (minimum 20, no upper limit, 100 by default).

#### Built-in help

A detailed help page is available via **menu → Help** (in the active language).

#### Usage tips

- ✅ Multilingual: French, English — switch via **menu → Change language**
- ✅ Transparent sync across multiple machines
- ✅ Frequent, timestamped automatic backups
- ✅ No server — all data stays on your disk
- ✅ Customisable font via **menu → Change font…**

### Uninstallation

To completely remove EiTodo:

```bash
bash ~/.local/share/eitodo/uninstall.sh
```

This removes the install folder, the menu launcher, the desktop shortcut and the autostart entry. **Backups under `~/.local/share/eitodo/save/` are also removed** — copy them elsewhere first if you want to keep them.

---

## Technical information

- **Language:** Python 3
- **UI framework:** PyQt6
- **Multi-instance sync:** `watchdog` (inotify) + `fcntl` lock
- **Reboot save:** `systemd-logind` delay inhibitor via QtDBus
- **Storage:** single JSON file + timestamped backups
- **Internationalisation:** Qt Linguist (`pylupdate6` / `lrelease`)

---

**[⬆ Back to top](#eitodo---guide-dinstallation-et-dutilisation--installation-and-user-guide)**
