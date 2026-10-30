import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from litelabel.config import load_config
from litelabel.window import MainWindow

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv)
    window = MainWindow(load_config())
    window.resize(1200, 800)
    window.show()
    window.open_image(args.image)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()