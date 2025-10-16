# Entwickler-Werkzeuge

Dieses Verzeichnis enthält Hilfsskripte für Wartungsaufgaben.

## `find_unused_symbols.py`

Analysiert die Python-Dateien des Projekts und meldet Modul-Symbole (Funktionen, Klassen und Variablen),
für die keine Referenz im Quellcode gefunden wurde. Damit lässt sich schnell prüfen, ob unbeabsichtigt
Code-Leichen entstanden sind.

Beispielaufruf für das gesamte Repository:

```bash
python tools/find_unused_symbols.py
```

Ein bestimmtes Verzeichnis oder eine Datei kann optional angegeben werden:

```bash
python tools/find_unused_symbols.py tricycle.py webui
```

Das Skript gibt eine Liste der verdächtigen Symbole mit Dateipfad und Zeilennummer aus. Werden keine
Treffer gefunden, bestätigt es dies explizit.
