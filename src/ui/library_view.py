from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QHBoxLayout, QFrame, QMessageBox,
    QStyledItemDelegate, QStyle, QApplication
)
from PySide6.QtCore import Signal, Qt, QSize, QRect, QPoint
from PySide6.QtGui import QIcon, QPainter, QPen, QBrush, QColor, QFont
import os
import subprocess
from src.utils.paths import get_output_dir


class RecordingItemDelegate(QStyledItemDelegate):
    """
    Efficient delegate that paints items directly without creating widgets.
    Much faster than setItemWidget for large lists.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._open_btn_rect = {}  # Store button rects per index for click handling
        self._del_btn_rect = {}
        self._hovered_index = None
        self._hovered_btn = None

    def paint(self, painter, option, index):
        painter.save()

        # Get data
        file_name = index.data(Qt.DisplayRole) or ""
        file_path = index.data(Qt.UserRole) or ""
        file_size = index.data(Qt.UserRole + 1) or 0

        rect = option.rect
        row = index.row()

        # Background
        painter.setRenderHint(QPainter.Antialiasing)
        bg_rect = rect.adjusted(5, 2, -5, -2)

        if option.state & QStyle.State_Selected:
            painter.setBrush(QColor(55, 0, 179, 128))
            painter.setPen(QColor("#BB86FC"))
        else:
            painter.setBrush(QColor(30, 30, 30, 178))
            painter.setPen(QColor(255, 255, 255, 25))

        painter.drawRoundedRect(bg_rect, 8, 8)

        # File name
        painter.setPen(QColor("#E0E0E0"))
        name_font = QFont()
        name_font.setPointSize(10)
        name_font.setWeight(QFont.Medium)
        painter.setFont(name_font)
        name_rect = QRect(rect.left() + 20, rect.top(), rect.width() - 220, rect.height())
        painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, file_name)

        # Size
        painter.setPen(QColor("#AAA"))
        size_font = QFont()
        size_font.setPointSize(9)
        painter.setFont(size_font)
        size_rect = QRect(rect.right() - 190, rect.top(), 55, rect.height())
        painter.drawText(size_rect, Qt.AlignVCenter | Qt.AlignRight, f"{file_size:.1f} МБ")

        # Open button
        open_btn_rect = QRect(rect.right() - 125, rect.top() + (rect.height() - 32) // 2, 70, 32)
        # Сохраняем в локальных координатах (относительно начала элемента)
        local_open_rect = QRect(open_btn_rect.x() - rect.x(), open_btn_rect.y() - rect.y(), 70, 32)
        self._open_btn_rect[row] = local_open_rect
        painter.setBrush(QColor("#3700B3"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(open_btn_rect, 4, 4)
        painter.setPen(QColor("white"))
        painter.drawText(open_btn_rect, Qt.AlignCenter, "ОТКР")

        # Delete button - красный крестик
        del_btn_rect = QRect(rect.right() - 47, rect.top() + (rect.height() - 32) // 2, 32, 32)
        # Сохраняем в локальных координатах (относительно начала элемента)
        local_del_rect = QRect(del_btn_rect.x() - rect.x(), del_btn_rect.y() - rect.y(), 32, 32)
        self._del_btn_rect[row] = local_del_rect

        # Рисуем красный крестик
        pen = QPen(QColor("#CF6679"))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # Линии крестика (с отступами от краёв)
        margin = 10
        painter.drawLine(
            del_btn_rect.left() + margin, del_btn_rect.top() + margin,
            del_btn_rect.right() - margin, del_btn_rect.bottom() - margin
        )
        painter.drawLine(
            del_btn_rect.right() - margin, del_btn_rect.top() + margin,
            del_btn_rect.left() + margin, del_btn_rect.bottom() - margin
        )

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(400, 60)

    def editorEvent(self, event, model, option, index):
        """Handle mouse clicks on buttons"""
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.MouseButtonRelease:
            # Получаем позицию клика
            click_pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            # Преобразуем в локальные координаты относительно элемента
            local_pos = QPoint(click_pos.x() - option.rect.x(), click_pos.y() - option.rect.y())
            row = index.row()

            # Находим LibraryView (parent -> QListWidget, parent().parent() -> LibraryView)
            list_widget = self.parent()
            library_view = list_widget.parent() if list_widget else None

            # Check open button click
            if row in self._open_btn_rect and self._open_btn_rect[row].contains(local_pos):
                file_path = index.data(Qt.UserRole)
                if file_path and library_view and hasattr(library_view, 'open_file'):
                    library_view.open_file(file_path)
                return True

            # Check delete button click
            if row in self._del_btn_rect and self._del_btn_rect[row].contains(local_pos):
                file_path = index.data(Qt.UserRole)
                if file_path and library_view and hasattr(library_view, 'delete_file'):
                    library_view.delete_file(file_path)
                return True

        return super().editorEvent(event, model, option, index)

class LibraryView(QWidget):
    # Signal to request switching to the preparation screen
    start_new_recording_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header = QLabel("Библиотека")
        header.setProperty("class", "header")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh_list)
        header_layout.addWidget(refresh_btn)

        open_folder_btn = QPushButton("Открыть папку")
        open_folder_btn.clicked.connect(self.open_output_folder)
        header_layout.addWidget(open_folder_btn)
        
        layout.addLayout(header_layout)
        
        # Recordings list
        self.recordings_list = QListWidget()
        self.recordings_list.setSpacing(5) # Add spacing between items
        self.recordings_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                background-color: rgba(30, 30, 30, 0.7); /* Semi-transparent item */
                border-radius: 8px;
                margin: 2px 5px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            QListWidget::item:selected {
                border: 1px solid #BB86FC;
                background-color: rgba(55, 0, 179, 0.5);
            }
        """)
        # We don't necessarily need double click if we have format buttons, but keep it
        self.recordings_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.recordings_list)
        
        # Empty State Label
        self.empty_label = QLabel("Нет записей")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 24px; color: #777;")
        self.empty_label.hide()
        layout.addWidget(self.empty_label)
        
        # 'New Recording' Button
        self.new_recording_btn = QPushButton("Новая запись")
        self.new_recording_btn.setMinimumHeight(60) # Taller button
        self.new_recording_btn.setStyleSheet("""
            QPushButton {
                background-color: #6200EE; 
                color: white; 
                font-size: 18px; 
                font-weight: bold;
                border-radius: 10px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #7C4DFF;
            }
        """)
        self.new_recording_btn.clicked.connect(self.start_new_recording_requested.emit)
        layout.addWidget(self.new_recording_btn)
        
        # Initial refresh
        self.refresh_list()

    def refresh_list(self):
        self.recordings_list.clear()
        output_dir = get_output_dir()

        # Set delegate once (much more efficient than setItemWidget)
        if not hasattr(self, '_delegate'):
            self._delegate = RecordingItemDelegate(self.recordings_list)
            self.recordings_list.setItemDelegate(self._delegate)

        if not os.path.exists(output_dir):
            self.recordings_list.hide()
            self.empty_label.show()
            return

        files = sorted(
            [f for f in os.listdir(output_dir) if f.endswith(('.mp4', '.mkv', '.webm'))],
            key=lambda x: os.path.getmtime(os.path.join(output_dir, x)),
            reverse=True
        )

        if not files:
            self.recordings_list.hide()
            self.empty_label.show()
            return

        self.recordings_list.show()
        self.empty_label.hide()

        for f in files:
            file_path = os.path.join(output_dir, f)
            try:
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
            except OSError:
                size_mb = 0

            # Create Item with data (delegate handles rendering)
            item = QListWidgetItem()
            item.setData(Qt.DisplayRole, f)
            item.setData(Qt.UserRole, file_path)
            item.setData(Qt.UserRole + 1, size_mb)
            item.setSizeHint(QSize(400, 60))

            self.recordings_list.addItem(item)
            # NO setItemWidget() - delegate handles rendering efficiently

    def delete_file(self, filepath):
        ret = QMessageBox.question(self, "Удалить запись", 
                                   f"Вы уверены, что хотите удалить?\n{os.path.basename(filepath)}",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                os.remove(filepath)
                self.refresh_list()
            except Exception as e:
                print(f"Error deleting file: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить файл:\n{e}")

    def on_item_double_clicked(self, item):
        file_path = item.data(Qt.UserRole)
        # Only open if it's a file path (not 'No recordings found' string)
        if file_path and isinstance(file_path, str) and os.path.exists(file_path):
            self.open_file(file_path)

    def open_file(self, file_path):
        if os.name == 'nt':
            try:
                os.startfile(file_path)
            except Exception as e:
                 print(f"Error opening file: {e}")
        else:
            subprocess.call(('xdg-open', file_path))

    def open_output_folder(self):
        output_dir = get_output_dir()
        if os.path.exists(output_dir):
            self.open_file(output_dir)
    
    def showEvent(self, event):
        self.refresh_list()
        super().showEvent(event)
