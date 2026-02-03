import subprocess
import os
import time
from datetime import datetime
from src.utils.paths import get_output_dir, get_ffmpeg_path
from src.utils import logger


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
        start_time = time.time()
        logger.info(f"start_recording() called with config: {config}")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._temp_file = os.path.join(get_output_dir(), f"recording_{timestamp}_temp.mp4")
        self.output_file = os.path.join(get_output_dir(), f"recording_{timestamp}.mp4")

        audio_device = config.get("audio_device")

        ffmpeg_exe = get_ffmpeg_path()

        screen_geometry = config.get("screen_geometry")
        # Check for valid audio device (not scanning placeholder)
        has_audio = (audio_device and
                     audio_device != "None" and
                     audio_device != "No microphone found" and
                     "Сканирование" not in audio_device)
        self._has_audio = has_audio  # Store for later use

        cmd = [ffmpeg_exe]

        # Video input - 30 fps for smooth playback (same as camera)
        cmd.extend([
            "-f", "gdigrab",
            "-framerate", "30",
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
                logger.debug(f"FFmpeg audio devices: {ffmpeg_devices}")
                logger.debug(f"Looking for audio device: {audio_device}")

                # Попытка найти устройство
                resolved_device = None

                # 1. Точное совпадение
                if audio_device in ffmpeg_devices:
                    resolved_device = ffmpeg_devices[audio_device]
                    logger.debug(f"Found exact match: {resolved_device}")
                else:
                    # 2. Частичное совпадение (имя из sounddevice может быть обрезано)
                    for ffmpeg_name, alt_name in ffmpeg_devices.items():
                        if audio_device in ffmpeg_name or ffmpeg_name in audio_device:
                            resolved_device = alt_name
                            logger.debug(f"Found partial match: {ffmpeg_name} -> {alt_name}")
                            break

                # 3. Если найдено — использовать
                if resolved_device:
                    audio_device = resolved_device
                else:
                    # 4. Fallback: записать без аудио
                    logger.warning(f"Audio device '{audio_device}' not found in FFmpeg. Recording without audio.")
                    has_audio = False
                    self._has_audio = False
            except Exception as e:
                logger.error(f"Error resolving audio device: {e}")
                has_audio = False
                self._has_audio = False

        if has_audio:
            cmd.extend([
                "-f", "dshow",
                "-i", f"audio={audio_device}"
            ])

        # Scale to 1080p for good quality
        cmd.extend(["-vf", "scale=1920:1080"])

        # Better quality encoding with constant frame rate
        # -g 30: keyframe every 1 second (at 30fps) - prevents data loss on stop
        # -flush_packets 1: flush data to disk immediately - prevents buffer loss
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",   # Better quality than ultrafast
            "-crf", "20",            # Better quality (lower = better)
            "-pix_fmt", "yuv420p",
            "-g", "30",              # Keyframe every 30 frames (1 sec) - critical for data safety
            "-flush_packets", "1",   # Flush to disk immediately
            "-r", "30",              # Fixed output FPS
            "-vsync", "cfr",         # Constant frame rate for smooth playback
        ])

        if has_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
            ])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-y", self._temp_file])

        logger.info(f"FFmpeg command: {' '.join(cmd)}")

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
            time.sleep(0.5)
            if self.process.poll() is not None:
                # Process already terminated - get error
                _, stderr = self.process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg failed to start: {error_msg}")
                return False, f"FFmpeg error: {error_msg[:200]}"

            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Recording started successfully in {elapsed:.0f}ms")
            return True, self.output_file
        except FileNotFoundError:
            logger.error("FFmpeg executable not found")
            return False, "FFmpeg not found."
        except Exception as e:
            logger.exception(f"Exception starting recording: {e}")
            return False, str(e)

    def stop_recording(self):
        """Stops the recording gracefully."""
        if self.process:
            logger.info("stop_recording() called, stopping FFmpeg...")
            try:
                # Check if process is still running
                if self.process.poll() is None:
                    self.process.stdin.write(b'q')
                    self.process.stdin.flush()
                    logger.debug("Sent 'q' to FFmpeg stdin")
                self.process.communicate(timeout=15)
                logger.debug("FFmpeg process terminated")
            except subprocess.TimeoutExpired:
                logger.warning("FFmpeg did not stop in 15s, killing...")
                self.process.kill()
                self.process.communicate()
            except (OSError, BrokenPipeError):
                # Process already terminated
                logger.debug("FFmpeg process already terminated")
                try:
                    self.process.communicate(timeout=5)
                except:
                    pass
            except Exception as e:
                logger.error(f"Error stopping FFmpeg: {e}")
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
                        logger.info(f"Recording saved (no audio): {self.output_file}")
                    except Exception as e:
                        logger.error(f"Error saving file: {e}")
            else:
                logger.error(f"Recording file not created at {self._temp_file}")
                return None

            return self.output_file
        return None

    def _fix_audio_sync(self):
        """Shift audio to sync with video."""
        logger.debug("_fix_audio_sync() started")
        ffmpeg_exe = get_ffmpeg_path()

        # Shift audio 250ms later to compensate for video capture delay
        cmd = [
            ffmpeg_exe,
            "-i", self._temp_file,
            "-itsoffset", "0.25",  # Delay audio by 250ms
            "-i", self._temp_file,
            "-map", "0:v",         # Video from first input (not delayed)
            "-map", "1:a",         # Audio from second input (delayed)
            "-c", "copy",
            "-movflags", "+faststart",
            "-y",
            self.output_file
        ]

        try:
            logger.debug(f"Audio sync command: {' '.join(cmd)}")
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
                logger.info(f"Audio sync fixed, saved: {self.output_file}")
            else:
                # Fallback: use original file
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                logger.warning(f"Audio sync failed, using original file. Error: {error_msg}")
                try:
                    if os.path.exists(self.output_file):
                        os.remove(self.output_file)
                    os.rename(self._temp_file, self.output_file)
                except Exception as e:
                    logger.error(f"Error renaming file: {e}")
        except Exception as e:
            logger.error(f"Error fixing sync: {e}")
            try:
                os.rename(self._temp_file, self.output_file)
            except:
                pass
