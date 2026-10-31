"""LiteLabel"""
import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from litelabel.config import load_config
from litelabel.window import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, nargs='?', help="an image folder, or one image in it")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    try:
        window = MainWindow(load_config())
    except (OSError, ValueError) as error:
        # a windowed exe has no console, so show the reason instead of closing silently
        QMessageBox.critical(None, "LiteLabel", f"Could not start LiteLabel.\n\n{error}")
        sys.exit(1)
    window.resize(1200, 800)
    window.show()
    if args.path:
        path = args.path.resolve()
        if not path.exists():
            QMessageBox.warning(window, "LiteLabel", f"Not found: {path}")
        elif path.is_dir():
            window.open_folder(path)
        else:
            window.open_folder(path.parent, path)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
