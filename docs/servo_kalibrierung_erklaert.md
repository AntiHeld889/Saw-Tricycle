# Servo-Kalibrierung ganz einfach erklärt

Die Software merkt sich jetzt drei Pulsweiten (Links, Mitte, Rechts) für den Lenkservo. Diese Werte sagen der Elektronik, welchen Steuerimpuls (in Mikrosekunden) sie an den Servo schicken soll, damit er wirklich ganz nach links, in die Mitte oder ganz nach rechts fährt.

## Was im Code passiert

1. Beim Start lädt `tricycle.py` gespeicherte Pulswerte aus dem Web-State. Gibt es noch keine, werden sinnvolle Standardwerte genutzt.
2. Jeder Lenkbefehl wird über eine kleine Tabelle in Pulsweiten übersetzt. Dadurch können linke und rechte Anschläge unterschiedliche Werte haben.
3. Wenn du neue Werte speicherst, prüft die Software erst, ob sie in der erlaubten Reihenfolge liegen (z. B. Links ≤ Mitte ≤ Rechts). Nur gültige Kombinationen werden akzeptiert und gespeichert.
4. Die gespeicherten Werte landen dauerhaft im State-File, sodass sie nach einem Neustart automatisch wieder aktiv sind.

## So nutzt du die Kalibrierung im Web-Interface

1. Öffne die Seite „Weitere Einstellungen“ im Web-Interface.
2. Scrolle zum Abschnitt **„Lenkservo kalibrieren“**.
3. Fahre den Servo manuell (z. B. über die Fernbedienung) an den jeweiligen Anschlag und lies den Wert ab, der zum gewünschten Punkt passt.
4. Trage die Pulsweite in Mikrosekunden (µs) für **Links**, **Mitte** und **Rechts** ein.
5. Wenn du einen Wert änderst, wird er sofort gespeichert. Ungültige Eingaben werden verworfen und der letzte gültige Wert wiederhergestellt.
6. Nach einem Neustart nutzt der Tricycle automatisch deine gespeicherten Kalibrierwerte – du musst nichts weiter tun.

So stellst du sicher, dass der Servo seine physikalischen Grenzen respektiert und das Fahrzeug auch bei kleinen Fertigungstoleranzen sauber geradeaus fährt.
