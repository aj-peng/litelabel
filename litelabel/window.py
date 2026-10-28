from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImageReader, QMouseEvent, QPen, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

ZOOM_STEP = 1.25
MIN_ZOOM = 0.05
MAX_ZOOM = 40

def build_pen(config: dict) -> QPen:
    # box_color is stored blue, green, red
    blue, green, red = config['box_color']
    pen = QPen(QColor(red, green, blue), config['box_line_width'])
    # keep the line the same on-screen width at every zoom level
    pen.setCosmetic(True)
    return pen

class BoxItem(QGraphicsRectItem):
    def __init__(self, rect: QRectF, cls: int, difficult: int=0):
        super().__init__(rect)
        self.cls = cls
        self.difficult = difficult

class ImageView(QGraphicsView):
    def __init__(self, config: dict):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene().addItem(self.pixmap_item)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.config = config
        self.fitted = True
        self.current_cls = 0
        self.drawing = None
        self.draw_start = QPointF()

    def set_image(self, path: Path) -> None:
        reader = QImageReader(str(path))
        # apply EXIF orientation so phone photos appear upright, as OpenCV and training tools see them
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            raise ValueError(f"Could not open image {path}: {reader.errorString()}")
        self.pixmap_item.setPixmap(QPixmap.fromImage(image))
        self.setSceneRect(self.pixmap_item.boundingRect())
        self.fit_image()

    def fit_image(self) -> None:
        self.fitted = True
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def scene_point(self, event: QMouseEvent) -> QPointF:
        # whole pixels, kept inside the image
        point = self.mapToScene(event.position().toPoint())
        bounds = self.pixmap_item.boundingRect()
        x = min(max(round(point.x()), 0), bounds.width())
        y = min(max(round(point.y()), 0), bounds.height())
        return QPointF(x, y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.pixmap_item.pixmap().isNull():
            super().mousePressEvent(event)
            return
        self.draw_start = self.scene_point(event)
        self.drawing = BoxItem(QRectF(self.draw_start, self.draw_start), self.current_cls)
        self.drawing.setPen(build_pen(self.config))
        self.scene().addItem(self.drawing)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.drawing is None:
            super().mouseMoveEvent(event)
            return
        self.drawing.setRect(QRectF(self.draw_start, self.scene_point(event)).normalized())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.drawing is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        rect = self.drawing.rect()
        if min(rect.width(), rect.height()) < self.config['min_object_size']:
            self.scene().removeItem(self.drawing)
        self.drawing = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        # one mouse-wheel notch is 120; trackpads send smaller steps, so zoom in proportion
        factor = ZOOM_STEP ** (event.angleDelta().y() / 120)
        current = self.transform().m11()
        target = min(max(current * factor, MIN_ZOOM), MAX_ZOOM)
        self.fitted = False
        self.scale(target / current, target / current)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.fitted:
            self.fit_image()