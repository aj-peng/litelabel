import os

# run without opening real windows; must be set before the QApplication is created
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, QRectF
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog

from litelabel.gt import load_boxes, save_boxes
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
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     view.mapFromScene(*point))


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
    'animal_classes': ["cat", "dog", "bird"],
    'format0': {'name': "darknet yolo", 'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'], 'delimiter': " "},
    'format1': {'name': "pascal voc", 'data_fmt': ['cname', 'difficult', 'x1', 'y1', 'x2', 'y2'], 'gt_file_ext': "xml"},
    'format2': {'name': "animals", 'data_fmt': ['cname', 'x1', 'y1', 'x2', 'y2'], 'classes_set': "animal_classes"},
}


def list_items(box) -> list[str]:
    return [box.itemText(index) for index in range(box.count())]


def test_format_dropdown(app):
    window = MainWindow(FULL_CONFIG)
    names = [window.format_box.itemText(index) for index in range(window.format_box.count())]
    assert names == ["darknet yolo", "pascal voc", "animals"]
    assert window.current_format()['gt_file_ext'] == "txt"
    window.format_box.setCurrentIndex(1)
    assert window.current_format()['gt_file_ext'] == "xml"


def test_class_dropdown_follows_format(app):
    window = MainWindow(FULL_CONFIG)
    assert list_items(window.class_box) == ["target"]
    window.format_box.setCurrentIndex(2)
    assert list_items(window.class_box) == ["cat", "dog", "bird"]


def test_class_dropdown_sets_new_box_class(app):
    window = MainWindow(FULL_CONFIG)
    window.format_box.setCurrentIndex(2)
    window.class_box.setCurrentIndex(1)
    assert window.view.current_cls == 1


def test_class_choice_kept_or_reset(app):
    window = MainWindow(FULL_CONFIG)
    window.format_box.setCurrentIndex(2)
    window.class_box.setCurrentIndex(2)
    window.format_box.setCurrentIndex(0)
    assert window.class_box.currentIndex() == 0
    assert window.view.current_cls == 0


BOX = {'cls': 0, 'x1': 100, 'y1': 50, 'x2': 300, 'y2': 250, 'difficult': 0}
YOLO = {'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'], 'gt_file_ext': "txt", 'gt_merged': 0, 'delimiter': " "}


def test_image_size(view):
    assert view.image_size() == (640, 480)


def test_get_boxes_after_drawing(view):
    drag(view, (100, 50), (300, 250))
    assert view.get_boxes() == [BOX]


def test_set_boxes_round_trip(view):
    boxes = [BOX, {'cls': 1, 'x1': 10, 'y1': 20, 'x2': 30, 'y2': 40, 'difficult': 1}]
    view.set_boxes(boxes)
    assert view.get_boxes() == boxes


def test_set_boxes_replaces_existing(view):
    drag(view, (400, 300), (500, 400))
    view.set_boxes([BOX])
    assert view.get_boxes() == [BOX]


def test_set_image_clears_boxes(view, tmp_path):
    view.set_boxes([BOX])
    path = tmp_path / "cat.png"
    QImage(320, 240, QImage.Format.Format_RGB32).save(str(path))
    view.set_image(path)
    assert view.get_boxes() == []


def test_save_and_reload_drawn_box(view, tmp_path):
    drag(view, (100, 50), (300, 250))
    image_path = tmp_path / "dog.png"
    width, height = view.image_size()
    save_boxes(image_path, view.get_boxes(), width, height, YOLO, ["target"])
    view.set_image(image_path)
    view.set_boxes(load_boxes(image_path, width, height, YOLO, ["target"]))
    assert view.get_boxes() == [BOX]


@pytest.fixture
def window(app, tmp_path):
    path = tmp_path / "dog.png"
    QImage(640, 480, QImage.Format.Format_RGB32).save(str(path))
    window = MainWindow(FULL_CONFIG)
    window.resize(1200, 800)
    window.show()
    app.processEvents()
    yield window
    window.hide()


@pytest.fixture
def warnings(monkeypatch):
    # record message boxes instead of opening them, which would block the test
    shown = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda parent, title, text: shown.append(title))
    return shown


def test_open_image_loads_gt(window, tmp_path):
    (tmp_path / "dog.txt").write_text("0 0.3125 0.3125 0.3125 0.416667\n", encoding='utf-8')
    window.open_image(tmp_path / "dog.png")
    assert window.view.get_boxes() == [BOX]


def test_open_image_without_auto_load(app, tmp_path):
    path = tmp_path / "dog.png"
    QImage(640, 480, QImage.Format.Format_RGB32).save(str(path))
    (tmp_path / "dog.txt").write_text("0 0.3125 0.3125 0.3125 0.416667\n", encoding='utf-8')
    window = MainWindow({**FULL_CONFIG, 'auto_gt_load': 0})
    window.open_image(path)
    assert window.view.get_boxes() == []


def test_save_gt(window, tmp_path):
    window.open_image(tmp_path / "dog.png")
    window.view.set_boxes([BOX])
    window.save_gt()
    assert (tmp_path / "dog.txt").read_text(encoding='utf-8') == "0 0.3125 0.3125 0.3125 0.416667\n"
    assert "dog.txt" in window.statusBar().currentMessage()


def test_load_gt_error_warns(window, tmp_path, warnings):
    (tmp_path / "dog.txt").write_text("0 abc 0.3125 0.3125 0.416667\n", encoding='utf-8')
    window.open_image(tmp_path / "dog.png")
    assert warnings == ["Could not load GT"]
    assert window.view.get_boxes() == []


def test_save_gt_class_out_of_range_warns(window, tmp_path, warnings):
    window.open_image(tmp_path / "dog.png")
    window.view.set_boxes([{**BOX, 'cls': 2}])
    window.save_gt()
    assert warnings == ["Could not save GT"]
    assert not (tmp_path / "dog.txt").exists()


@pytest.fixture
def folder(tmp_path):
    # a subfolder, so the window fixture's dog.png isn't part of it
    frames = tmp_path / "frames"
    frames.mkdir()
    for name in ["frame1.png", "frame2.png", "frame10.png"]:
        QImage(640, 480, QImage.Format.Format_RGB32).save(str(frames / name))
    (frames / "frame2.txt").write_text("0 0.3125 0.3125 0.3125 0.416667\n", encoding='utf-8')
    return frames


def test_open_folder_starts_at_first_image(window, folder):
    window.open_folder(folder)
    assert window.image_path.name == "frame1.png"
    assert "(1/3)" in window.windowTitle()


def test_open_folder_at_given_image(window, folder):
    window.open_folder(folder, folder / "frame10.png")
    assert window.index == 2


def test_next_and_previous(window, folder):
    window.open_folder(folder)
    window.show_next()
    assert window.image_path.name == "frame2.png"
    assert window.view.get_boxes() == [BOX]
    window.show_previous()
    assert window.image_path.name == "frame1.png"
    assert window.view.get_boxes() == []


def test_navigation_stops_at_ends(window, folder):
    window.open_folder(folder)
    window.show_previous()
    assert window.index == 0
    window.go_to(2)
    window.show_next()
    assert window.index == 2


def test_hotkeys(window, folder):
    window.open_folder(folder)
    QTest.keyClick(window, Qt.Key.Key_D)
    assert window.index == 1
    QTest.keyClick(window, Qt.Key.Key_A)
    assert window.index == 0


def test_open_folder_without_images(window, tmp_path, warnings):
    empty = tmp_path / "empty"
    empty.mkdir()
    window.open_folder(empty)
    assert warnings == ["No images"]


def test_bad_image_does_not_block_navigation(window, folder, warnings):
    (folder / "frame3.png").write_bytes(b"not an image")
    window.open_folder(folder)
    window.go_to(2)
    window.show_next()
    assert warnings == ["Could not open image"]
    assert window.index == 3


def test_navigation_saves_changes(window, folder):
    window.open_folder(folder)
    window.view.set_boxes([BOX])
    window.show_next()
    assert (folder / "frame1.txt").read_text(encoding='utf-8') == "0 0.3125 0.3125 0.3125 0.416667\n"


def test_navigation_without_changes_writes_nothing(window, folder):
    window.open_folder(folder)
    window.show_next()
    window.show_previous()
    assert not (folder / "frame1.txt").exists()


def test_failed_save_stays_on_image(window, folder, warnings):
    window.open_folder(folder)
    window.view.set_boxes([{**BOX, 'cls': 2}])
    window.show_next()
    assert warnings == ["Could not save GT"]
    assert window.index == 0


def test_close_saves_changes(window, folder):
    window.open_folder(folder)
    window.view.set_boxes([BOX])
    assert window.close()
    assert (folder / "frame1.txt").exists()


@pytest.mark.parametrize('answer, closed', [
    (QMessageBox.StandardButton.Yes, True),
    (QMessageBox.StandardButton.No, False),
])
def test_close_asks_when_save_fails(window, folder, warnings, monkeypatch, answer, closed):
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: answer)
    window.open_folder(folder)
    window.view.set_boxes([{**BOX, 'cls': 2}])
    assert window.close() == closed


def test_menus(window):
    menus = {action.text(): [item.text() for item in action.menu().actions()] for action in window.menuBar().actions()}
    assert menus == {'File': ["Open Folder...", "Save"], 'Image': ["Previous", "Next"]}


def test_choose_folder(window, folder, monkeypatch):
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(folder))
    window.choose_folder()
    assert window.image_path == folder / "frame1.png"


def test_choose_folder_cancelled(window, monkeypatch):
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: "")
    window.choose_folder()
    assert window.image_path is None


def test_choose_folder_starts_at_media_path_root(app, tmp_path, monkeypatch):
    starts = []
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda parent, title, start: starts.append(start) or "")
    window = MainWindow({**FULL_CONFIG, 'media_path_root': str(tmp_path)})
    window.choose_folder()
    assert starts == [str(tmp_path)]
