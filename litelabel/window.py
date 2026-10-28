from pathlib import Path

from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class ImageView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene().addItem(self.pixmap_item)

    def set_image(self, path: Path) -> None:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError(f"Could not open image {path}: {reader.errorString()}")
        self.pixmap_item.setPixmap(QPixmap.fromImage(image))
        self.setSceneRect(self.pixmap_item.boundingRect())