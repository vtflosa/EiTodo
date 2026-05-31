# EiTodo — Ayuda

## La matriz de Eisenhower

EiTodo organiza las tareas en los cuatro cuadrantes de la matriz
de Eisenhower, cruzando dos dimensiones: **urgencia** e
**importancia**.

|                    | Urgente       | No urgente              |
| ------------------ | ------------- | ----------------------- |
| **Importante**     | Hacerlo ya    | Planificarlo            |
| **No importante**  | Delegar       | Descartar / tiempo libre |

- **Urgente e Importante** — incendios que debes apagar tú mismo,
  ahora.
- **No Urgente e Importante** — el trabajo de fondo, lo que más
  cuenta a largo plazo. Ponlo en el calendario antes de que lo
  urgente lo desplace.
- **Urgente y No Importante** — interrupciones y prioridades de
  otros. Delega cuando puedas; di que no cuando no puedas.
- **No Urgente y No Importante** — distracciones. Descártalas, o
  guárdalas para los ratos libres.

Cada cuadrante tiene dos zonas: un editor arriba para la lista de
tareas activa, y debajo una zona de solo lectura que guarda las
últimas tareas terminadas. Cuando borras una línea del editor,
aparece ahí tachada. *Borrar todas las tareas terminadas* en el
menú vacía esas zonas inferiores en los cuatro cuadrantes a la
vez.

## Reorganizar y mover las tareas

Además de escribir directamente, varios atajos y acciones de
clic derecho ayudan a organizar las tareas:

- **Ctrl+Arriba / Ctrl+Abajo** — mueve la línea que contiene el
  cursor una posición hacia arriba o abajo (solo líneas no
  vacías).
- **Ctrl+clic sobre un enlace** — abre un enlace web detectado
  (`http://`, `https://` o `www.`) en el navegador. Al mantener
  Ctrl sobre un enlace, el cursor toma forma de mano.

**Clic derecho sobre una tarea activa** abre un menú con:

- **Abrir enlace** — si se detecta una URL bajo el cursor.
- **Subir / Bajar** — equivalentes a los atajos Ctrl+Flecha.
- **Marcar como terminada** — retira la tarea del editor y la
  coloca en la zona de tareas terminadas (tachada).
- **Mover al cuadrante ▸** — submenú con los otros tres
  cuadrantes; la tarea desaparece de aquí y reaparece arriba en
  la lista activa del cuadrante elegido.

**Clic derecho sobre una tarea terminada** (zona tachada) abre:

- **Restaurar a la lista activa** — devuelve la tarea arriba en
  la lista activa del mismo cuadrante.
- **Restaurar al cuadrante ▸** — submenú con los otros tres
  cuadrantes; restaura la tarea en la lista activa de otro
  cuadrante.
- **Eliminar permanentemente** — retira la tarea de la lista
  de terminadas para siempre.

## Dónde se guardan tus datos

Tus tareas se guardan en un único **archivo JSON** (nombre por
defecto `param.json`), acompañado de una carpeta `save/` que
contiene las copias de seguridad con marca de tiempo. EiTodo no
habla con ningún servidor — todo se queda en tu disco.

La ruta del archivo de datos se registra en `config.INI`, en
`[PATH] → json_file_path`. Puedes verla o cambiarla mediante
**menú → Cambiar ubicación de los datos**, que ofrece dos
opciones:

- **Apuntar a un archivo existente** — abandona el archivo
  actual y empieza a leer/escribir desde otro archivo `.json`
  que ya tengas. EiTodo seguirá usando esa ruta hasta que la
  vuelvas a cambiar.
- **Mover el archivo actual** — mueve físicamente el archivo de
  datos actual (con su contenido) a una nueva ubicación y
  nombre, y sigue usándolo desde ahí.

En el primer arranque, o si el archivo de datos registrado
desaparece, EiTodo hace la misma pregunta antes de crear nada:
conservar la ubicación por defecto, apuntar a un archivo
existente, o crear un archivo por defecto nuevo en otro sitio.

Red de seguridad: cada vez que cambias de ubicación o cargas
una copia de seguridad, EiTodo escribe primero una copia de los
datos *actuales* en la carpeta save. No se pierde nada si
cambias de idea.

## Compartir tareas entre varios ordenadores

Como los datos caben en un único archivo JSON, basta con
sincronizarlo mediante cualquier servicio de sincronización de
archivos (Dropbox, MEGA, Nextcloud, Syncthing, Google Drive,
etc.) para compartir la misma matriz entre varios ordenadores.

**Los recursos de red directos no son recomendables** (NAS
Samba/NFS, carpetas compartidas desde otro ordenador). EiTodo
vigila el archivo de datos mediante las notificaciones del
sistema de archivos local del sistema operativo, que no se
disparan cuando otra máquina escribe en un recurso de red. Con
un recurso de red tendrías que reiniciar la aplicación en cada
ordenador para obtener las modificaciones del otro lado. Un
servicio de sincronización en la nube escribe en tu disco local
y, por tanto, dispara la actualización en vivo correctamente —
quédate con esta solución.

Instalación:

1. Coloca el archivo de datos dentro de una carpeta
   sincronizada — por ejemplo a través de **Cambiar ubicación
   de los datos → Mover el archivo actual**.
2. En cada otro ordenador, instala EiTodo y usa **Cambiar
   ubicación de los datos → Apuntar a un archivo existente**
   para seleccionar el archivo compartido.

Una vez en marcha, EiTodo vigila el archivo de datos en busca
de cambios externos. Cuando el servicio de sincronización deja
una nueva versión en disco, las demás instancias lo detectan
en segundos y refrescan sus editores automáticamente — no hace
falta reiniciar la aplicación.

Edición concurrente en máquinas distintas:

- Un archivo `.lock` junto al archivo de datos coordina las
  escrituras.
- Cada guardado conserva los cuadrantes que no has tocado y
  solo sobrescribe el cuadrante que realmente has cambiado. Si
  dos ordenadores editan cuadrantes *distintos* casi a la vez,
  ambas modificaciones se mantienen.
- Si dos ordenadores editan **el mismo** cuadrante casi a la
  vez, gana el guardado más reciente para ese cuadrante — la
  versión anterior sigue siendo recuperable desde `save/`
  (véase más abajo).
- Los servicios de sincronización suelen tardar unos segundos
  en propagar un cambio. Si tecleas en dos máquinas a la vez,
  dale un momento a la sincronización antes de continuar en la
  otra.

## Copias de seguridad automáticas

EiTodo escribe las copias de seguridad en la carpeta `save/`
(ruta en `config.INI`, en `[PATH] → save_folder_path`). Los
archivos se llaman `AAAA_MM_DD_HHMMSS_<archivo>.json`, así que
una simple ordenación alfabética ya los pone en orden
cronológico.

Las copias se escriben:

- **Cada hora** mientras la aplicación está en marcha.
- **Al cerrar**, sea cual sea la causa: *Salir* del menú, cierre
  de sesión, reinicio, apagado o `SIGTERM`.
- **Antes de cualquier acción arriesgada**: cargar una copia,
  mover el archivo de datos o apuntar a otro archivo.

Para no llenar el disco con copias idénticas cuando la matriz
no ha cambiado, EiTodo deduplica: si los datos actuales
coinciden con la última copia (excluyendo los metadatos de
sincronización), la copia existente se renombra simplemente
con la nueva marca de tiempo en lugar de duplicarse.

El número de copias conservadas se ajusta desde
**menú → Número de copias de seguridad…**: cualquier valor a
partir de **20** (por defecto **100**, sin límite superior).
El ajuste se guarda en `config.INI`, en
`[CONFIG] → backups_to_keep`. Las copias excedentes se eliminan
de inmediato al cambiar el valor; después, las copias más
antiguas se borran cada vez que se vuelve a superar el límite.

Para restaurar una copia, usa **menú → Cargar una copia de
seguridad**: elige un archivo `.json` de la carpeta save y
confirma. Antes de reemplazar tus tareas actuales, EiTodo
escribe una copia nueva de la matriz *actual*, de modo que la
carga también es reversible.

## Reactividad de la interfaz

Cuando dejas de escribir, EiTodo espera un breve instante antes
de formatear la línea y guardarla — este «debounce» evita
trabajar con cada pulsación. **menú → Reactividad de la
interfaz…** abre un control deslizante con muescas: muévelo a la
izquierda para un retraso más corto (más reactivo, trabajo algo
más frecuente) o a la derecha para un retraso más largo (más
ligero para los recursos). Las muescas van de 200 a 1000 ms, en
pasos de 100 ms; **Restaurar valores predeterminados** vuelve a
400 ms. El cambio surte efecto de inmediato.
