import cv2
import threading
from PySide6.QtCore import QThread, Signal, QObject, Qt
from PySide6.QtGui import QImage
import numpy as np


class CameraWorker(QObject):
    frame_captured = Signal(QImage)
    finished = Signal()

    def __init__(self, camera_index, width=None, height=None):
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.is_running = True
        # Frame throttling: skip new frames if previous not consumed
        self._frame_pending = False
        self._frame_lock = threading.Lock()

    def run(self):
        # Use CAP_DSHOW for consistency with DeviceManager and better Windows support
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"Could not open camera {self.camera_index} with DSHOW, trying CAP_ANY...")
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_ANY)

        if not cap.isOpened():
            print(f"Could not open camera {self.camera_index}")
            self.finished.emit()
            return

        while self.is_running:
            ret, frame = cap.read()
            if ret:
                # Skip frame if previous frame not yet consumed (prevents queue buildup)
                with self._frame_lock:
                    if self._frame_pending:
                        QThread.msleep(10)
                        continue

                # Resize in thread if requested (Performance Optimization)
                if self.width and self.height:
                    try:
                        frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
                    except Exception:
                        pass  # Ignore resize errors

                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

                with self._frame_lock:
                    self._frame_pending = True

                # Must copy, otherwise data is bound to local variable 'rgb_frame' which is garbage collected
                self.frame_captured.emit(qt_image.copy())
            else:
                break

            # Simple Frame Limiter (approx 30 FPS)
            QThread.msleep(33)

        cap.release()
        self.finished.emit()

    def mark_frame_consumed(self):
        """Called by UI after processing frame to allow next frame"""
        with self._frame_lock:
            self._frame_pending = False

    def stop(self):
        self.is_running = False

class CameraManager(QObject):
    frame_ready = Signal(QImage)

    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None

    def start_camera(self, index, width=None, height=None):
        self.stop_camera()  # Stop existing if any

        self.thread = QThread()
        self.worker = CameraWorker(index, width, height)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.frame_captured.connect(self._on_frame_captured)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _on_frame_captured(self, q_image):
        """Internal handler that forwards frame and marks as consumed"""
        self.frame_ready.emit(q_image)
        # Mark frame as consumed so worker can capture next frame
        if self.worker:
            self.worker.mark_frame_consumed()

    def stop_camera(self):
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            if not self.thread.wait(3000):  # 3 second timeout
                print("Camera thread did not stop in time, terminating...")
                self.thread.terminate()
                self.thread.wait()
        self.worker = None
        self.thread = None
