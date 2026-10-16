import cv2
import json
import time
from datetime import datetime
import sys
import mediapipe as mp
import numpy as np
from picamera2 import Picamera2
from libcamera import controls

mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_pose = mp.solutions.pose

class Camera():
    def __init__(self, resolution=(640, 480), frame_rate=15, exposure=10000):
        self.resolution = resolution
        self.frame_rate = frame_rate
        self.exposure = exposure
        self.frame_time = 1 / frame_rate
        self.picam = None
        self.prev_time = None
        self.open()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def open(self):
        self.picam = Picamera2()
        config = self.picam.create_video_configuration(
            main={"size": self.resolution},
            controls={
                "FrameRate": self.frame_rate,
                "ExposureTime": self.exposure,
                "AwbMode": controls.AwbModeEnum.Auto
            }
        )
        self.picam.configure(config)
        self.picam.start()

    def close(self):
        if self.picam is not None:
            self.picam.stop()
            self.picam = None

    def getFrame(self):
        if self.picam is None:
            raise Exception("camera capture failed (not opened)")
        if self.prev_time is not None:
            time_now = time.time()
            time_already_passed = time_now - self.prev_time
            time_to_wait = self.frame_time - time_already_passed
            if time_to_wait > 0:
                time.sleep(time_to_wait)
        self.prev_time = time.time()

        frame = self.picam.capture_array()
        # Ensure 3-channel RGB
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        elif frame.shape[2] == 3:
            frame = frame.astype(np.uint8)
        else:
            raise Exception(f"Unexpected frame shape: {frame.shape}")

        frame = cv2.flip(frame, 1)  # mirror horizontally for human view
        return frame

class ImageView():
    def __init__(self):
        self.done = False  # Flag to track exit status

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def show(self, img):
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        cv2.imshow('PARO Pose Tracking', img_bgr)

        delay_ms = 1  # 1ms (almost non-blocking)
        key = cv2.waitKey(delay_ms)
        if key == 27:  # ESC
            self.done = True

    def close(self):
        cv2.destroyAllWindows()

class PoseDetector():
    def __init__(self):
        self.pose = mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self.pose.close()

    def process(self, img):
        img.flags.writeable = False
        pose_res = self.pose.process(img)
        img.flags.writeable = True
        return pose_res

    def draw(self, img, pose_res):
        if pose_res.pose_landmarks:
            mp_drawing.draw_landmarks(
                img,
                pose_res.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style()
            )

if __name__ == '__main__':
    try:
        # Prepare output file for JSON logging
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        json_file = open(f"pose_{timestamp}.jsonl", "w")

        with Camera() as cam, ImageView() as view, PoseDetector() as pose:
            while True:
                frame_start_time = time.time()

                img = cam.getFrame()
                if img is None:
                    break

                pose_res = pose.process(img)
                # Log pose landmarks if detected
                if pose_res.pose_landmarks:
                    landmarks = [{
                        "id": i,
                        "x": lm.x,
                        "y": lm.y,
                        "z": lm.z,
                        "visibility": lm.visibility
                    } for i, lm in enumerate(pose_res.pose_landmarks.landmark)]

                    log = {
                        "timestamp": datetime.now().isoformat(),
                        "landmarks": landmarks
                    }
                    json_file.write(json.dumps(log) + "\n")
                    json_file.flush()

                # Draw pose landmarks
                pose.draw(img, pose_res)

                # FPS calculation (optional)
                fps = 1.0 / (time.time() - frame_start_time)
                cv2.putText(img, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

                view.show(img)
                if view.done:
                    break

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        err_string = f"{datetime.now()} - Exception: {e}, Line: {exc_tb.tb_lineno}\n"
        print(err_string)
        with open("pose_monitor_log.txt", "a") as log_file:
            log_file.write(err_string)
    finally:
        try:
            json_file.close()
        except:
            pass
        cv2.destroyAllWindows()


def run():
    import cv2, json, time, sys
    from datetime import datetime

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        json_file = open(f"pose_{timestamp}.jsonl", "w")

        with Camera() as cam, ImageView() as view, PoseDetector() as pose:
            while True:
                frame_start_time = time.time()
                img = cam.getFrame()
                if img is None:
                    break

                pose_res = pose.process(img)

                if pose_res.pose_landmarks:
                    landmarks = [{
                        "id": i,
                        "x": lm.x,
                        "y": lm.y,
                        "z": lm.z,
                        "visibility": lm.visibility
                    } for i, lm in enumerate(pose_res.pose_landmarks.landmark)]
                    log = {"timestamp": datetime.now().isoformat(), "landmarks": landmarks}
                    json_file.write(json.dumps(log) + "\n")
                    json_file.flush()

                pose.draw(img, pose_res)

                fps = 1.0 / (time.time() - frame_start_time)
                cv2.putText(img, f"FPS: {fps:.1f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

                view.show(img)
                if view.done:
                    break

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        err_string = f"{datetime.now()} - Exception: {e}, Line: {exc_tb.tb_lineno}\n"
        print(err_string)
        with open("pose_monitor_log.txt", "a") as log_file:
            log_file.write(err_string)
    finally:
        try:
            json_file.close()
        except:
            pass
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run()

