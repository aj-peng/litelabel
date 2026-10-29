import os

# run without opening real windows; must be set before the QApplication is created
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, QRectF
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from litelabel.window import BoxItem, ImageView, build_pen, find_edges, MainWindow

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

def selected_boxes(view: ImageView) -> list[tuple]:
    return [item.rect().getCoords() for item in view.scene().selectedItems()]

def click(view: ImageView, point: tuple[int, int]) -> None:
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, view.mapFromScene(*point))

def test_new_box_is_selected(view):
    drag(view, (100, 50), (300, 250))
    assert selected_boxes(view) == [(100, 50, 300, 250)]

def test_click_selects_box(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (400, 300), (500, 400))
    click(view, (200, 150))
    assert selected_boxes(view) == [(100, 50, 300, 250)]

def test_click_empty_clears_selection(view):
    drag(view, (100, 50), (300, 250))
    click(view, (500, 400))
    assert selected_boxes(view) == []

def test_move_box(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (200, 150), (250, 170))
    assert list_boxes(view) == [(150, 70, 350, 270)]

def test_move_box_stays_inside_image(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (200, 150), (630, 470))
    assert list_boxes(view) == [(440, 280, 640, 480)]

@pytest.mark.parametrize('point, expected', [
    ((200, 150), set()),
    ((100, 150), {'left'}),
    ((303, 150), {'right'}),
    ((300, 250), {'right', 'bottom'}),
    ((400, 150), set()),
])
def test_find_edges(point, expected):
    assert find_edges(QRectF(100, 50, 200, 200), QPointF(*point), 4) == expected

def test_resize_edge(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (300, 150), (350, 150))
    assert list_boxes(view) == [(100, 50, 350, 250)]

def test_resize_corner(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (300, 250), (320, 270))
    assert list_boxes(view) == [(100, 50, 320, 270)]

def test_resize_stays_inside_image(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (300, 150), (900, 150))
    assert list_boxes(view) == [(100, 50, 640, 250)]

def test_resize_too_small_reverts(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (100, 150), (295, 150))
    assert list_boxes(view) == [(100, 50, 300, 250)]

def test_middle_still_moves(view):
    drag(view, (100, 50), (300, 250))
    drag(view, (200, 150), (210, 150))
    assert list_boxes(view) == [(110, 50, 310, 250)]

def test_wheel_zoom_tiny_image_never_reverses(app, tmp_path):
    path = tmp_path / "tiny.png"
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkCyan)
    image.save(str(path))
    view = ImageView(CONFIG)
    view.resize(1000, 700)
    view.set_image(path)
    view.show()
    app.processEvents()
    fit = view.transform().m11()
    wheel(view, 120)
    assert view.transform().m11() >= fit
    view.close()

def hover(view: ImageView, point: tuple[float, float]) -> Qt.CursorShape:
    QTest.mouseMove(view.viewport(), view.mapFromScene(*point))
    return view.viewport().cursor().shape()

@pytest.mark.parametrize('point, expected', [
    ((200, 150), Qt.CursorShape.SizeAllCursor),
    ((300, 150), Qt.CursorShape.SizeHorCursor),
    ((200, 50), Qt.CursorShape.SizeVerCursor),
    ((300, 250), Qt.CursorShape.SizeFDiagCursor),
    ((300, 50), Qt.CursorShape.SizeBDiagCursor),
    ((500, 400), Qt.CursorShape.CrossCursor),
])
def test_hover_cursor(view, point, expected):
    drag(view, (100, 50), (300, 250))
    assert hover(view, point) == expected

def test_hover_cursor_outside_image(view):
    view.resize(1400, 700)
    assert hover(view, (-50, 200)) == Qt.CursorShape.ArrowCursor

@pytest.mark.parametrize('key', [Qt.Key.Key_Delete, Qt.Key.Key_Backspace])
def test_delete_selected_box(view, key):
    drag(view, (100, 50), (300, 250))
    drag(view, (400, 300), (500, 400))
    click(view, (200, 150))
    QTest.keyClick(view, key)
    assert list_boxes(view) == [(400, 300, 500, 400)]

def test_delete_with_nothing_selected(view):
    drag(view, (100, 50), (300, 250))
    click(view, (500, 400))
    QTest.keyClick(view, Qt.Key.Key_Delete)
    assert list_boxes(view) == [(100, 50, 300, 250)]

FULL_CONFIG = {
    **CONFIG,
    'gt_file_ext': "txt", 'gt_merged': 0, 'delimiter': ",", 'classes_set': "default_classes",
    'default_classes': ["target"],
    'format0': {'name': "darknet yolo", 'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'], 'delimiter': " "},
    'format1': {'name': "pascal voc", 'data_fmt': ['cname', 'difficult', 'x1', 'y1', 'x2', 'y2'], 'gt_file_ext': "xml"},
}

def test_format_dropdown(app):
    window = MainWindow(FULL_CONFIG)
    names = [window.format_box.itemText(index) for index in range(window.format_box.count())]
    assert names == ["darknet yolo", "pascal voc"]
    assert window.current_format()['gt_file_ext'] == "txt"
    window.format_box.setCurrentIndex(1)
    assert window.current_format()['gt_file_ext'] == "xml"