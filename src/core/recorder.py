import subprocess
import os
import signal
from datetime import datetime
from src.utils.paths import get_output_dir

class Recorder:
    """
    Manages the recording process using FFmpeg.
    """
    def __init__(self):
        self.process = None
        self.output_file = None

    def start_recording(self, config):
        """
        Starts the recording with the given configuration.
        config: dict containing 'audio_device', 'screen_region', etc.
        """
        print(f"Starting recording with config: {config}")
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.output_file = os.path.join(get_output_dir(), f"recording_{timestamp}.mp4")
        
        # Build FFmpeg command
        # MVP: Record full desktop + specific audio device
        
        audio_device = config.get("audio_device")
        
        # Try to find ffmpeg
        ffmpeg_exe = "ffmpeg"
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass

        screen_geometry = config.get("screen_geometry")
        
        # Build command with proper A/V sync
        # Key: Use rtbufsize for video buffering, and sync audio with video timestamps
        cmd = [
            ffmpeg_exe,
        ]

        # Video input (gdigrab)
        if screen_geometry:
            x, y, w, h = screen_geometry
            cmd.extend([
                "-rtbufsize", "150M",
                "-f", "gdigrab",
                "-framerate", "30",
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}",
                "-show_region", "1",
                "-thread_queue_size", "512",
                "-i", "desktop"
            ])
        else:
            cmd.extend([
                "-rtbufsize", "150M",
                "-f", "gdigrab",
                "-framerate", "30",
                "-thread_queue_size", "512",
                "-i", "desktop"
            ])

        if audio_device and audio_device != "None" and audio_device != "No microphone found":
            # Resolve to FFmpeg alternative name if possible to avoid encoding issues
            try:
                from src.core.device_manager import DeviceManager
                ffmpeg_devices = DeviceManager.get_ffmpeg_devices()
                if audio_device in ffmpeg_devices:
                    print(f"Resolving '{audio_device}' to '{ffmpeg_devices[audio_device]}'")
                    audio_device = ffmpeg_devices[audio_device]
            except Exception as e:
                print(f"Error resolving device name: {e}")

            # Audio input
            cmd.extend([
                "-f", "dshow",
                "-thread_queue_size", "512",
                "-i", f"audio={audio_device}"
            ])
        
        # Encoding options
        # Optimization: Downscale to 1080p if source is larger to ensure smooth recording
        vf_filters = []
        if screen_geometry:
            w, h = screen_geometry[2], screen_geometry[3]
            if w > 1920 or h > 1080:
                print(f"Downscaling video from {w}x{h} to 1920x1080 for performance.")
                vf_filters.append("scale=1920:-2") # -2 keeps aspect ratio
        
        # Audio drift fix is already in -af, let's keep it.
        # We need to Combine -vf filters if any
        if vf_filters:
            cmd.extend(["-vf", ",".join(vf_filters)])

        # Check if audio is being recorded
        has_audio = audio_device and audio_device != "None" and audio_device != "No microphone found"

        # Map streams explicitly for proper sync
        if has_audio:
            cmd.extend(["-map", "0:v", "-map", "1:a"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-g", "30",  # Keyframe every 1 second
            "-r", "30",
            "-vsync", "cfr",  # Constant frame rate
            "-pix_fmt", "yuv420p",
        ])

        if has_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-ac", "2",
                "-af", "aresample=async=1000:min_hard_comp=0.100000:first_pts=0",
            ])
        else:
            cmd.extend([
                "-an",  # No audio
            ])

        cmd.extend([
            "-y",
            self.output_file
        ])
        
        print(f"Running command: {' '.join(cmd)}")
        
        # Start process without showing window (on Windows)
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
            return True, self.output_file
        except FileNotFoundError:
            print("FFmpeg not found!")
            return False, "FFmpeg executable not found in PATH."
        except Exception as e:
            print(f"Error starting recording: {e}")
            return False, str(e)

    def stop_recording(self):
        """Stops the recording gracefully."""
        if self.process:
            print("Stopping recording...")
            # Send 'q' to stdin to stop ffmpeg gracefully
            try:
                self.process.stdin.write(b'q')
                self.process.stdin.flush()
                # Wait for process to finish with longer timeout
                out, err = self.process.communicate(timeout=15)
                if err:
                    print(f"FFmpeg stderr: {err.decode('utf-8', errors='ignore')}")
            except subprocess.TimeoutExpired:
                print("FFmpeg timeout, killing...")
                self.process.kill()
                out, err = self.process.communicate()
                if err:
                    print(f"FFmpeg stderr: {err.decode('utf-8', errors='ignore')}")
            except Exception as e:
                print(f"Error stopping recording: {e}")
                self.process.kill()
                self.process.communicate()

            self.process = None

            # Apply faststart for quick playback (moves moov atom to beginning)
            if self.output_file and os.path.exists(self.output_file):
                self._apply_faststart()

            return self.output_file
        return None

    def _apply_faststart(self):
        """Re-encode with proper A/V sync and faststart for instant playback."""
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ffmpeg_exe = "ffmpeg"

        temp_file = self.output_file + ".tmp.mp4"

        # Re-encode to fix timestamps and sync audio/video properly
        # This ensures video starts at 0 and audio is synced
        cmd = [
            ffmpeg_exe,
            "-i", self.output_file,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-r", "30",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-af", "aresample=async=1:first_pts=0",  # Force audio to start at 0 and stay synced
            "-video_track_timescale", "30000",
            "-movflags", "+faststart",
            "-avoid_negative_ts", "make_zero",
            "-y",
            temp_file
        ]

        try:
            print("Re-encoding for proper A/V sync...")
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(cmd, capture_output=True, timeout=300, startupinfo=startupinfo)
            if result.returncode == 0 and os.path.exists(temp_file):
                os.replace(temp_file, self.output_file)
                print("Re-encoding completed successfully.")
            else:
                print(f"Re-encoding failed: {result.stderr.decode('utf-8', errors='ignore')}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        except Exception as e:
            print(f"Error re-encoding: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
