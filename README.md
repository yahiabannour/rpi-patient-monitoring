**English** | [Deutsch](README.de.md)

# 🧠 Raspberry Pi Patient Monitoring 📷

A privacy-friendly monitoring station built with **Python**, **MediaPipe** and **OpenCV** on a **Raspberry Pi 5**.
It watches a patient through the Pi camera, detects closed eyes, tracks mouth and full-body movements, and logs only
anonymous landmark coordinates – never images. A single push button and an RGB LED control the whole system, so it
runs without keyboard or screen.

---

## ✨ Features

* **👁️ Eye & Mouth Monitor**: Tracks the face with **MediaPipe FaceMesh**, detects closed eyes via the
  **Eye Aspect Ratio** (EAR < 0.21) and logs the mouth and eye landmarks.
* **🧍 AI Pose Tracking**: Tracks all **33 body landmarks** with **MediaPipe Pose**, including their visibility.
* **🔘 One-Button Control**: A state machine switches between the monitors with single, double and long presses.
* **🚨 LED Status Feedback**: An RGB LED shows at a glance which monitor is running and when something went wrong.
* **🔒 Privacy by Design**: Only normalized landmark coordinates are stored – no camera images.
* **🛡️ Robust Camera Handling**: A camera check before every start, a clean shutdown of each monitor and a lock
  file against double starts.
* **🔄 Autostart**: Runs as a **systemd** service after boot.

---

## 🚦 LED Status Guide

The system uses a 3-pin RGB LED (common cathode) to show the current state:

| Color | Pattern | Meaning |
| --- | --- | --- |
| 🔴🟢🔵 | Short sequence | **Self-test**: Red → green → blue at start-up. |
| ⚫ **Off** | – | **Idle**: Waiting for a button press, or shut down. |
| 🟢 **Green** | Solid | **Eye & mouth monitor**: FaceMesh is running. |
| 🔵 **Blue** | Solid | **Pose monitor**: Body tracking is running. |
| 🔴 **Red** | Blinking (~2 s) | **Feedback / error**: A monitor was stopped, or the camera was not available. |

![State diagram](docs/state-diagram.png)

---

## 🛠️ Hardware Setup

* **Controller**: Raspberry Pi 5.
* **Camera**: Raspberry Pi camera on the CSI port.
* **Peripherals**:
  * **Button**: Connected to **BCM 12** (auto-calibrated, works with pull-up or pull-down wiring).
  * **RGB LED**: Pins **BCM 23** (R), **24** (G), **25** (B), each with a series resistor.

---

## 🚀 Getting Started

### 1. Install Dependencies

Install the system libraries for the camera and GPIO, then the Python packages:

```bash
sudo apt install python3-picamera2 python3-lgpio
python3 -m venv --system-site-packages ~/pose-env && source ~/pose-env/bin/activate
pip install -r requirements.txt
```

### 2. Execution

```bash
python3 controller.py
```

### 3. Autostart (optional)

Copy `deploy/run-paro.sh` to `/usr/local/bin/` and `deploy/paro.service` to `/etc/systemd/system/`, adjust the
paths inside, then enable the service:

```bash
sudo systemctl enable --now paro
```

> ⚠️ **Known limitation:** Under systemd the controller, button and LED work, but the camera monitors only ran
> reliably when started from a desktop session – most likely because of the missing display and session
> environment (`DISPLAY`, `XDG_RUNTIME_DIR`) and the access permissions for libcamera.

---

## 🕹️ User Controls

The whole system runs on a **single button** (BCM 12):

1. **Single press**: Start or stop the eye & mouth monitor (LED green).
2. **Double press**: Start or stop the pose monitor (LED blue).
3. **Long press** (≥ 1.2 s): Shut down the controller (LED off).

Only one monitor runs at a time – starting one stops the other.

---

## 📁 Data Output Structure

Each session writes timestamped files next to the scripts:

* `mouth_eye_<timestamp>.jsonl`: One line per frame – `timestamp`, `eyes_closed`, `mouth_points`, `eye_points`.
* `pose_<timestamp>.jsonl`: One line per frame – `timestamp` and all 33 `landmarks` (`x`, `y`, `z`, `visibility`).
* `mouth_eye_log.txt`, `pose_monitor_log.txt`: Error logs of the two monitors.

All coordinates are normalized to 0…1, so later analysis is independent of the camera resolution.

---

## 📂 Project Structure

* `controller.py`: Button handling, state machine, LED control and starting/stopping the monitors.
* `mouth_eye_monitor_picamera2.py`: Eye & mouth monitor with FaceMesh and the Eye Aspect Ratio.
* `patient_monitor2.py`: Full-body pose monitor.
* `deploy/`: systemd service and start script.
* `docs/`: State diagram.
