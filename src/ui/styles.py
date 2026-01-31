
# OneTake Style System
# Dark Theme with Purple Accents

MAIN_STYLE = """
/* Global */
QMainWindow, QDialog {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1c20, stop:1 #24243e);
}

QWidget {
    /* Transparent by default to show gradient */
    color: #E0E0E0;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 14px;
}

/* Headers */
QLabel[class="header"] {
    font-size: 24px;
    font-weight: bold;
    color: #BB86FC;
}

/* Buttons */
QPushButton {
    background-color: #3700B3;
    color: #FFFFFF;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #6200EE;
    border: 1px solid #BB86FC;
}
QPushButton:pressed {
    background-color: #03DAC6;
    color: #000000;
}
QPushButton[class="secondary"] {
    background-color: #333333;
    color: #BBBBBB;
}

/* Inputs */
QLineEdit, QComboBox, QListWidget {
    background-color: #1E1E1E;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 8px;
    color: #E0E0E0;
}
QComboBox:hover {
    border: 1px solid #BB86FC;
}
QComboBox::drop-down {
    border-left-width: 0px;
}
/* Pop-up List in ComboBox */
QComboBox QAbstractItemView {
    background-color: #2D2D30; /* Lighter than main bg to stand out */
    color: #E0E0E0;
    selection-background-color: #3700B3;
    selection-color: #FFFFFF;
    border: 1px solid #555555;
}

/* Lists */
QListWidget::item {
    background-color: #1E1E1E;
    padding: 12px;
    margin-bottom: 4px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #3700B3;
    border: 1px solid #BB86FC;
}
QListWidget::item:hover {
    background-color: #2C2C2C;
}

/* Progress Bar (Audio Level) */
QProgressBar {
    background-color: #1E1E1E;
    border: 1px solid #333;
    border-radius: 4px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #BB86FC, stop:1 #03DAC6);
    border-radius: 4px;
}
"""
