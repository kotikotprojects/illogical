import importlib.metadata
import sys

from PySide6.QtWidgets import QApplication

from illogical.ui.main_window import MainWindow


def main() -> None:
    app_module = sys.modules["__main__"].__package__ or "illogical"
    metadata = importlib.metadata.metadata(app_module)

    QApplication.setApplicationName(metadata["Formal-Name"])

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
