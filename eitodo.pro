# Qt project file used only by pylupdate6 / lrelease for i18n.
# Not a real qmake build — EiTodo is pure Python.
# Source language is English; add one TRANSLATIONS entry per target locale.

SOURCES = main.py \
          guiqt.py \
          todolist.py \
          general.py \
          output.py \
          logger.py \
          custom_path.py \
          version.py

TRANSLATIONS = translations/eitodo_fr.ts \
               translations/eitodo_de.ts \
               translations/eitodo_es.ts
