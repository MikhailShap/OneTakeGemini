import sounddevice as sd
import cv2
import subprocess
from PySide6.QtCore import QObject, Signal, QThread


class DeviceEnumerationWorker(QObject):
    """Background worker for device enumeration to avoid blocking UI"""
    screens_ready = Signal(list)  # List of screen info dicts
    mics_ready = Signal(list)     # List of mic names
    cameras_ready = Signal(list)  # List of camera dicts
    finished = Signal()

    def __init__(self):
        super().__init__()
        self._is_running = True

    def run(self):
        # Enumerate microphones (fast, ~10-50ms)
        mics = []
        if self._is_running:
            try:
                mics = DeviceManager.get_audio_input_devices()
            except Exception as e:
                print(f"Error enumerating mics: {e}")
        self.mics_ready.emit(mics)

        # Enumerate cameras (fast mode - trust FFmpeg list without OpenCV verification)
        cameras = []
        if self._is_running:
            try:
                cameras = DeviceManager.get_camera_devices_fast()
            except Exception as e:
                print(f"Error enumerating cameras: {e}")
        self.cameras_ready.emit(cameras)

        self.finished.emit()

    def stop(self):
        self._is_running = False


class DeviceManager:
    """Handles enumeration of audio and video devices."""
    
    @staticmethod
    def get_audio_input_devices():
        """Returns a list of audio input devices names."""
        devices = []
        try:
            # query_devices returns a list of dicts
            all_devices = sd.query_devices()
            # Filter for input devices (max_input_channels > 0)
            # We want unique names to avoid duplicates if possible, or just list them all
            # HostAPI 0 is usually MME on Windows, 1 is DirectSound, etc. 
            # We'll just list all unique input names for simplicity in this MVP
            seen_names = set()
            for d in all_devices:
                if d['max_input_channels'] > 0:
                    name = d['name']
                    if name not in seen_names:
                        devices.append(name)
                        seen_names.add(name)
        except Exception as e:
            print(f"Error querying audio devices: {e}")
            # Fallback
            devices = ["Default Microphone"]
        return devices

    @staticmethod
    def get_ffmpeg_devices():
        """
        Returns a dictionary of device names to FFmpeg alternative names (dshow).
        Example: {'Microphone (Realtek)': '@device_cm_{...}'}
        """
        devices = {}
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

            # Run ffmpeg to list devices
            cmd = [ffmpeg_exe, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')

            output = result.stderr

            # FFmpeg 7.x format: [dshow @ ...] "Device Name" (video/audio)
            # Then: [dshow @ ...]   Alternative name "..."
            last_name = None

            for line in output.split('\n'):
                line = line.strip()

                if not line.startswith('[dshow @'):
                    continue

                if 'Alternative name' in line:
                    if last_name:
                        # Extract alt name within quotes
                        start = line.find('"') + 1
                        end = line.rfind('"')
                        if start > 0 and end > start:
                            alt_name = line[start:end]
                            devices[last_name] = alt_name
                            last_name = None
                elif '(audio)' in line:
                    # Audio device - extract name
                    start = line.find('"') + 1
                    end = line.rfind('"')
                    if start > 0 and end > start:
                        name = line[start:end]
                        last_name = name

        except Exception as e:
            print(f"Error listing FFmpeg devices: {e}")

        return devices

    @staticmethod
    def get_ffmpeg_video_devices():
        """
        Returns a list of video device names in order found by DirectShow.
        """
        device_names = []
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

            # Use dummy file to trigger device listing
            cmd = [ffmpeg_exe, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]

            # Capture output. FFmpeg writes to stderr.
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            output = ""
            try:
                output = result.stderr.decode('utf-8', errors='ignore')
            except:
                output = result.stderr.decode('cp1251', errors='ignore')

            # FFmpeg 7.x format: [dshow @ ...] "Device Name" (video) or (audio)
            # Older format: DirectShow video devices: header then device names
            for line in output.split('\n'):
                line = line.strip()

                # Skip non-device lines
                if not line.startswith('[dshow @'):
                    continue

                # Skip "Alternative name" lines
                if "Alternative name" in line:
                    continue

                # Check if this is a video device (ends with "(video)")
                if "(video)" in line:
                    # Extract content between first and last quotes before (video)
                    start_quote = line.find('"')
                    end_quote = line.rfind('"')

                    if start_quote != -1 and end_quote > start_quote:
                        name = line[start_quote + 1:end_quote]
                        if name:
                            device_names.append(name)

        except Exception as e:
            print(f"Error listing FFmpeg video devices: {e}")

        return device_names

    @staticmethod
    def get_camera_devices_fast():
        """
        Returns cameras based on FFmpeg DirectShow enumeration only.
        Much faster than OpenCV verification (100ms vs 3-5s).
        Falls back to OpenCV scan if FFmpeg finds nothing.
        """
        available_cameras = []
        friendly_names = DeviceManager.get_ffmpeg_video_devices()
        print(f"FFmpeg found camera names (fast mode): {friendly_names}")

        if friendly_names:
            for i, name in enumerate(friendly_names):
                available_cameras.append({'index': i, 'name': name})
        else:
            # Fallback: FFmpeg didn't find cameras, try quick OpenCV scan
            print("FFmpeg found no cameras, trying OpenCV fallback...")
            for i in range(3):  # Check first 3 indices quickly
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        available_cameras.append({'index': i, 'name': f"Camera {i}"})
                        cap.release()
                except Exception:
                    pass

        return available_cameras

    @staticmethod
    def get_camera_devices():
        """
        Returns a list of available camera indices and friendly names.
        Uses OpenCV verification (slower but more accurate).
        """
        available_cameras = []

        # 1. Get friendly names from FFmpeg (DirectShow order usually matches OpenCV DSHOW order)
        friendly_names = DeviceManager.get_ffmpeg_video_devices()
        print(f"FFmpeg found camera names: {friendly_names}")

        # 2. Check indices with OpenCV
        print("Checking for cameras with optimized scan...")

        # Optimization: Only scan as many indices as we found devices + 1 (for safety)
        # If no devices found by ffmpeg, scan at least 3 indices just in case.
        scan_limit = max(len(friendly_names) + 1, 3)
        # Cap at 5 to avoid long hangs
        scan_limit = min(scan_limit, 5)

        for i in range(scan_limit):
            try:
                cap = None
                backend_name = "None"

                # 1. Try DSHOW
                try:
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if not cap.isOpened():
                        print(f"Index {i}: DSHOW failed to open.")
                        cap.release()
                        cap = None
                    else:
                        backend_name = "DSHOW"
                except Exception as e:
                    print(f"Index {i}: DSHOW exception: {e}")
                    if cap:
                        cap.release()
                    cap = None

                # 2. Try MSMF (Media Foundation) Explicitly
                if cap is None:
                    try:
                        print(f"Index {i}: Trying CAP_MSMF...")
                        cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
                        if not cap.isOpened():
                            print(f"Index {i}: MSMF failed to open.")
                            cap.release()
                            cap = None
                        else:
                            backend_name = "MSMF"
                    except Exception as e:
                        if cap:
                            cap.release()
                        cap = None

                # 3. Try ANY (Auto)
                if cap is None:
                    try:
                        print(f"Index {i}: Trying CAP_ANY...")
                        cap = cv2.VideoCapture(i, cv2.CAP_ANY)
                        if not cap.isOpened():
                            print(f"Index {i}: CAP_ANY failed to open.")
                            cap.release()
                            cap = None
                        else:
                            backend_name = "ANY"
                    except Exception as e:
                        if cap:
                            cap.release()
                        cap = None

                # Check if we have a valid capture
                if cap and cap.isOpened():
                    # Read a frame to verify
                    ret, _ = cap.read()
                    if ret:
                        name = f"Camera {i}"
                        if i < len(friendly_names):
                            name = friendly_names[i]

                        print(f"Found camera at index {i} using {backend_name}: {name}")
                        available_cameras.append({'index': i, 'name': name})
                    else:
                        print(f"Index {i}: Opened with {backend_name} but failed to read frame.")

                    cap.release()
                else:
                    print(f"Index {i}: No working backend found.")

            except Exception as e:
                print(f"Error checking camera {i}: {e}")
        return available_cameras

