import time
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import Qt, QPoint, Signal, QRect
from PySide6.QtGui import QPixmap, QRegion, QPainter, QPainterPath, QColor

class RecorderOverlay(QWidget):
    """
    Transparent overlay window for webcam PiP and controls.
    Separates the Video Display from the Control Bar to allow for 
    different shapes (Circle/Rect) while keeping controls accessible.
    """
    stop_requested = Signal()
    camera_ready = Signal()

    def __init__(self, camera_index=-1, shape="Rectangle", initial_frame=None):
        super().__init__()
        self.camera_index = camera_index
        self.shape = shape
        self.camera_manager = None
        self.first_frame_received = False
        self.old_pos = None  # For dragging

        # Performance optimization: cache for frame rendering
        self._cached_clip_path = None
        self._cached_size = None
        self._cached_circle_rect = None
        self._last_frame_time = 0
        self._min_frame_interval = 33  # ~30 FPS cap
        
        # Window Flags: Frameless, Always on Top, Tool (no taskbar icon)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Initial Resize
        self.resize(320, 300) 
        
        # Main Layout (Vertical)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 1. Video Container (Top)
        self.video_container = QWidget()
        self.video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_layout = QVBoxLayout(self.video_container)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False) 
        # CRITICAL: Ignore size policy to prevent label from forcing window growth when pixmap is set
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.video_layout.addWidget(self.image_label)
        
        self.main_layout.addWidget(self.video_container)
        
        # Apply Initial Style based on Shape
        self.update_style()
        
        # Show Initial Frame (Handoff)
        if initial_frame:
             # Scale to fit current size (use video_container size, not label size which might be 0 or small)
             target_size = self.video_container.size()
             if target_size.width() < 10 or target_size.height() < 10:
                 target_size = self.size() # Fallback
                 
             scaled = initial_frame.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
             self.image_label.setPixmap(scaled)

        # Start Camera
        if self.camera_index >= 0:
            self.start_camera()
        else:
            # If no camera, ready immediately
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self.camera_ready.emit)

    def update_style(self):
        """Applies styles based on Rectangle or Circle shape."""
        # Reset stylesheet first
        self.video_container.setStyleSheet("background-color: transparent;")
        
        if self.shape == "Circle":
            # For Circle, manual drawing handles text/border
            self.image_label.setStyleSheet("border: none;") 
            
        else: # Rectangle
            # We want rounded corners.
            # Label background handles border, but pixmap overlaps?
            # Safe bet: Draw rounded rect in update_image like Circle, OR use stylesheet if resizing handles it.
            self.image_label.setStyleSheet("""
                background-color: black;
                border: 2px solid #6200EE;
                border: 2px solid #6200EE;
                border-radius: 12px;
            """)

    def update_image(self, q_image):
        if not self.first_frame_received:
            self.first_frame_received = True
            self.camera_ready.emit()

        # Frame throttling - skip if too recent
        current_time = time.time() * 1000
        if current_time - self._last_frame_time < self._min_frame_interval:
            return
        self._last_frame_time = current_time

        pixmap = QPixmap.fromImage(q_image)
        container_size = self.image_label.size()

        # Cache clipping paths - only recompute when size changes
        if self._cached_size != container_size:
            self._cached_size = container_size
            self._cached_clip_path = QPainterPath()

            if self.shape == "Circle":
                s = min(container_size.width(), container_size.height())
                self._cached_clip_path.addEllipse(0, 0, s, s)
                self._cached_circle_rect = s
            else:
                self._cached_clip_path.addRoundedRect(QRect(0, 0, container_size.width(), container_size.height()), 12, 12)
                self._cached_circle_rect = None

        if self.shape == "Circle":
            s = self._cached_circle_rect
            if s is None or s <= 0:
                return

            target = QPixmap(s, s)
            target.fill(Qt.transparent)

            painter = QPainter(target)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipPath(self._cached_clip_path)

            # Use SmoothTransformation for clear preview
            scaled_source = pixmap.scaled(s, s, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            x_offset = (scaled_source.width() - s) // 2
            y_offset = (scaled_source.height() - s) // 2
            painter.drawPixmap(-x_offset, -y_offset, scaled_source)

            # Draw Border
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(QColor("#6200EE"))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.drawEllipse(2, 2, s - 4, s - 4)

            painter.end()
            self.image_label.setPixmap(target)

        else:
            target = QPixmap(container_size)
            target.fill(Qt.transparent)

            painter = QPainter(target)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipPath(self._cached_clip_path)

            # Use SmoothTransformation for clear preview
            scaled_pixmap = pixmap.scaled(container_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            x = (container_size.width() - scaled_pixmap.width()) // 2
            y = (container_size.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)

            # Draw Border
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(QColor("#6200EE"))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.drawRoundedRect(2, 2, container_size.width() - 4, container_size.height() - 4, 12, 12)

            painter.end()
            self.image_label.setPixmap(target)

    def start_camera(self):
        from src.core.camera_manager import CameraManager
        self.camera_manager = CameraManager()
        self.camera_manager.frame_ready.connect(self.update_image)
        # Optimization: Request frames resized to our container size
        # This dramatically reduces MainThread work for scaling high-res webcams
        target_w = 400
        target_h = 400
        if self.video_container:
            s = self.video_container.size()
            if s.width() > 0 and s.height() > 0:
                 target_w, target_h = s.width(), s.height()
        
        # Add a bit of buffer for quality if we resize window slightly? 
        # But this window is fixed size usually.
        self.camera_manager.start_camera(self.camera_index, target_w, target_h)

    # Dragging Logic
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def closeEvent(self, event):
        if self.camera_manager:
            self.camera_manager.stop_camera()
        super().closeEvent(event)
