from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImageReader, QMouseEvent, QPen, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

ZOOM_STEP = 1.25
MIN_ZOOM = 0.05
MAX_ZOOM = 40
GRAB_MARGIN = 6

def find_edges(rect: QRectF, point: QPointF, margin: float) -> set[str]:
    if not rect.adjusted(-margin, -margin, margin, margin).contains(point):
        return set()
    edges = set()
    if abs(point.x() - rect.left()) <= margin:
        edges.add('left')
    elif abs(point.x() - rect.right()) <= margin:
        edges.add('right')
    if abs(point.y() - rect.top()) <= margin:
        edges.add('top')
    elif abs(point.y() - rect.bottom()) <= margin:
        edges.add('bottom')
    return edges

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
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

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
        self.mode = None
        self.active = None
        self.edges = set()
        self.drag_start = QPointF()
        self.start_rect = QRectF()

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
        point = self.mapToScene(event.position().toPoint())
        bounds = self.pixmap_item.boundingRect()
        x = min(max(round(point.x()), 0), bounds.width())
        y = min(max(round(point.y()), 0), bounds.height())
        return QPointF(x, y)

    def box_at(self, point: QPointF) -> BoxItem|None:
        for item in self.scene().items(point):
            if isinstance(item, BoxItem):
                return item
        return None

    def grab_at(self, point: QPointF) -> tuple[BoxItem|None, set[str]]:
        margin = GRAB_MARGIN / self.transform().m11()
        box = self.box_at(point)
        if box:
            return box, find_edges(box.rect(), point, margin)
        for item in self.scene().items():
            if isinstance(item, BoxItem):
                edges = find_edges(item.rect(), point, margin)
                if edges:
                    return item, edges
        return None, set()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.pixmap_item.pixmap().isNull():
            super().mousePressEvent(event)
            return
        self.drag_start = self.scene_point(event)
        self.scene().clearSelection()
        box, self.edges = self.grab_at(self.mapToScene(event.position().toPoint()))
        if box:
            self.mode = 'resize' if self.edges else 'move'
            self.active = box
            box.setSelected(True)
        else:
            self.mode = 'draw'
            self.active = BoxItem(QRectF(self.drag_start, self.drag_start), self.current_cls)
            self.active.setPen(build_pen(self.config))
            self.scene().addItem(self.active)
        self.start_rect = self.active.rect()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # a quick second press arrives as a double-click; treat it as a normal press
        self.mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.mode is None:
            super().mouseMoveEvent(event)
            return
        point = self.scene_point(event)
        if self.mode == 'draw':
            self.active.setRect(QRectF(self.drag_start, point).normalized())
        elif self.mode == 'move':
            # limit the shift so the whole box stays inside the image
            bounds = self.pixmap_item.boundingRect()
            delta = point - self.drag_start
            dx = min(max(delta.x(), -self.start_rect.left()), bounds.width() - self.start_rect.right())
            dy = min(max(delta.y(), -self.start_rect.top()), bounds.height() - self.start_rect.bottom())
            self.active.setRect(self.start_rect.translated(dx, dy))
        elif self.mode == 'resize':
            delta = point - self.drag_start
            rect = QRectF(self.start_rect)
            if 'left' in self.edges:
                rect.setLeft(self.start_rect.left() + delta.x())
            if 'right' in self.edges:
                rect.setRight(self.start_rect.right() + delta.x())
            if 'top' in self.edges:
                rect.setTop(self.start_rect.top() + delta.y())
            if 'bottom' in self.edges:
                rect.setBottom(self.start_rect.bottom() + delta.y())
            self.active.setRect(rect.normalized().intersected(self.pixmap_item.boundingRect()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.mode is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        rect = self.active.rect()
        too_small = min(rect.width(), rect.height()) < self.config['min_object_size']
        if self.mode == 'draw':
            if too_small:
                self.scene().removeItem(self.active)
            else:
                self.active.setSelected(True)
        elif self.mode == 'resize' and too_small:
            self.active.setRect(self.start_rect)
        self.mode = None
        self.active = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        # one mouse-wheel notch is 120; trackpads send smaller steps, so zoom in proportion
        factor = ZOOM_STEP ** (event.angleDelta().y() / 120)
        current = self.transform().m11()
        lowest, highest = min(MIN_ZOOM, current), max(MAX_ZOOM, current)
        target = min(max(current * factor, lowest), highest)
        self.fitted = False
        self.scale(target / current, target / current)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.fitted:
            self.fit_image()