import sys
import os
import time

# Add the project root directory to sys.path so we can import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Initialize logging early
from src.utils import logger

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    start_time = time.time()
    logger.info("=" * 50)
    logger.info("OneTake starting...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")

    app = QApplication(sys.argv)
    logger.debug(f"QApplication created in {(time.time() - start_time)*1000:.0f}ms")
    
    # Optional: Load stylesheet here
    # with open("src/ui/assets/style.qss", "r") as f:
    #     app.setStyleSheet(f.read())
    
    window = MainWindow()
    logger.debug(f"MainWindow created in {(time.time() - start_time)*1000:.0f}ms")

    window.show()
    logger.info(f"Application ready in {(time.time() - start_time)*1000:.0f}ms")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
