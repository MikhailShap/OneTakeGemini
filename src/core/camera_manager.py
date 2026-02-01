import threading
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage
from src.utils import logger

# cv2 imported lazily in CameraWorker.run() to speed up app startup


class CameraWorker(QObject):
    frame_captured = Signal(QImage)
    finished = Signal()

    def __init__(self, camera_index, width=None, height=None):
        super().__init__()
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self._is_running = True
        self._frame_pending = False
        self._lock = threading.Lock()

    def run(self):
        # Lazy import cv2 to speed up app startup (~500-800ms saved)
        import cv2

        logger.debug(f"CameraWorker.run() starting for camera {self.camera_index}")
        cap = None

        try:
            # Try DSHOW first
            if self._is_running:
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)

            if cap and not cap.isOpened() and self._is_running:
                logger.warning(f"DSHOW failed for camera {self.camera_index}, trying MSMF...")
                cap.release()
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_MSMF)

            if not cap or not cap.isOpened():
                logger.error(f"Could not open camera {self.camera_index}")
                self.finished.emit()
                return

            if not self._is_running:
                cap.release()
                self.finished.emit()
                return

            logger.info(f"Camera {self.camera_index} opened")

            # Configure camera
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            while self._is_running:
                ret, frame = cap.read()
                if not ret:
                    if not self._is_running:
                        break
                    QThread.msleep(50)
                    continue

                with self._lock:
                    if self._frame_pending:
                        QThread.msleep(10)
                        continue

                if self.width and self.height:
                    try:
                        frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
                    except:
                        pass

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

                with self._lock:
                    self._frame_pending = True

                if self._is_running:
                    self.frame_captured.emit(img)

                QThread.msleep(33)

        except Exception as e:
            logger.error(f"CameraWorker error: {e}")
        finally:
            if cap:
                cap.release()
            logger.debug(f"CameraWorker.run() finished for camera {self.camera_index}")
            self.finished.emit()

    def mark_consumed(self):
        with self._lock:
            self._frame_pending = False

    def stop(self):
        logger.debug(f"CameraWorker.stop() called")
        self._is_running = False


class CameraManager(QObject):
    frame_ready = Signal(QImage)

    def __init__(self):
        super().__init__()
        self._thread = None
        self._worker = None
        self._lock = threading.Lock()

    def start_camera(self, index, width=None, height=None):
        logger.info(f"CameraManager.start_camera({index})")

        with self._lock:
            self._cleanup()

            self._thread = QThread()
            self._worker = CameraWorker(index, width, height)
            self._worker.moveToThread(self._thread)

            self._thread.started.connect(self._worker.run)
            self._worker.frame_captured.connect(self._on_frame)
            self._worker.finished.connect(self._on_finished)

            self._thread.start()
            logger.debug("Camera thread started")

    def _on_frame(self, img):
        self.frame_ready.emit(img)
        with self._lock:
            if self._worker:
                self._worker.mark_consumed()

    def _on_finished(self):
        logger.debug("CameraManager._on_finished()")
        # Don't cleanup here - it causes issues with signals during deletion

    def stop_camera(self):
        logger.debug("CameraManager.stop_camera()")
        with self._lock:
            self._cleanup()

    def _cleanup(self):
        """Internal cleanup - must be called with lock held"""
        if self._worker:
            try:
                self._worker.stop()
            except:
                pass

        if self._thread:
            try:
                if self._thread.isRunning():
                    self._thread.quit()
                    if not self._thread.wait(2000):
                        logger.warning("Thread timeout, terminating")
                        self._thread.terminate()
                        self._thread.wait(500)
            except RuntimeError:
                # Thread already deleted
                pass
            except:
                pass

        self._worker = None
        self._thread = None
        logger.debug("Camera cleanup done")
