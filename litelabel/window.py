from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImageReader, QMouseEvent, QPen, QPixmap, QResizeEvent, QWheelEvent, QKeyEvent, \
    QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget, QMessageBox,
)

from litelabel.config import load_formats
from litelabel.gt import load_boxes, resolve_gt_path, save_boxes

ZOOM_STEP = 1.25
MIN_ZOOM = 0.05
MAX_ZOOM = 40
GRAB_MARGIN = 6
EDGE_CURSORS = {
    frozenset(): Qt.CursorShape.SizeAllCursor,
    frozenset({'left'}): Qt.CursorShape.SizeHorCursor,
    frozenset({'right'}): Qt.CursorShape.SizeHorCursor,
    frozenset({'top'}): Qt.CursorShape.SizeVerCursor,
    frozenset({'bottom'}): Qt.CursorShape.SizeVerCursor,
    frozenset({'left', 'top'}): Qt.CursorShape.SizeFDiagCursor,
    frozenset({'right', 'bottom'}): Qt.CursorShape.SizeFDiagCursor,
    frozenset({'right', 'top'}): Qt.CursorShape.SizeBDiagCursor,
    frozenset({'left', 'bottom'}): Qt.CursorShape.SizeBDiagCursor,
}

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
        self.viewport().setMouseTracking(True)
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
        self.clear_boxes()
        self.pixmap_item.setPixmap(QPixmap.fromImage(image))
        self.setSceneRect(self.pixmap_item.boundingRect())
        self.fit_image()

    def fit_image(self) -> None:
        self.fitted = True
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def image_size(self) -> tuple[int, int]:
        pixmap = self.pixmap_item.pixmap()
        return pixmap.width(), pixmap.height()

    def add_box(self, rect: QRectF, cls: int, difficult: int=0) -> BoxItem:
        box = BoxItem(rect, cls, difficult)
        box.setPen(build_pen(self.config))
        self.scene().addItem(box)
        return box

    def list_box_items(self) -> list[BoxItem]:
        return [item for item in reversed(self.scene().items()) if isinstance(item, BoxItem)]

    def clear_boxes(self) -> None:
        for box in self.list_box_items():
            self.scene().removeItem(box)
        self.mode = None
        self.active = None

    def get_boxes(self) -> list[dict]:
        boxes = []
        for item in self.list_box_items():
            rect = item.rect()
            boxes.append({
                'cls': item.cls,
                'x1': round(rect.left()), 'y1': round(rect.top()), 'x2': round(rect.right()), 'y2': round(rect.bottom()),
                'difficult': item.difficult,
            })
        return boxes

    def set_boxes(self, boxes: list[dict]) -> None:
        self.clear_boxes()
        for box in boxes:
            rect = QRectF(QPointF(box['x1'], box['y1']), QPointF(box['x2'], box['y2']))
            self.add_box(rect, box['cls'], box.get('difficult', 0))

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

    def update_cursor(self, point: QPointF) -> None:
        box, edges = self.grab_at(point)
        if box:
            shape = EDGE_CURSORS[frozenset(edges)]
        elif self.pixmap_item.boundingRect().contains(point):
            shape = Qt.CursorShape.CrossCursor
        else:
            shape = Qt.CursorShape.ArrowCursor
        self.viewport().setCursor(shape)

    def delete_selected(self) -> None:
        for item in self.scene().selectedItems():
            self.scene().removeItem(item)

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
            self.active = self.add_box(QRectF(self.drag_start, self.drag_start), self.current_cls)
        self.start_rect = self.active.rect()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # a quick second press arrives as a double-click; treat it as a normal press
        self.mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.mode is None:
            super().mouseMoveEvent(event)
            self.update_cursor(self.mapToScene(event.position().toPoint()))
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

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Backspace is the delete key on Mac keyboards
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.mode is None:
            self.delete_selected()
        else:
            super().keyPressEvent(event)

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

class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.setWindowTitle("LiteLabel")
        self.config = config
        self.formats = load_formats(config)
        self.image_path = None
        self.view = ImageView(config)
        self.format_box = QComboBox()
        self.class_box = QComboBox()
        for key, fmt in self.formats.items():
            # each entry shows the format's name and remembers its formatN key
            self.format_box.addItem(fmt['name'], key)
        panel = QWidget()
        panel.setFixedWidth(240)
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(QLabel("Format"))
        panel_layout.addWidget(self.format_box)
        panel_layout.addWidget(QLabel("Class"))
        panel_layout.addWidget(self.class_box)
        panel_layout.addStretch()
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(panel)
        self.setCentralWidget(central)
        self.format_box.currentIndexChanged.connect(self.update_classes)
        self.class_box.currentIndexChanged.connect(self.select_class)
        self.update_classes()
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_gt)
        self.addAction(save_action)

    def current_format(self) -> dict:
        return self.formats[self.format_box.currentData()]

    def current_classes(self) -> list[str]:
        return self.config[self.current_format()['classes_set']]

    def update_classes(self) -> None:
        # keep the chosen class when the new format's list still has it
        previous = self.class_box.currentIndex()
        self.class_box.clear()
        self.class_box.addItems(self.current_classes())
        if 0 <= previous < self.class_box.count():
            self.class_box.setCurrentIndex(previous)

    def select_class(self, index: int) -> None:
        # the list briefly has no selection (-1) while it is being refilled
        if index >= 0:
            self.view.current_cls = index

    def open_image(self, path: Path) -> None:
        self.view.set_image(path)
        self.image_path = path
        if self.config.get('auto_gt_load', 1):
            self.load_gt()

    def load_gt(self) -> None:
        width, height = self.view.image_size()
        try:
            boxes = load_boxes(self.image_path, width, height, self.current_format(), self.current_classes(),
                               self.config.get('gt_path_root'))
        except ValueError as error:
            QMessageBox.warning(self, "Could not load GT", str(error))
            return
        self.view.set_boxes(boxes)

    def save_gt(self) -> None:
        if self.image_path is None:
            return
        width, height = self.view.image_size()
        fmt = self.current_format()
        gt_path_root = self.config.get('gt_path_root')
        try:
            save_boxes(self.image_path, self.view.get_boxes(), width, height, fmt, self.current_classes(), gt_path_root)
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, "Could not save GT", str(error))
            return
        self.statusBar().showMessage(f"Saved {resolve_gt_path(self.image_path, fmt, gt_path_root)}", 3000)