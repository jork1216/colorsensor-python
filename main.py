import sys
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

from ui import MainWindow

def main():
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()