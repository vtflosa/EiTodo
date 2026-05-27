# EiTodo — Aide

## La matrice d'Eisenhower

EiTodo organise les tâches dans les quatre quadrants de la matrice
d'Eisenhower, qui croise deux axes : **urgence** et **importance**.

|                  | Urgent       | Non urgent              |
| ---------------- | ------------ | ----------------------- |
| **Important**    | À faire      | À planifier             |
| **Non important**| À déléguer   | À supprimer / détente   |

- **Urgent & Important** — les urgences que vous devez traiter
  vous-même, maintenant.
- **Non Urgent & Important** — le travail de fond, celui qui
  compte vraiment à long terme. À caler dans l'agenda avant que
  les urgences ne le grignotent.
- **Urgent & Non Important** — les interruptions et les
  priorités des autres. À déléguer quand c'est possible, à
  refuser sinon.
- **Non Urgent & Non Important** — les distractions. À supprimer,
  ou à garder pour les moments de détente.

Chaque quadrant comporte deux zones : un éditeur en haut pour la
liste de tâches active, et une zone en lecture seule en dessous
qui conserve les dernières tâches terminées. Quand vous supprimez
une ligne dans l'éditeur, elle apparaît en dessous barrée.
*Effacer toutes les tâches finies* (menu de la zone de
notification) vide ces zones inférieures pour les quatre
quadrants d'un coup.

## Où sont stockées vos données

Vos tâches sont enregistrées dans un unique **fichier JSON** (par
défaut `param.json`), accompagné d'un dossier `save/` qui
contient les sauvegardes horodatées. EiTodo ne communique avec
aucun serveur : tout reste sur votre disque.

Le chemin du fichier de données est inscrit dans `config.INI`,
sous `[PATH] → json_file_path`. Vous pouvez le consulter ou le
modifier via **menu → Changer l'emplacement des données**, qui
propose deux choix :

- **Indiquer un fichier existant** — abandonner le fichier
  actuel et utiliser un autre fichier `.json` que vous possédez
  déjà. EiTodo continuera d'utiliser ce chemin jusqu'à la
  prochaine modification.
- **Déplacer le fichier actuel** — déplacer physiquement le
  fichier de données actuel (avec son contenu) vers un nouvel
  emplacement et nom, puis continuer à l'utiliser depuis là.

Au premier lancement, ou si le fichier de données configuré est
introuvable, EiTodo pose la même question avant de créer quoi
que ce soit : garder l'emplacement par défaut, indiquer un
fichier existant, ou créer un nouveau fichier par défaut
ailleurs.

Filet de sécurité : à chaque changement d'emplacement ou
chargement d'une sauvegarde, EiTodo écrit d'abord une sauvegarde
des données *actuelles* dans le dossier `save/`. Rien n'est
perdu si vous changez d'avis.

## Partager les tâches entre plusieurs ordinateurs

Comme les données tiennent dans un unique fichier JSON, il
suffit de le synchroniser via un service de synchronisation de
fichiers (Dropbox, MEGA, Nextcloud, Syncthing, Google Drive,
etc.) pour partager la même matrice entre plusieurs
ordinateurs.

Mise en place :

1. Placez le fichier de données dans un dossier synchronisé —
   par exemple via **Changer l'emplacement des données →
   Déplacer le fichier actuel**.
2. Sur chaque autre ordinateur, installez EiTodo puis utilisez
   **Changer l'emplacement des données → Indiquer un fichier
   existant** pour sélectionner le fichier synchronisé.

Une fois lancé, EiTodo surveille le fichier pour détecter les
modifications externes. Quand le service de synchro dépose une
nouvelle version sur le disque, les autres instances la
détectent en quelques secondes et rafraîchissent leurs éditeurs
automatiquement — pas besoin de relancer l'application.

Édition concurrente sur plusieurs machines :

- Un fichier `.lock` placé à côté du fichier de données
  coordonne les écritures.
- Chaque enregistrement conserve les quadrants que vous n'avez
  pas touchés et n'écrase que celui que vous avez modifié. Si
  deux ordinateurs éditent des quadrants *différents* à peu près
  en même temps, les deux modifications sont conservées.
- Si deux ordinateurs éditent **le même** quadrant quasiment au
  même moment, c'est l'enregistrement le plus récent qui
  l'emporte pour ce quadrant — la version précédente reste
  récupérable depuis `save/` (voir ci-dessous).
- La propagation par le service de synchro prend généralement
  quelques secondes. Si vous tapez sur deux machines en même
  temps, laissez à la synchro le temps de s'établir avant de
  continuer sur l'autre.

## Sauvegardes automatiques

EiTodo écrit les sauvegardes dans le dossier `save/` (chemin
indiqué dans `config.INI` sous `[PATH] → save_folder_path`). Les
fichiers sont nommés `AAAA_MM_JJ_HHMMSS_<fichier>.json`, ce qui
donne directement l'ordre chronologique par tri alphabétique.

Les sauvegardes sont écrites :

- **Toutes les heures** pendant que l'application tourne.
- **À l'extinction**, quelle qu'en soit la cause : *Quitter* du
  menu, déconnexion, redémarrage, arrêt, ou `SIGTERM`.
- **Avant chaque action à risque** : chargement d'une sauvegarde,
  déplacement du fichier de données, changement vers un autre
  fichier.

Pour éviter d'accumuler des copies identiques quand la matrice
n'a pas bougé, EiTodo déduplique : si les données actuelles sont
identiques à la dernière sauvegarde (métadonnées de synchro
mises à part), la sauvegarde existante est simplement renommée
avec le nouvel horodatage au lieu d'être recopiée.

Le nombre de sauvegardes conservées se règle via **menu →
Nombre de sauvegardes à conserver…** : n'importe quelle valeur
à partir de **20** (par défaut **100**, sans limite haute). Le
réglage est inscrit dans `config.INI` sous `[CONFIG] →
backups_to_keep`. Les sauvegardes en trop sont supprimées
immédiatement quand vous changez la valeur, puis les plus
anciennes sont supprimées au fil de l'eau dès que la limite est
de nouveau dépassée.

Pour restaurer une sauvegarde, utilisez **menu → Charger une
sauvegarde** : choisissez un fichier `.json` dans le dossier
`save/` et confirmez. Avant de remplacer vos tâches actuelles,
EiTodo écrit une nouvelle sauvegarde de la matrice *en cours*,
de sorte que le chargement reste réversible.
