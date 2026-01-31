import subprocess
import os
from datetime import datetime
from src.utils.paths import get_output_dir


class Recorder:
    """
    Manages the recording process using FFmpeg.
    """
    def __init__(self):
        self.process = None
        self.output_file = None
        self._temp_file = None

    def start_recording(self, config):
        """
        Starts the recording with the given configuration.
        """
        print(f"Starting recording with config: {config}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._temp_file = os.path.join(get_output_dir(), f"recording_{timestamp}_temp.mp4")
        self.output_file = os.path.join(get_output_dir(), f"recording_{timestamp}.mp4")

        audio_device = config.get("audio_device")

        ffmpeg_exe = "ffmpeg"
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass

        screen_geometry = config.get("screen_geometry")
        # Check for valid audio device (not scanning placeholder)
        has_audio = (audio_device and
                     audio_device != "None" and
                     audio_device != "No microphone found" and
                     "Сканирование" not in audio_device)
        self._has_audio = has_audio  # Store for later use

        cmd = [ffmpeg_exe]

        # Video input - 25 fps balance between smoothness and quality
        cmd.extend([
            "-f", "gdigrab",
            "-framerate", "25",
        ])

        if screen_geometry:
            x, y, w, h = screen_geometry
            cmd.extend([
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}",
            ])

        cmd.extend(["-i", "desktop"])

        # Audio input
        if has_audio:
            try:
                from src.core.device_manager import DeviceManager
                ffmpeg_devices = DeviceManager.get_ffmpeg_devices()
                print(f"FFmpeg audio devices: {ffmpeg_devices}")
                print(f"Looking for audio device: {audio_device}")

                # Попытка найти устройство
                resolved_device = None

                # 1. Точное совпадение
                if audio_device in ffmpeg_devices:
                    resolved_device = ffmpeg_devices[audio_device]
                    print(f"Found exact match: {resolved_device}")
                else:
                    # 2. Частичное совпадение (имя из sounddevice может быть обрезано)
                    for ffmpeg_name, alt_name in ffmpeg_devices.items():
                        if audio_device in ffmpeg_name or ffmpeg_name in audio_device:
                            resolved_device = alt_name
                            print(f"Found partial match: {ffmpeg_name} -> {alt_name}")
                            break

                # 3. Если найдено — использовать
                if resolved_device:
                    audio_device = resolved_device
                else:
                    # 4. Fallback: записать без аудио
                    print(f"Warning: Audio device '{audio_device}' not found in FFmpeg. Recording without audio.")
                    has_audio = False
                    self._has_audio = False
            except Exception as e:
                print(f"Error resolving audio device: {e}")
                has_audio = False
                self._has_audio = False

        if has_audio:
            cmd.extend([
                "-f", "dshow",
                "-i", f"audio={audio_device}"
            ])

        # Scale to 1080p for good quality
        cmd.extend(["-vf", "scale=1920:1080"])

        # Better quality encoding
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
        ])

        if has_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
            ])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-y", self._temp_file])

        print(f"Running command: {' '.join(cmd)}")

        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )

            # Wait a moment and check if process started successfully
            import time
            time.sleep(0.5)
            if self.process.poll() is not None:
                # Process already terminated - get error
                _, stderr = self.process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore')
                print(f"FFmpeg failed to start: {error_msg}")
                return False, f"FFmpeg error: {error_msg[:200]}"

            print("Recording started!")
            return True, self.output_file
        except FileNotFoundError:
            return False, "FFmpeg not found."
        except Exception as e:
            return False, str(e)

    def stop_recording(self):
        """Stops the recording gracefully."""
        if self.process:
            print("Stopping recording...")
            try:
                # Check if process is still running
                if self.process.poll() is None:
                    self.process.stdin.write(b'q')
                    self.process.stdin.flush()
                self.process.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.communicate()
            except (OSError, BrokenPipeError):
                # Process already terminated
                try:
                    self.process.communicate(timeout=5)
                except:
                    pass
            except Exception as e:
                print(f"Error stopping: {e}")
                try:
                    self.process.kill()
                    self.process.communicate()
                except:
                    pass

            self.process = None

            # Check if temp file was created
            if self._temp_file and os.path.exists(self._temp_file):
                # Fix audio sync if audio was recorded
                if getattr(self, '_has_audio', False):
                    self._fix_audio_sync()
                else:
                    # No audio - just rename temp to output
                    try:
                        if os.path.exists(self.output_file):
                            os.remove(self.output_file)
                        os.rename(self._temp_file, self.output_file)
                        print("Recording saved (no audio).")
                    except Exception as e:
                        print(f"Error saving file: {e}")
            else:
                print(f"Error: Recording file not created at {self._temp_file}")
                return None

            return self.output_file
        return None

    def _fix_audio_sync(self):
        """Shift audio to sync with video."""
        ffmpeg_exe = "ffmpeg"
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass

        # Shift audio 180ms later to compensate for video capture delay
        cmd = [
            ffmpeg_exe,
            "-i", self._temp_file,
            "-itsoffset", "0.18",  # Delay audio by 180ms
            "-i", self._temp_file,
            "-map", "0:v",
            "-map", "1:a",
            "-c", "copy",
            "-movflags", "+faststart",
            "-y",
            self.output_file
        ]

        try:
            print("Fixing audio sync...")
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(cmd, capture_output=True, timeout=60, startupinfo=startupinfo)

            if result.returncode == 0 and os.path.exists(self.output_file):
                try:
                    os.remove(self._temp_file)
                except:
                    pass
                print("Audio sync fixed.")
            else:
                # Fallback: use original file
                print(f"Audio sync failed, using original file. Error: {result.stderr.decode('utf-8', errors='ignore')}")
                try:
                    if os.path.exists(self.output_file):
                        os.remove(self.output_file)
                    os.rename(self._temp_file, self.output_file)
                except Exception as e:
                    print(f"Error renaming file: {e}")
        except Exception as e:
            print(f"Error fixing sync: {e}")
            try:
                os.rename(self._temp_file, self.output_file)
            except:
                pass
