from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QTimer, QTime

class RecordingControlPanel(QWidget):
    """
    Top-bar control panel for recording: [Time] [Restart] [Stop] [Cancel]
    """
    stop_requested = Signal()
    cancel_requested = Signal()
    restart_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Window Flags: Frameless, Always on Top, Tool (no taskbar icon)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Fixed Height, dynamic width (centered)
        self.setFixedHeight(60)
        self.setFixedWidth(400) # Reasonable width
        
        # Main Layout (pill shape)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(20, 10, 20, 10)
        self.layout.setSpacing(15)
        
        # Background Widget for styling
        self.bg_widget = QWidget(self)
        self.bg_widget.setObjectName("PanelBg")
        self.bg_widget.setStyleSheet("""
            #PanelBg {
                background-color: rgba(30, 30, 30, 0.9);
                border: 1px solid #444;
                border-radius: 20px;
            }
        """)
        self.bg_widget.setGeometry(0, 0, self.width(), self.height())
        self.bg_widget.lower() # Send to back
        
        # Timer Label
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet("""
            color: #E0E0E0;
            font-size: 16px;
            font-family: monospace;
            font-weight: bold;
        """)
        self.layout.addWidget(self.timer_label)
        
        # Buttons Style
        btn_style = """
            QPushButton {
                background-color: #333;
                border: 1px solid #555;
                border-radius: 15px;
                color: white;
                font-weight: bold;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #444;
                border-color: #888;
            }
        """
        
        # Restart Button (Yellow/Orange icon or text)
        self.restart_btn = QPushButton("↺")
        self.restart_btn.setFixedSize(30, 30)
        self.restart_btn.setStyleSheet(btn_style + "QPushButton:hover { background-color: #FFB74D; color: black; }")
        self.restart_btn.setToolTip("Перезаписать")
        self.restart_btn.clicked.connect(self.restart_requested.emit)
        self.layout.addWidget(self.restart_btn)

        # Stop Button (Red)
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(30, 30)
        self.stop_btn.setStyleSheet(btn_style + "QPushButton { background-color: #D32F2F; border: none; } QPushButton:hover { background-color: #F44336; }")
        self.stop_btn.setToolTip("Остановить и сохранить")
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.layout.addWidget(self.stop_btn)

        # Cancel Button (X)
        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedSize(30, 30)
        self.cancel_btn.setStyleSheet(btn_style + "QPushButton:hover { background-color: #E57373; color: black; }")
        self.cancel_btn.setToolTip("Отменить (не сохранять)")
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.layout.addWidget(self.cancel_btn)

        # Timer Logic
        self.elapsed_seconds = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)
        
    def update_timer(self):
        self.elapsed_seconds += 1
        t = QTime(0, 0, 0).addSecs(self.elapsed_seconds)
        self.timer_label.setText(t.toString("HH:mm:ss"))

    def paintEvent(self, event):
        # Ensure bg matches size
        self.bg_widget.setGeometry(0, 0, self.width(), self.height())
        super().paintEvent(event)
