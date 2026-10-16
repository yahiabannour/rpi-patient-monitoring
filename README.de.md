[English](README.md) | **Deutsch**

# 🧠 Patienten-Monitoring mit dem Raspberry Pi 📷

Eine datensparsame Überwachungsstation, gebaut mit **Python**, **MediaPipe** und **OpenCV** auf einem
**Raspberry Pi 5**. Sie beobachtet einen Patienten über die Pi-Kamera, erkennt geschlossene Augen, verfolgt Mund-
und Körperbewegungen und protokolliert nur anonyme Landmark-Koordinaten – niemals Bilder. Ein einzelner Taster und
eine RGB-LED steuern das ganze System, es läuft also ohne Tastatur und Bildschirm.

---

## ✨ Funktionen

* **👁️ Augen- & Mund-Monitor**: Erfasst das Gesicht mit **MediaPipe FaceMesh**, erkennt geschlossene Augen über
  die **Eye Aspect Ratio** (EAR < 0,21) und protokolliert die Landmarken von Mund und Augen.
* **🧍 KI-Posenerkennung**: Erfasst alle **33 Körper-Landmarken** mit **MediaPipe Pose**, inklusive Sichtbarkeit.
* **🔘 Bedienung mit einem Taster**: Ein Zustandsautomat wechselt per Einfach-, Doppel- und Langdruck zwischen den
  Monitoren.
* **🚨 LED-Statusanzeige**: Eine RGB-LED zeigt auf einen Blick, welcher Monitor läuft und wann etwas schiefging.
* **🔒 Datenschutz durch Technik**: Gespeichert werden nur normierte Landmark-Koordinaten – keine Kamerabilder.
* **🛡️ Robuster Kamerazugriff**: Kameraprüfung vor jedem Start, sauberes Beenden jedes Monitors und eine Lock-Datei
  gegen Doppelstarts.
* **🔄 Autostart**: Läuft nach dem Booten als **systemd**-Dienst.

---

## 🚦 LED-Statusanzeige

Das System nutzt eine RGB-LED mit drei Pins (gemeinsame Kathode), um den aktuellen Zustand anzuzeigen:

| Farbe | Muster | Bedeutung |
| --- | --- | --- |
| 🔴🟢🔵 | Kurze Abfolge | **Selbsttest**: Rot → Grün → Blau beim Start. |
| ⚫ **Aus** | – | **Leerlauf**: Wartet auf einen Tastendruck, oder beendet. |
| 🟢 **Grün** | Dauerhaft | **Augen- & Mund-Monitor**: FaceMesh läuft. |
| 🔵 **Blau** | Dauerhaft | **Posen-Monitor**: Die Körpererkennung läuft. |
| 🔴 **Rot** | Blinkend (~2 s) | **Rückmeldung / Fehler**: Ein Monitor wurde gestoppt, oder die Kamera war nicht verfügbar. |

![Zustandsdiagramm](docs/state-diagram.png)

---

## 🛠️ Hardware-Aufbau

* **Steuerung**: Raspberry Pi 5.
* **Kamera**: Raspberry-Pi-Kamera am CSI-Anschluss.
* **Peripherie**:
  * **Taster**: An **BCM 12** (automatisch kalibriert, funktioniert mit Pull-up- und Pull-down-Verdrahtung).
  * **RGB-LED**: Pins **BCM 23** (R), **24** (G), **25** (B), jeweils mit Vorwiderstand.

---

## 🚀 Erste Schritte

### 1. Abhängigkeiten installieren

Erst die Systembibliotheken für Kamera und GPIO, dann die Python-Pakete:

```bash
sudo apt install python3-picamera2 python3-lgpio
python3 -m venv --system-site-packages ~/pose-env && source ~/pose-env/bin/activate
pip install -r requirements.txt
```

### 2. Starten

```bash
python3 controller.py
```

### 3. Autostart (optional)

`deploy/run-paro.sh` nach `/usr/local/bin/` und `deploy/paro.service` nach `/etc/systemd/system/` kopieren, die
Pfade darin anpassen und den Dienst aktivieren:

```bash
sudo systemctl enable --now paro
```

> ⚠️ **Bekannte Einschränkung:** Unter systemd funktionieren Controller, Taster und LED, die Kamera-Monitore liefen
> aber nur zuverlässig aus einer Desktop-Sitzung – wahrscheinlich wegen der fehlenden Anzeige- und
> Sitzungsumgebung (`DISPLAY`, `XDG_RUNTIME_DIR`) und der Zugriffsrechte für libcamera.

---

## 🕹️ Bedienung

Das ganze System läuft über **einen einzigen Taster** (BCM 12):

1. **Einfachdruck**: Augen- & Mund-Monitor starten oder stoppen (LED grün).
2. **Doppeldruck**: Posen-Monitor starten oder stoppen (LED blau).
3. **Langdruck** (≥ 1,2 s): Controller beenden (LED aus).

Es läuft immer nur ein Monitor – der Start des einen stoppt den anderen.

---

## 📁 Ausgabedaten

Jede Sitzung schreibt Dateien mit Zeitstempel neben die Skripte:

* `mouth_eye_<Zeitstempel>.jsonl`: Eine Zeile pro Bild – `timestamp`, `eyes_closed`, `mouth_points`, `eye_points`.
* `pose_<Zeitstempel>.jsonl`: Eine Zeile pro Bild – `timestamp` und alle 33 `landmarks` (`x`, `y`, `z`,
  `visibility`).
* `mouth_eye_log.txt`, `pose_monitor_log.txt`: Fehlerprotokolle der beiden Monitore.

Alle Koordinaten sind auf 0…1 normiert, die spätere Auswertung ist also unabhängig von der Kameraauflösung.

---

## 📂 Projektstruktur

* `controller.py`: Taster-Auswertung, Zustandsautomat, LED-Steuerung sowie Starten/Stoppen der Monitore.
* `mouth_eye_monitor_picamera2.py`: Augen- & Mund-Monitor mit FaceMesh und Eye Aspect Ratio.
* `patient_monitor2.py`: Ganzkörper-Posen-Monitor.
* `deploy/`: systemd-Dienst und Startskript.
* `docs/`: Zustandsdiagramm.
