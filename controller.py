#!/usr/bin/env python3
import time, os, sys, signal, subprocess, lgpio, statistics
from pathlib import Path

# ========= CONFIG =========
GPIO_CHIP = 0

# 3-color LED pins (BCM)
RED_PIN   = 23  # error / feedback
GREEN_PIN = 24  # mouth/eye running
BLUE_PIN  = 25  # pose running

# Button 
BUTTON_PIN = 12

# LED wiring type
COMMON_ANODE = False  

# Button timings
DEBOUNCE_SEC = 0.05
DOUBLE_PRESS_WIN = 0.45
LONG_PRESS_SEC = 1.2
START_STOP_GRACE_SEC = 0.5  # ignore long-press immediately after start/stop

# LED blink timing for errors
ERROR_BLINK_PERIOD = 0.5

# Camera preflight / retry
CAM_PREFLIGHT_MAX_TRIES = 6
CAM_PREFLIGHT_SLEEP_S   = 0.8
# ==========================

BASE_DIR = Path(__file__).resolve().parent
MOUTH_SCRIPT = str(BASE_DIR / "mouth_eye_monitor_picamera2.py")
POSE_SCRIPT  = str(BASE_DIR / "patient_monitor2.py")

IDLE, MOUTH_RUNNING, POSE_RUNNING = "IDLE", "MOUTH_RUNNING", "POSE_RUNNING"

# ---------- single-instance lock ----------
LOCK = "/tmp/monitor_controller.lock"
if os.path.exists(LOCK):
    print("[ABORT] Another controller instance is already running.")
    sys.exit(1)
open(LOCK, "w").close()
import atexit; atexit.register(lambda: os.path.exists(LOCK) and os.remove(LOCK))

# ---------- LED helpers ----------
def _w(chip, pin, on):
    if COMMON_ANODE:
        lgpio.gpio_write(chip, pin, 0 if on else 1)
    else:
        lgpio.gpio_write(chip, pin, 1 if on else 0)

def leds_off(chip):
    for p in (RED_PIN, GREEN_PIN, BLUE_PIN):
        try: _w(chip, p, False)
        except: pass

def led_red(chip):   leds_off(chip); _w(chip, RED_PIN,   True)
def led_green(chip): leds_off(chip); _w(chip, GREEN_PIN, True)
def led_blue(chip):  leds_off(chip); _w(chip, BLUE_PIN,  True)

def leds_selftest(chip, hold=0.25):
    for f in (led_red, led_green, led_blue):
        f(chip); time.sleep(hold)
    leds_off(chip)

# ---------- camera preflight ----------
def camera_ready():
    """
    Try to open/close Picamera2 briefly; return True if OK.
    Ensure .close() so pipeline releases before child starts.
    """
    try:
        from picamera2 import Picamera2
        from libcamera import controls  # import ensures bindings OK
        cam = Picamera2()
        cam.start()
        time.sleep(0.2)
        cam.stop()
        try:
            cam.close()
        except Exception:
            pass
        del cam
        time.sleep(0.05)  # tiny settle to fully release pipeline
        return True
    except Exception as e:
        print(f"[CAM] not ready yet: {e}")
        return False

class Runner:
    def __init__(self):
        self.proc = None
        self.state = IDLE
        self.last_action_time = 0.0

    def _mark_action(self):
        self.last_action_time = time.time()

    def _start(self, which):
        if self.proc is not None:
            return

        # Preflight camera
        tries = 0
        while tries < CAM_PREFLIGHT_MAX_TRIES:
            if camera_ready():
                break
            tries += 1
            time.sleep(CAM_PREFLIGHT_SLEEP_S)

        if tries >= CAM_PREFLIGHT_MAX_TRIES:
            print("[ERROR] Camera not ready after retries; not starting.")
            # Mark an action so the LED logic triggers the short red-blink
            self.state = IDLE
            self._mark_action()
            return

        script = MOUTH_SCRIPT if which == "mouth" else POSE_SCRIPT
        print(f"[INFO] Starting {which} monitor: {script}")
        self.proc = subprocess.Popen(
            [sys.executable, script],
            cwd=str(BASE_DIR),
            env=os.environ.copy()
        )
        self.state = MOUTH_RUNNING if which == "mouth" else POSE_RUNNING
        self._mark_action()

    def _stop(self):
        if self.proc is None:
            return
        print("[INFO] Stopping current monitor...")
        try:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                print("[WARN] Force killing process…")
                self.proc.kill()
        finally:
            self.proc = None
            self.state = IDLE
            time.sleep(0.4)  # let camera release
            self._mark_action()

    def toggle_mouth(self):
        if self.state == MOUTH_RUNNING:
            self._stop()
        else:
            if self.state == POSE_RUNNING:
                self._stop()
            self._start("mouth")

    def toggle_pose(self):
        if self.state == POSE_RUNNING:
            self._stop()
        else:
            if self.state == MOUTH_RUNNING:
                self._stop()
            self._start("pose")

def autocalibrate_button(chip):
    samples = []
    t0 = time.time()
    while time.time() - t0 < 0.5:
        samples.append(lgpio.gpio_read(chip, BUTTON_PIN))
        time.sleep(0.002)
    idle_level = int(round(statistics.median(samples))) if samples else 1
    active_level = 0 if idle_level == 1 else 1
    print(f"[CALIB] Button idle={idle_level}, active={active_level}")
    return idle_level, active_level

def main():
    exiting = False  # avoid double cleanup
    chip = lgpio.gpiochip_open(GPIO_CHIP)

    # Claim LED pins (retry a bit)
    for name, pin in (("RED", RED_PIN), ("GREEN", GREEN_PIN), ("BLUE", BLUE_PIN)):
        for attempt in range(5):
            try:
                lgpio.gpio_claim_output(chip, pin)
                break
            except lgpio.error as e:
                print(f"[GPIO] {name} pin claim failed (attempt {attempt+1}/5): {e}")
                time.sleep(0.2)
        else:
            print("[GPIO] Could not claim LED pins. Is another controller/service running?")
            try: lgpio.gpiochip_close(chip)
            except: pass
            return
    leds_selftest(chip)

    # Button (try internal pull-up if available; still auto-calibrate)
    try:
        FLG = getattr(lgpio, "BIAS_PULL_UP", None) or getattr(lgpio, "SET_BIAS_PULL_UP", None)
        if FLG is not None:
            lgpio.gpio_claim_input(chip, BUTTON_PIN, FLG)
            print("[GPIO] BUTTON with internal pull-up enabled")
        else:
            lgpio.gpio_claim_input(chip, BUTTON_PIN)
            print("[GPIO] BUTTON without explicit pull-up (no bias flag)")
    except Exception as e:
        print(f"[GPIO] Pull-up claim not supported ({e}); using plain input")
        lgpio.gpio_claim_input(chip, BUTTON_PIN)

    idle_level, active_level = autocalibrate_button(chip)

    runner = Runner()
    print(f"[PATH] Using Python: {sys.executable}")
    print("Ready:")
    print("  • Single press  -> toggle MOUTH+EYE (LED GREEN)")
    print("  • Double press  -> toggle POSE (LED BLUE)")
    print("  • Long press    -> EXIT program (LEDs off)")

    try:
        last_level = lgpio.gpio_read(chip, BUTTON_PIN)
        first_press_time = None
        pending_single = False
        press_start_time = None
        long_fired = False
        err_blink_on = False
        last_err_blink = time.time()

        while True:
            level = lgpio.gpio_read(chip, BUTTON_PIN)
            now = time.time()

            # press edge
            if last_level == idle_level and level == active_level:
                press_start_time = now
                long_fired = False

            # release edge
            if last_level == active_level and level == idle_level:
                time.sleep(DEBOUNCE_SEC)
                if long_fired:
                    first_press_time = None
                    pending_single = False
                    long_fired = False
                    press_start_time = None
                else:
                    if first_press_time is None:
                        first_press_time = now
                        pending_single = True
                    else:
                        if (now - first_press_time) <= DOUBLE_PRESS_WIN:
                            print("[BTN] double press -> toggle pose")
                            runner.toggle_pose()
                            first_press_time = None
                            pending_single = False
                        else:
                            print("[BTN] single press -> toggle mouth/eye")
                            runner.toggle_mouth()
                            first_press_time = now
                            pending_single = True

            # long press -> EXIT (no double cleanup)
            if (press_start_time is not None and
                not long_fired and
                level == active_level and
                (now - runner.last_action_time) > START_STOP_GRACE_SEC and
                (now - press_start_time) >= LONG_PRESS_SEC):
                print("[BTN] LONG PRESS -> EXIT")
                exiting = True
                break

            # execute pending single if double window expired
            if pending_single and first_press_time is not None:
                if (now - first_press_time) > DOUBLE_PRESS_WIN:
                    print("[BTN] single press -> toggle mouth/eye")
                    runner.toggle_mouth()
                    pending_single = False
                    first_press_time = None

            last_level = level

            # if child died unexpectedly, go IDLE (RED blink shortly)
            if runner.proc is not None and runner.proc.poll() is not None:
                print(f"[WARN] Monitor exited with code {runner.proc.returncode}")
                runner.proc = None
                runner.state = IDLE
                runner._mark_action()

            # LED state
            if runner.state == MOUTH_RUNNING:
                led_green(chip)
            elif runner.state == POSE_RUNNING:
                led_blue(chip)
            else:
                # idle: brief RED blink after last action (start/stop/fail)
                since = now - runner.last_action_time
                if since < 2.0:
                    if (now - last_err_blink) >= (ERROR_BLINK_PERIOD / 2.0):
                        err_blink_on = not err_blink_on
                        last_err_blink = now
                        if err_blink_on:
                            led_red(chip)
                        else:
                            leds_off(chip)
                else:
                    leds_off(chip)

            time.sleep(0.01)

    finally:
        # single, idempotent cleanup path
        try:
            runner._stop()
        except: pass
        try:
            leds_off(chip)
        except: pass
        try:
            lgpio.gpiochip_close(chip)
        except: pass
        if exiting:
            sys.exit(0)

if __name__ == "__main__":
    main()
