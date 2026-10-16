import cv2
import time
import numpy as np
import json
from datetime import datetime
from picamera2 import Picamera2
from libcamera import controls
import mediapipe as mp
import sys
import os



mp_face_mesh = mp.solutions.face_mesh

# Eye landmarks for drawing (many points)
LEFT_EYE_IDX_DRAW = [33, 246, 161, 160, 159, 158, 157, 173,
                     133, 155, 154, 153, 145, 144, 163, 7]
RIGHT_EYE_IDX_DRAW = [362, 398, 384, 385, 386, 387, 388, 466,
                      263, 249, 390, 373, 374, 380, 381, 382]

# Eye landmarks for EAR (6 points)
LEFT_EYE_IDX_EAR = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX_EAR = [362, 385, 387, 263, 373, 380]

# Mouth outline (outer lip)
MOUTH_IDX = [
    61, 146, 91, 181, 84, 17, 314, 405, 321,
    375, 291, 308, 324, 318, 402, 317, 14,
    87, 178, 88, 95, 185, 40, 39, 37, 0, 267,
    269, 270, 409, 415, 310, 311, 312, 13,
    82, 81, 42, 183, 78, 61
]

def eye_aspect_ratio(eye):
    A = np.linalg.norm(eye[1] - eye[5])
    B = np.linalg.norm(eye[2] - eye[4])
    C = np.linalg.norm(eye[0] - eye[3])
    return (A + B) / (2.0 * C)

class Camera():
    def __init__(self, resolution=(640, 480), frame_rate=15, exposure=10000):
        self.resolution = resolution
        self.frame_rate = frame_rate
        self.exposure = exposure
        self.frame_time = 1 / frame_rate
        self.picam = None
        self.prev_time = None
        self.open()

    def __enter__(self): return self
    def __exit__(self, type, value, traceback): self.close()

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
            time.sleep(max(0, self.frame_time - (time.time() - self.prev_time)))
        self.prev_time = time.time()

        frame = self.picam.capture_array()
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        elif frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
        elif frame.shape[2] == 3:
            frame = frame.astype(np.uint8)
        else:
            raise Exception(f"Unexpected frame shape: {frame.shape}")
        return cv2.flip(frame, 1)

class ImageView():
    def __init__(self): self.done = False
    def __enter__(self): return self
    def __exit__(self, type, value, traceback): self.close()
    def show(self, img):
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        cv2.imshow('Mouth + Eye Monitor', img_bgr)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            self.done = True
    def close(self): cv2.destroyAllWindows()

if __name__ == '__main__':
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        json_file = open(f"mouth_eye_{timestamp}.jsonl", "w")

        with Camera() as cam, ImageView() as view, \
                mp_face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5) as face_mesh:

            while True:
                frame_start_time = time.time()  # For FPS

                img = cam.getFrame()
                results = face_mesh.process(img)

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        h, w, _ = img.shape

                        # --- Draw detailed eye points (green) ---
                        left_eye_draw = np.array([[face_landmarks.landmark[i].x * w,
                                                   face_landmarks.landmark[i].y * h] for i in LEFT_EYE_IDX_DRAW])
                        right_eye_draw = np.array([[face_landmarks.landmark[i].x * w,
                                                    face_landmarks.landmark[i].y * h] for i in RIGHT_EYE_IDX_DRAW])
                        for (x, y) in np.concatenate((left_eye_draw, right_eye_draw)):
                            cv2.circle(img, (int(x), int(y)), 2, (0, 255, 0), -1)

                        # --- EAR calculation (classic 6-point) for eyes closed notification only ---
                        left_eye_ear = np.array([[face_landmarks.landmark[i].x * w,
                                                  face_landmarks.landmark[i].y * h] for i in LEFT_EYE_IDX_EAR])
                        right_eye_ear = np.array([[face_landmarks.landmark[i].x * w,
                                                   face_landmarks.landmark[i].y * h] for i in RIGHT_EYE_IDX_EAR])
                        left_ear = eye_aspect_ratio(left_eye_ear)
                        right_ear = eye_aspect_ratio(right_eye_ear)
                        ear = (left_ear + right_ear) / 2.0

                        # --- Eyes closed notification only ---
                        if ear < 0.21:
                            cv2.putText(img, "Eyes Closed!", (10, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                        # --- Mouth points as yellow dots ---
                        mouth = np.array([[face_landmarks.landmark[i].x * w,
                                           face_landmarks.landmark[i].y * h] for i in MOUTH_IDX])
                        for (x, y) in mouth:
                            cv2.circle(img, (int(x), int(y)), 2, (0, 255, 255), -1)

                        # --- Log to JSONL ---
                        mouth_points = [{"x": float(face_landmarks.landmark[i].x),
                                         "y": float(face_landmarks.landmark[i].y)} for i in MOUTH_IDX]
                        eye_points = [{"x": float(face_landmarks.landmark[i].x),
                                       "y": float(face_landmarks.landmark[i].y)} for i in (LEFT_EYE_IDX_DRAW + RIGHT_EYE_IDX_DRAW)]
                        log = {
                            "timestamp": datetime.now().isoformat(),
                            "eyes_closed": bool(ear < 0.21),
                            "mouth_points": mouth_points,
                            "eye_points": eye_points
                        }
                        json_file.write(json.dumps(log) + "\n")
                        json_file.flush()

                # --- FPS display ---
                fps = 1.0 / (time.time() - frame_start_time)
                cv2.putText(img, f"FPS: {fps:.1f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                view.show(img)
                if view.done:
                    break

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        err_string = f"{datetime.now()} - Exception: {e}, Line: {exc_tb.tb_lineno}\n"
        print(err_string)
        with open("mouth_eye_log.txt", "a") as log_file:
            log_file.write(err_string)
    finally:
        try:
            json_file.close()
        except:
            pass
        cv2.destroyAllWindows()

def run():
    import cv2, time, json, sys
    from datetime import datetime
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        json_file = open(f"mouth_eye_{timestamp}.jsonl", "w")

        with Camera() as cam, ImageView() as view, \
                mp_face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5) as face_mesh:

            while True:
                frame_start_time = time.time()
                img = cam.getFrame()
                results = face_mesh.process(img)

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        h, w, _ = img.shape

                        # --- Draw detailed eye points ---
                        left_eye_draw = np.array([[face_landmarks.landmark[i].x * w,
                                                   face_landmarks.landmark[i].y * h] for i in LEFT_EYE_IDX_DRAW])
                        right_eye_draw = np.array([[face_landmarks.landmark[i].x * w,
                                                    face_landmarks.landmark[i].y * h] for i in RIGHT_EYE_IDX_DRAW])
                        for (x, y) in np.concatenate((left_eye_draw, right_eye_draw)):
                            cv2.circle(img, (int(x), int(y)), 2, (0, 255, 0), -1)

                        # --- EAR for eyes closed notification ---
                        left_eye_ear = np.array([[face_landmarks.landmark[i].x * w,
                                                  face_landmarks.landmark[i].y * h] for i in LEFT_EYE_IDX_EAR])
                        right_eye_ear = np.array([[face_landmarks.landmark[i].x * w,
                                                   face_landmarks.landmark[i].y * h] for i in RIGHT_EYE_IDX_EAR])
                        left_ear = eye_aspect_ratio(left_eye_ear)
                        right_ear = eye_aspect_ratio(right_eye_ear)
                        ear = (left_ear + right_ear) / 2.0
                        if ear < 0.21:
                            cv2.putText(img, "Eyes Closed!", (10, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                        # --- Mouth points ---
                        mouth = np.array([[face_landmarks.landmark[i].x * w,
                                           face_landmarks.landmark[i].y * h] for i in MOUTH_IDX])
                        for (x, y) in mouth:
                            cv2.circle(img, (int(x), int(y)), 2, (0, 255, 255), -1)

                        # --- Log to JSONL ---
                        mouth_points = [{"x": float(face_landmarks.landmark[i].x),
                                         "y": float(face_landmarks.landmark[i].y)} for i in MOUTH_IDX]
                        eye_points = [{"x": float(face_landmarks.landmark[i].x),
                                       "y": float(face_landmarks.landmark[i].y)} for i in (LEFT_EYE_IDX_DRAW + RIGHT_EYE_IDX_DRAW)]
                        log = {
                            "timestamp": datetime.now().isoformat(),
                            "eyes_closed": bool(ear < 0.21),
                            "mouth_points": mouth_points,
                            "eye_points": eye_points
                        }
                        json_file.write(json.dumps(log) + "\n")
                        json_file.flush()

                # --- FPS display ---
                fps = 1.0 / (time.time() - frame_start_time)
                cv2.putText(img, f"FPS: {fps:.1f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                view.show(img)
                if view.done:
                    break

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        err_string = f"{datetime.now()} - Exception: {e}, Line: {exc_tb.tb_lineno}\n"
        print(err_string)
        with open("mouth_eye_log.txt", "a") as log_file:
            log_file.write(err_string)
    finally:
        try: json_file.close()
        except: pass
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
