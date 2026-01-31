import json
import os
from PySide6.QtCore import QTimer
from src.utils.paths import get_project_root

CONFIG_FILE = os.path.join(get_project_root(), "config.json")


class ConfigManager:
    _instance = None
    _config = {}
    _dirty = False
    _save_timer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.load_config()
            cls._instance._setup_save_timer()
        return cls._instance

    def _setup_save_timer(self):
        """Setup debounced save timer"""
        self._save_timer = QTimer()
        self._save_timer.timeout.connect(self._flush_if_dirty)
        self._save_timer.start(2000)  # Check every 2 seconds

    def _flush_if_dirty(self):
        """Save config if there are pending changes"""
        if self._dirty:
            self._do_save()
            self._dirty = False

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self._config = json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
                self._config = {}
        else:
            self._config = {}

    def _do_save(self):
        """Internal save method"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def save_config(self):
        """Immediate save (for shutdown or explicit save)"""
        self._do_save()
        self._dirty = False

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self._dirty = True  # Mark dirty, don't save immediately (debounced)
