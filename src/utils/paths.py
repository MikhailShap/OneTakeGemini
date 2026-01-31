import os
import sys

def get_project_root():
    """Returns the root directory of the project."""
    # This assumes this file is in src/utils/
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
