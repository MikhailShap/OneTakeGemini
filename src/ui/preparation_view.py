import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QGroupBox, QSpacerItem, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Signal, Qt, QTimer, QThread
from PySide6.QtGui import QPixmap, QImage, QPainter, QPainterPath, QColor
from src.utils import logger

class PreparationView(QWidget):
    # Signals
    back_requested = Signal()
    start_recording_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header Area
        header_layout = QHBoxLayout()
        back_btn = QPushButton("Назад")
        back_btn.setFixedSize(80, 40)
        back_btn.setProperty("class", "secondary")
        back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(back_btn)
        
        header = QLabel("Подготовка")
        header.setProperty("class", "header")
        header.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(header)
        
        # Balance the header
        spacer = QWidget()
        spacer.setFixedSize(80, 40)
        header_layout.addWidget(spacer)
        
        layout.addLayout(header_layout)
        
        # Content Area (Split Left/Right)
        content_layout = QHBoxLayout()
        layout.addLayout(content_layout)
        
        # Left Side: Settings
        settings_container = QWidget()
        settings_layout = QVBoxLayout(settings_container)
        settings_layout.setSpacing(15)
        content_layout.addWidget(settings_container, 1) # Stretch factor 1
        
        # Screen Selection
        settings_layout.addWidget(QLabel("Выберите экран:"))
        self.screen_combo = QComboBox()
        # Screens are populated in refresh_devices
        settings_layout.addWidget(self.screen_combo)

        # Camera Device
        settings_layout.addWidget(QLabel("Камера:"))
        self.camera_combo = QComboBox()
        settings_layout.addWidget(self.camera_combo)
        
        # Camera Shape
        settings_layout.addWidget(QLabel("Форма камеры:"))
        self.shape_combo = QComboBox()
        self.shape_combo.addItem("Прямоугольник", "Rectangle")
        self.shape_combo.addItem("Круг", "Circle")
        settings_layout.addWidget(self.shape_combo)
        
        # Microphone
        settings_layout.addWidget(QLabel("Микрофон:"))
        self.mic_combo = QComboBox()
        settings_layout.addWidget(self.mic_combo)
        
        # Audio Level
        self.audio_level = QProgressBar()
        self.audio_level.setRange(0, 100)
        self.audio_level.setTextVisible(False)
        self.audio_level.setFixedHeight(8)
        settings_layout.addWidget(self.audio_level)
        
        settings_layout.addStretch() # Push settings up
        
        # Right Side: Preview
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0,0,0,0)
        content_layout.addWidget(preview_container, 2) # Stretch factor 2
        
        preview_label_title = QLabel("Предпросмотр")
        preview_label_title.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(preview_label_title)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: transparent; border: none;")
        self.preview_label.setMinimumSize(480, 270)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview_label)
        
        # Start Button
        self.start_btn = QPushButton("Начать запись")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #6200EE; 
                color: white; 
                font-size: 18px; 
                font-weight: bold; 
                border-radius: 25px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        self.start_btn.clicked.connect(self.start_recording_requested.emit)
        layout.addWidget(self.start_btn)
        
        self.camera_manager = None
        self.audio_manager = None

        # Performance optimization: cache for frame rendering
        self._cached_clip_path = None
        self._cached_size = None
        self._cached_shape = None
        self._cached_circle_rect = None
        self._last_frame_time = 0
        self._min_frame_interval = 33  # ~30 FPS cap in milliseconds

        # Device enumeration caching
        self._cached_cameras = None
        self._cached_mics = None
        self._cache_time = 0
        self._cache_duration = 30  # seconds
        self._enum_thread = None
        self._enum_worker = None

        # Connect Combo Changes
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)

        # Flag to track if view has been shown
        self._initialized = False
        # DON'T call refresh_devices here - wait for showEvent
        # This speeds up app startup significantly

    def refresh_devices(self):
        logger.debug("PreparationView.refresh_devices() called")
        current_time = time.time()

        # Check if we have valid cached devices
        if (self._cached_cameras is not None and
            self._cached_mics is not None and
            current_time - self._cache_time < self._cache_duration):
            logger.debug("Using cached device data")
            self._populate_from_cache()
            return

        # Start async enumeration
        logger.debug("Starting async device enumeration")
        self._start_async_enumeration()

    def _start_async_enumeration(self):
        """Start background device enumeration"""
        from src.core.device_manager import DeviceEnumerationWorker

        # Populate screens immediately (fast, no blocking)
        self._populate_screens()

        # Show loading state for cameras
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItem("Сканирование камер...", -1)
        self.camera_combo.setEnabled(False)
        self.camera_combo.blockSignals(False)

        # Show loading state for mics
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.addItem("Сканирование микрофонов...", None)
        self.mic_combo.setEnabled(False)
        self.mic_combo.blockSignals(False)

        # Clean up previous thread if any
        try:
            if self._enum_thread is not None and self._enum_thread.isRunning():
                self._enum_worker.stop()
                self._enum_thread.quit()
                self._enum_thread.wait(1000)
        except RuntimeError:
            # Thread was already deleted
            pass

        self._enum_thread = QThread()
        self._enum_worker = DeviceEnumerationWorker()
        self._enum_worker.moveToThread(self._enum_thread)

        self._enum_thread.started.connect(self._enum_worker.run)
        self._enum_worker.mics_ready.connect(self._on_mics_ready)
        self._enum_worker.cameras_ready.connect(self._on_cameras_ready)
        self._enum_worker.finished.connect(self._enum_thread.quit)
        self._enum_worker.finished.connect(self._enum_worker.deleteLater)
        self._enum_thread.finished.connect(self._on_enum_thread_finished)

        self._enum_thread.start()

    def _on_enum_thread_finished(self):
        """Clean up thread reference when finished"""
        self._enum_thread = None
        self._enum_worker = None

    def _populate_screens(self):
        """Populate screens combo (fast, runs on main thread)"""
        from PySide6.QtGui import QGuiApplication

        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()

        screens = QGuiApplication.screens()
        for i, screen in enumerate(screens):
            geom = screen.geometry()
            self.screen_combo.addItem(f"Display {i+1} ({geom.width()}x{geom.height()})", geom)

        self.screen_combo.blockSignals(False)

    def _on_mics_ready(self, mics):
        """Called when microphones enumeration completes"""
        logger.debug(f"_on_mics_ready: received {len(mics)} microphones")
        from src.core.config_manager import ConfigManager
        config = ConfigManager()

        self._cached_mics = mics
        self._cache_time = time.time()

        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.setEnabled(True)

        if mics:
            self.mic_combo.addItems(mics)
            saved_mic = config.get("last_mic")
            if saved_mic and saved_mic in mics:
                self.mic_combo.setCurrentText(saved_mic)
        else:
            self.mic_combo.addItem("No microphone found")

        self.mic_combo.blockSignals(False)

        if self.mic_combo.count() > 0:
            self.on_mic_changed(self.mic_combo.currentIndex())

    def _on_cameras_ready(self, cams):
        """Called when camera enumeration completes"""
        logger.debug(f"_on_cameras_ready: received {len(cams)} cameras")
        from src.core.config_manager import ConfigManager
        config = ConfigManager()

        self._cached_cameras = cams
        self._cache_time = time.time()

        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.setEnabled(True)

        if cams:
            for cam in cams:
                self.camera_combo.addItem(cam['name'], cam['index'])
            self.camera_combo.addItem("None", -1)

            saved_cam_index = config.get("last_camera_index")
            if saved_cam_index is not None:
                index = self.camera_combo.findData(saved_cam_index)
                if index >= 0:
                    self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.addItem("No camera found", -1)

        self.camera_combo.blockSignals(False)

        if self.camera_combo.count() > 0:
            self.on_camera_changed(self.camera_combo.currentIndex())

    def _populate_from_cache(self):
        """Populate combos from cached device data"""
        from src.core.config_manager import ConfigManager
        config = ConfigManager()

        # Screens (always populate fresh, it's fast)
        self._populate_screens()

        # Microphones from cache
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        if self._cached_mics:
            self.mic_combo.addItems(self._cached_mics)
            saved_mic = config.get("last_mic")
            if saved_mic and saved_mic in self._cached_mics:
                self.mic_combo.setCurrentText(saved_mic)
        else:
            self.mic_combo.addItem("No microphone found")
        self.mic_combo.blockSignals(False)

        if self.mic_combo.count() > 0:
            self.on_mic_changed(self.mic_combo.currentIndex())

        # Cameras from cache
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        if self._cached_cameras:
            for cam in self._cached_cameras:
                self.camera_combo.addItem(cam['name'], cam['index'])
            self.camera_combo.addItem("None", -1)

            saved_cam_index = config.get("last_camera_index")
            if saved_cam_index is not None:
                index = self.camera_combo.findData(saved_cam_index)
                if index >= 0:
                    self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.addItem("No camera found", -1)
        self.camera_combo.blockSignals(False)

        if self.camera_combo.count() > 0:
            self.on_camera_changed(self.camera_combo.currentIndex())

    def on_mic_changed(self, index):
        mic_name = self.mic_combo.currentText()
        
        # Save selection
        from src.core.config_manager import ConfigManager
        ConfigManager().set("last_mic", mic_name)
        
        if self.audio_manager is None:
            from src.core.audio_manager import AudioManager
            self.audio_manager = AudioManager()
            self.audio_manager.level_ready.connect(self.update_audio_level)
            
        if mic_name and mic_name != "None" and mic_name != "No microphone found":
            self.audio_manager.start_monitoring(mic_name)
        else:
            self.audio_manager.stop_monitoring()
            self.audio_level.setValue(0)

    def update_audio_level(self, level):
        # level is 0.0 to 1.0, progress bar is 0-100
        val = int(level * 100)
        self.audio_level.setValue(val)

    def on_camera_changed(self, index):
        camera_index = self.camera_combo.itemData(index)
        logger.debug(f"on_camera_changed: index={index}, camera_index={camera_index}")

        # Save selection
        from src.core.config_manager import ConfigManager
        ConfigManager().set("last_camera_index", camera_index)

        try:
            if self.camera_manager is None:
                from src.core.camera_manager import CameraManager
                self.camera_manager = CameraManager()
                self.camera_manager.frame_ready.connect(self.update_preview)

            if camera_index is not None and camera_index >= 0:
                logger.info(f"Starting camera preview for index {camera_index}")
                self.camera_manager.start_camera(camera_index)
            else:
                logger.debug("Camera disabled, stopping preview")
                self.camera_manager.stop_camera()
                self.preview_label.setPixmap(QPixmap())
                self.preview_label.setText("Camera Disabled")
        except Exception as e:
            logger.error(f"Error in on_camera_changed: {e}")

    def update_preview(self, q_image):
        if not hasattr(self, 'preview_label'):
            return

        # Frame throttling - skip if too recent
        current_time = time.time() * 1000
        if current_time - self._last_frame_time < self._min_frame_interval:
            return
        self._last_frame_time = current_time

        pixmap = QPixmap.fromImage(q_image)
        # Store last valid frame for handoff
        self.last_frame = pixmap

        shape = self.shape_combo.currentData()
        target_size = self.preview_label.size()

        # Cache clipping paths - only recompute when size or shape changes
        if self._cached_size != target_size or self._cached_shape != shape:
            self._cached_size = target_size
            self._cached_shape = shape
            self._cached_clip_path = QPainterPath()

            if shape == "Circle":
                s = min(target_size.width(), target_size.height())
                cx = (target_size.width() - s) // 2
                cy = (target_size.height() - s) // 2
                self._cached_clip_path.addEllipse(cx, cy, s, s)
                self._cached_circle_rect = (cx, cy, s)
            else:
                self._cached_clip_path.addRoundedRect(0, 0, target_size.width(), target_size.height(), 12, 12)
                self._cached_circle_rect = None

        # Create a transparent target pixmap
        target = QPixmap(target_size)
        target.fill(Qt.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipPath(self._cached_clip_path)

        if shape == "Circle":
            cx, cy, s = self._cached_circle_rect
            # Use SmoothTransformation for clear preview
            scaled = pixmap.scaled(s, s, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            ox = cx + (s - scaled.width()) // 2
            oy = cy + (s - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

            # Draw Border
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(QColor("#6200EE"))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.drawEllipse(cx + 2, cy + 2, s - 4, s - 4)
        else:
            # Use SmoothTransformation for clear preview
            scaled = pixmap.scaled(target_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            ox = (target_size.width() - scaled.width()) // 2
            oy = (target_size.height() - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

            # Draw Border
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(QColor("#6200EE"))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.drawRoundedRect(2, 2, target_size.width() - 4, target_size.height() - 4, 12, 12)

        painter.end()
        self.preview_label.setPixmap(target)

    def get_current_frame(self):
        """Returns the last known camera frame as QPixmap or None."""
        return getattr(self, 'last_frame', None)

    def stop_preview(self):
        """Stops camera and audio monitoring explicitly."""
        logger.debug("PreparationView.stop_preview() called")
        try:
            if self.camera_manager:
                self.camera_manager.stop_camera()
        except RuntimeError:
            logger.debug("Camera manager already cleaned up")
        try:
            if self.audio_manager:
                self.audio_manager.stop_monitoring()
        except RuntimeError:
            logger.debug("Audio manager already cleaned up")
        try:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Preview Paused")
        except RuntimeError:
            pass
        # Invalidate cache so devices are rescanned on next show
        self._cache_time = 0

    def hideEvent(self, event):
        """Stop camera when view is hidden (e.g. going back to library)"""
        # Only stop if we were actually initialized (avoid startup issues)
        if self._initialized:
            try:
                self.stop_preview()
            except Exception as e:
                logger.debug(f"Error in hideEvent: {e}")
        super().hideEvent(event)

    def showEvent(self, event):
        """Restart camera if needed when view is shown"""
        logger.debug("PreparationView.showEvent() called")
        self._initialized = True
        super().showEvent(event)
        # Use timer to avoid blocking the show animation
        QTimer.singleShot(50, self.refresh_devices)

