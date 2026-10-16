[Deutsch](README.md) | **English**

# 🧠 Raspberry Pi Patient Monitoring 📷

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi%205-C51A4A?style=for-the-badge&logo=Raspberry%20Pi&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![MediaPipe](https://img.shields.io/badge/mediapipe-0097A7?style=for-the-badge&logo=google&logoColor=white)
![OpenCV](https://img.shields.io/badge/opencv-%235C3EE8.svg?style=for-the-badge&logo=opencv&logoColor=white)
![systemd](https://img.shields.io/badge/systemd-201A1E?style=for-the-badge&logo=linux&logoColor=white)

A camera-based patient monitor on a **Raspberry Pi 5**. It tracks **eye, mouth and body movements** with MediaPipe
and logs only anonymous landmark coordinates – never camera images. A **single push button** and an **RGB LED**
control the whole system, so it runs without a keyboard or screen.

Student project, Faculty I – Electrical Engineering and Computer Science, Hochschule Hannover, winter semester
2025/26.

---

## ✨ Features

### 👁️ Monitoring
* **Eye & mouth monitor** – MediaPipe FaceMesh; detects closed eyes with the **Eye Aspect Ratio** (EAR < 0.21)
  and logs the mouth and eye landmarks
* **Body pose monitor** – MediaPipe Pose; logs all **33 body landmarks** with their visibility

### 🔘 One-button control (state machine)
* **Single press** → eye/mouth monitor on/off (LED 🟢 green)
* **Double press** → pose monitor on/off (LED 🔵 blue)
* **Long press** (≥ 1.2 s) → shut down (LED off)
* **LED self-test** at start-up and a 🔴 red blink after every stop or error

### 🔒 Privacy & operation
* Only **normalized landmark coordinates** are stored, as JSON Lines (one line per frame, flushed after every write)
* **Autostart** with systemd

---

## 🏗️ Architecture

```
          push button (GPIO12)            RGB LED (GPIO23/24/25)
                 │                                  ▲
                 ▼                                  │
          controller.py ── state machine: IDLE / MOUTH_RUNNING / POSE_RUNNING
                 │  starts and stops exactly one monitor at a time as a subprocess
       ┌─────────┴──────────┐
       ▼                    ▼
mouth_eye_monitor_picamera2.py   patient_monitor2.py
   FaceMesh + EAR                   Pose
       │                            │
       ▼                            ▼
mouth_eye_<time>.jsonl        pose_<time>.jsonl
```

![State diagram](docs/state-diagram.png)

### 🛡️ Robustness
* **Camera preflight** – before starting a monitor, the controller opens and releases the camera (up to 6 tries),
  so a blocked libcamera pipeline gives a red blink instead of a hung process
* **Clean shutdown** – SIGINT first, `kill()` after a 3 s timeout, then a short pause so the camera is released
* **Button handling** – debouncing, double-press window, grace period after start/stop and automatic calibration
  of the idle level (works with pull-up and pull-down wiring)
* **Single instance** – a lock file prevents two controllers from running at once
* **Frame rate limit** – both monitors run at 15 fps to keep CPU load and temperature down

---

## 🔌 Hardware

| Part | Connection |
|------|------------|
| Raspberry Pi 5 | – |
| Raspberry Pi Camera | CSI |
| RGB LED (common cathode, with series resistors) | GPIO23 red · GPIO24 green · GPIO25 blue |
| Push button | GPIO12 |

---

## 🛠️ Getting Started

On Raspberry Pi OS:

```bash
sudo apt install python3-picamera2 python3-lgpio
python3 -m venv --system-site-packages ~/pose-env && source ~/pose-env/bin/activate
pip install -r requirements.txt
python3 controller.py
```

**Autostart:** copy `deploy/run-paro.sh` to `/usr/local/bin/` and `deploy/paro.service` to
`/etc/systemd/system/`, adjust the paths inside, then run `sudo systemctl enable --now paro`.

> ⚠️ **Known limitation:** under systemd the controller, button and LED work, but the camera monitors only ran
> reliably when started from a desktop session. Likely causes: the missing display and session environment
> (`DISPLAY`, `XDG_RUNTIME_DIR`) and the access permissions for libcamera.

---

## 🧰 Tech Stack

Python · MediaPipe · OpenCV · Picamera2 / libcamera · lgpio · systemd · Raspberry Pi 5
