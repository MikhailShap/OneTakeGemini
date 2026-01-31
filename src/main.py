import sys
import os

# Add the project root directory to sys.path so we can import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    print("Starting OneTake...")
    app = QApplication(sys.argv)
    
    # Optional: Load stylesheet here
    # with open("src/ui/assets/style.qss", "r") as f:
    #     app.setStyleSheet(f.read())
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
