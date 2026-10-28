import os

# run without opening real windows; must be set before the QApplication is created
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from litelabel.window import BoxItem, ImageView, build_pen

CONFIG = {'box_color': [0, 255, 0], 'box_line_width': 2, 'min_object_size': 10}

@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def view(app, tmp_path):
    path = tmp_path / "dog.png"
    image = QImage(640, 480, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    image.save(str(path))
    view = ImageView(CONFIG)
    view.resize(1000, 700)
    view.set_image(path)
    view.show()
    app.processEvents()
    yield view
    view.close()

def drag(view: ImageView, start: tuple[int, int], end: tuple[int, int]) -> None:
    viewport = view.viewport()
    start_point, end_point = view.mapFromScene(*start), view.mapFromScene(*end)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_point)
    QTest.mouseMove(viewport, end_point)
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_point)

def list_boxes(view: ImageView) -> list[tuple]:
    return [item.rect().getCoords() for item in view.scene().items() if isinstance(item, BoxItem)]

def wheel(view: ImageView, delta: int) -> None:
    point = QPointF(100, 100)
    view.wheelEvent(QWheelEvent(point, point, QPoint(), QPoint(0, delta), Qt.MouseButton.NoButton,
                                Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))

def test_set_image(view):
    assert view.sceneRect().getCoords() == (0, 0, 640, 480)
    assert view.fitted

def test_set_image_missing(view, tmp_path):
    with pytest.raises(ValueError, match="Could not open image"):
        view.set_image(tmp_path / "missing.png")

def test_wheel_zoom(view):
    fit = view.transform().m11()
    wheel(view, 120)
    assert view.transform().m11() == pytest.approx(fit * 1.25)
    assert not view.fitted

def test_wheel_zoom_limit(view):
    for _ in range(60):
        wheel(view, 120)
    assert view.transform().m11() == pytest.approx(40)

def test_draw_box(view):
    drag(view, (100, 50), (300, 250))
    assert list_boxes(view) == [(100, 50, 300, 250)]

def test_draw_box_any_direction(view):
    drag(view, (300, 250), (100, 50))
    assert list_boxes(view) == [(100, 50, 300, 250)]

def test_draw_box_too_small(view):
    drag(view, (10, 10), (15, 15))
    assert list_boxes(view) == []

def test_draw_box_clamped_to_image(view):
    drag(view, (600, 400), (900, 900))
    assert list_boxes(view) == [(600, 400, 640, 480)]

def test_build_pen_reads_bgr():
    pen = build_pen({**CONFIG, 'box_color': [255, 0, 0]})
    assert pen.color().getRgb()[:3] == (0, 0, 255)
    assert pen.isCosmetic()