"""
Shared utility for rendering camera frames with shape clipping.
Used by PreparationView and RecorderOverlay for consistent rendering.
"""
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor
from PySide6.QtCore import Qt, QRect


class FrameRenderer:
    """
    Shared utility for rendering camera frames with shape clipping.
    Provides optimized rendering with path caching.
    """

    def __init__(self):
        self._cached_clip_path = None
        self._cached_size = None
        self._cached_shape = None
        self._cached_circle_rect = None
        self._border_color = QColor("#6200EE")
        self._border_width = 4

    def set_border_color(self, color):
        """Set the border color"""
        if isinstance(color, str):
            self._border_color = QColor(color)
        else:
            self._border_color = color

    def set_border_width(self, width):
        """Set the border width in pixels"""
        self._border_width = width

    def _update_cache(self, target_size, shape):
        """Update cached paths if size or shape changed"""
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
                self._cached_clip_path.addRoundedRect(
                    0, 0, target_size.width(), target_size.height(), 12, 12
                )
                self._cached_circle_rect = None

    def render_frame(self, pixmap, target_size, shape, use_smooth=False):
        """
        Renders a pixmap with shape clipping and border.

        Args:
            pixmap: Source QPixmap
            target_size: QSize for output
            shape: "Circle" or "Rectangle"
            use_smooth: Use SmoothTransformation (slower but better quality)

        Returns:
            QPixmap with shape applied
        """
        transform_mode = Qt.SmoothTransformation if use_smooth else Qt.FastTransformation

        # Update cache if needed
        self._update_cache(target_size, shape)

        # Create transparent target pixmap
        target = QPixmap(target_size)
        target.fill(Qt.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setClipPath(self._cached_clip_path)

        if shape == "Circle":
            cx, cy, s = self._cached_circle_rect
            scaled = pixmap.scaled(s, s, Qt.KeepAspectRatioByExpanding, transform_mode)

            ox = cx + (s - scaled.width()) // 2
            oy = cy + (s - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

            # Draw border
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(self._border_color)
            pen.setWidth(self._border_width)
            painter.setPen(pen)
            painter.drawEllipse(cx + 2, cy + 2, s - 4, s - 4)
        else:
            # Rectangle
            scaled = pixmap.scaled(target_size, Qt.KeepAspectRatioByExpanding, transform_mode)

            ox = (target_size.width() - scaled.width()) // 2
            oy = (target_size.height() - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

            # Draw border
            painter.setClipping(False)
            pen = painter.pen()
            pen.setColor(self._border_color)
            pen.setWidth(self._border_width)
            painter.setPen(pen)
            painter.drawRoundedRect(
                2, 2, target_size.width() - 4, target_size.height() - 4, 12, 12
            )

        painter.end()
        return target

    def render_circle_frame(self, pixmap, size, use_smooth=False):
        """
        Convenience method for circle rendering.

        Args:
            pixmap: Source QPixmap
            size: int, diameter of the circle
            use_smooth: Use SmoothTransformation

        Returns:
            QPixmap with circle shape
        """
        from PySide6.QtCore import QSize
        return self.render_frame(pixmap, QSize(size, size), "Circle", use_smooth)

    def render_rect_frame(self, pixmap, target_size, use_smooth=False):
        """
        Convenience method for rectangle rendering.

        Args:
            pixmap: Source QPixmap
            target_size: QSize for output
            use_smooth: Use SmoothTransformation

        Returns:
            QPixmap with rounded rectangle shape
        """
        return self.render_frame(pixmap, target_size, "Rectangle", use_smooth)
