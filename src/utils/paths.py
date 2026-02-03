import os
import sys

def get_project_root():
    """Returns the root directory of the project."""
    # Check if running as PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running as exe - use directory containing the exe
        return os.path.dirname(sys.executable)
    else:
        # Running as script - this file is in src/utils/
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_ffmpeg_path():
    """Returns path to ffmpeg executable."""
    # 1. Check next to exe (for frozen app)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        ffmpeg_path = os.path.join(exe_dir, 'ffmpeg.exe')
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path

        # 2. Check in _MEIPASS (PyInstaller temp directory)
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            ffmpeg_path = os.path.join(meipass, 'ffmpeg.exe')
            if os.path.exists(ffmpeg_path):
                return ffmpeg_path

    # 3. Try imageio_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    # 4. Fallback to system ffmpeg
    return "ffmpeg"

def get_output_dir():
    """Returns the directory where recordings are saved."""
    root = get_project_root()
    output_dir = os.path.join(root, "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def get_logs_dir():
    """Returns the directory where logs are saved."""
    root = get_project_root()
    logs_dir = os.path.join(root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir
