import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from litelabel.window import ImageView

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    app = QApplication(sys.argv)
    view = ImageView()
    view.set_image(args.image)
    view.resize(1000, 700)
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()