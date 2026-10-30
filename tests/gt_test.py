import pytest

from litelabel.gt import save_boxes

BOX = {'cls': 0, 'x1': 100, 'y1': 50, 'x2': 300, 'y2': 250, 'difficult': 0}
YOLO = {'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'], 'gt_file_ext': "txt", 'gt_merged': 0, 'delimiter': " "}
CLASSES = ["target", "person"]

def test_save_boxes_class_out_of_range(tmp_path):
    with pytest.raises(ValueError, match="out of range"):
        save_boxes(tmp_path / "dog.jpg", [{**BOX, 'cls': 5}], 640, 480, YOLO, CLASSES)
    assert not (tmp_path / "dog.txt").exists()