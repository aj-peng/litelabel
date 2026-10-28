from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


ZOOM_STEP = 1.25
MIN_ZOOM = 0.05
MAX_ZOOM = 40

class ImageView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene().addItem(self.pixmap_item)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.fitted = True

    def set_image(self, path: Path) -> None:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError(f"Could not open image {path}: {reader.errorString()}")
        self.pixmap_item.setPixmap(QPixmap.fromImage(image))
        self.setSceneRect(self.pixmap_item.boundingRect())

    def fit_image(self) -> None:
        self.fitted = True
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:
        # one mouse-wheel notch is 120; trackpads send smaller steps
        factor = ZOOM_STEP ** (event.angleDelta().y() / 120)
        current = self.transform().m11()
        target = min(max(current * factor, MIN_ZOOM), MAX_ZOOM)
        self.fitted = False
        self.scale(target / current, target / current)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.fitted:
            self.fit_image()