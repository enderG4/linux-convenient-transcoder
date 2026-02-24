import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from qt_material import apply_stylesheet

from ui import MainWindow


def main():
    app = QApplication(sys.argv)

    # Base font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    apply_stylesheet(app, theme="dark_lightgreen.xml")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()