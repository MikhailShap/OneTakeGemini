import sounddevice as sd
import numpy as np
from PySide6.QtCore import QThread, Signal, QObject

class AudioWorker(QObject):
    level_changed = Signal(float)  # 0.0 to 1.0
    finished = Signal()

    def __init__(self, device_name):
        super().__init__()
        self.device_name = device_name
        self.is_running = True

    def run(self):
        try:
            # Find device index by name
            device_index = None
            if self.device_name and self.device_name != "Default Microphone":
                devices = sd.query_devices()
                for i, d in enumerate(devices):
                    if d['name'] == self.device_name and d['max_input_channels'] > 0:
                        device_index = i
                        break
            
            # Callback for stream
            def callback(indata, frames, time, status):
                if status:
                    print(status)
                if self.is_running:
                    # Calculate RMS
                    volume_norm = 0
                    if indata.any():
                        volume_norm = np.linalg.norm(indata) * 10
                    self.level_changed.emit(min(1.0, volume_norm / 100)) # Normalize roughly

            with sd.InputStream(device=device_index, channels=1, callback=callback):
                while self.is_running:
                    sd.sleep(100)
        except Exception as e:
            print(f"Audio stream error: {e}")
        
        self.finished.emit()

    def stop(self):
        self.is_running = False

class AudioManager(QObject):
    level_ready = Signal(float)

    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None

    def start_monitoring(self, device_name):
        self.stop_monitoring()

        self.thread = QThread()
        self.worker = AudioWorker(device_name)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.level_changed.connect(self.level_ready)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def stop_monitoring(self):
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            if not self.thread.wait(3000):  # 3 second timeout
                print("Audio thread did not stop in time, terminating...")
                self.thread.terminate()
                self.thread.wait()
        self.worker = None
        self.thread = None
