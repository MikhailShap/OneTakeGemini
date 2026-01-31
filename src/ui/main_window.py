import os
from PySide6.QtWidgets import QMainWindow, QStackedWidget
from src.ui.library_view import LibraryView
from src.ui.preparation_view import PreparationView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OneTake")
        self.setFixedSize(750, 600) # Wider to fit camera preview
        
        # Apply Theme
        from src.ui.styles import MAIN_STYLE
        self.setStyleSheet(MAIN_STYLE)
        
        # Apply Windows Dark Title Bar
        try:
            import ctypes
            from ctypes import wintypes
            
            # Key: DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ctypes.windll.user32.GetParent
            hwnd = int(self.winId())
            
            # Set the attribute
            rendering_policy = wintypes.BOOL(True)
            set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(rendering_policy), ctypes.sizeof(rendering_policy))
            
            # Trigger a repaint (sometimes needed)
            self.repaint()
        except Exception as e:
            print(f"Failed to set dark title bar: {e}")
        
        # Central Stacked Widget for navigation
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # Initialize Views
        self.library_view = LibraryView()
        self.preparation_view = PreparationView()
        
        # Add Views to Stack
        self.stack.addWidget(self.library_view)      # Index 0
        self.stack.addWidget(self.preparation_view)  # Index 1
        
        # Connect Signals
        self.library_view.start_new_recording_requested.connect(self.show_preparation)
        self.preparation_view.back_requested.connect(self.show_library)
        self.preparation_view.start_recording_requested.connect(self.start_recording)
        
        self.recorder = None
        self.overlay = None
        self._recording_finalized = False  # Prevent double start race condition

    def show_preparation(self):
        self.stack.setCurrentIndex(1)
        
    def show_library(self):
        self.stack.setCurrentIndex(0)

    def start_recording(self):
        # Reset finalization flag for new recording
        self._recording_finalized = False

        # 1. Gather config from PreparationView
        screen_geom = self.preparation_view.screen_combo.currentData()
        self.pending_config = {
            "audio_device": self.preparation_view.mic_combo.currentText(),
            "camera_index": self.preparation_view.camera_combo.currentData(),
            "camera_shape": self.preparation_view.shape_combo.currentData(),
            "screen_geometry": (screen_geom.x(), screen_geom.y(), screen_geom.width(), screen_geom.height()) if screen_geom else None
        }
        
        # 2. Capture Last Frame for seamless transition
        last_frame = self.preparation_view.get_current_frame()

        # 3. Stop Preview
        self.preparation_view.stop_preview()

        # 4. Minimize Main Window
        self.showMinimized()
        
        # 5. Show Overlay and wait for it to be ready
        from src.ui.recorder_overlay import RecorderOverlay
        
        camera_idx = self.pending_config["camera_index"]
        shape = self.pending_config["camera_shape"]
        
        if camera_idx < 0:
            # If no camera, use placeholder index -1
            camera_idx = -1
            
        self.recorder_overlay = RecorderOverlay(camera_idx, shape=shape, initial_frame=last_frame)
        self.recorder_overlay.camera_ready.connect(self.finalize_start_recording)
        
        # 6. Show Control Panel
        from src.ui.recording_control_panel import RecordingControlPanel
        self.control_panel = RecordingControlPanel()
        self.control_panel.stop_requested.connect(self.stop_recording)
        self.control_panel.cancel_requested.connect(self.cancel_recording)
        self.control_panel.restart_requested.connect(self.restart_recording)
        
        # Position Panel at top center of the RECORDING screen
        from PySide6.QtGui import QGuiApplication
        screens = QGuiApplication.screens()
        # Find screen matching config geometry
        target_screen = screens[0]
        if self.pending_config["screen_geometry"]:
            sx, sy, sw, sh = self.pending_config["screen_geometry"]
            for screen in screens:
                g = screen.geometry()
                if g.x() == sx and g.y() == sy:
                    target_screen = screen
                    break
        
        # Center panel horizontally on target screen, top 5px
        sg = target_screen.geometry()
        panel_x = sg.x() + (sg.width() - self.control_panel.width()) // 2
        panel_y = sg.y() + 5 
        self.control_panel.move(panel_x, panel_y)
        
        self.recorder_overlay.show()
        self.control_panel.show()
        
        # Safety timeout: If camera doesn't start in 3 seconds, start recording anyway
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, self.force_finalize_recording)
        
    def force_finalize_recording(self):
        # Only start if we haven't already finalized
        if not self._recording_finalized:
            print("Camera start timed out, forcing recording start...")
            self.finalize_start_recording()

    def finalize_start_recording(self):
        # Avoid double start with explicit flag (safer than checking self.recorder)
        if self._recording_finalized:
            return
        self._recording_finalized = True
        # Called when overlay camera is ready (or immediately if no camera)
        config = getattr(self, 'pending_config', {})
        
        from src.core.recorder import Recorder
        self.recorder = Recorder()
        success, message = self.recorder.start_recording(config)
        
        if not success:
            print(f"Failed to start: {message}")
            self.stop_recording_cleanup()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to start recording:\n{message}")
        else:
            print("Recording started!")

    def stop_recording(self):
        """Stops recording and returns to Library."""
        self.stop_recording_cleanup()
        
        output_file = None
        if self.recorder:
             output_file = self.recorder.stop_recording()
             self.recorder = None

        # Show Library
        self.stack.setCurrentIndex(0)
        self.showNormal()
        
        # Refresh Library
        if output_file:
             self.library_view.refresh_list()

    def cancel_recording(self):
        """Stops recording and deletes the file."""
        self.stop_recording_cleanup()
        output_file = None
        if self.recorder:
             output_file = self.recorder.stop_recording()
             self.recorder = None
        
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
                print(f"Recording cancelled, deleted: {output_file}")
            except Exception as e:
                print(f"Error deleting cancelled file: {e}")
        
        # Show Preparation (User likely wants to try again)
        self.stack.setCurrentIndex(1) # Preparation
        self.showNormal()

    def restart_recording(self):
        """Stops current, deletes it, and starts fresh immediately."""
        self.stop_recording_cleanup()
        output_file = None
        if self.recorder:
             output_file = self.recorder.stop_recording()
             self.recorder = None
        
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except: pass
            
        # Start again with SAME config
        # We need to re-initiate the start sequence
        # Brief delay to ensure ffmpeg closes
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self.start_recording)

    def stop_recording_cleanup(self):
        """Closes overlays and panels."""
        if hasattr(self, 'recorder_overlay') and self.recorder_overlay:
            self.recorder_overlay.close()
            self.recorder_overlay = None
            
        if hasattr(self, 'control_panel') and self.control_panel:
            self.control_panel.close()
            self.control_panel = None
