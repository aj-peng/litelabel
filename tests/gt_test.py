from pathlib import Path

import pytest

from litelabel.gt import (
    build_box, build_voc, compute_fields, format_row, load_boxes, parse_row,
    read_gt_file, read_voc_file, resolve_gt_path, save_boxes, write_gt_file, write_voc_file,
)

CLASSES = ["target", "person"]
BOX = {'cls': 0, 'x1': 100, 'y1': 50, 'x2': 300, 'y2': 250, 'difficult': 0}
YOLO = {'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'], 'gt_file_ext': "txt", 'gt_merged': 0, 'delimiter': " "}
MERGED = {'data_fmt': ['iname', 'classid', 'x1', 'y1', 'x2', 'y2'], 'gt_file_ext': "txt", 'gt_merged': 1,
          'delimiter': ","}
VOC = {'data_fmt': ['cname', 'difficult', 'x1', 'y1', 'x2', 'y2'], 'gt_file_ext': "xml", 'gt_merged': 0}


# rows

@pytest.mark.parametrize('data_fmt', [
    ['classid', 'ncx', 'ncy', 'nw', 'nh'],
    ['cname', 'difficult', 'x1', 'y1', 'x2', 'y2'],
    ['iname', 'cname', 'x1', 'y1', 'w', 'h'],
    ['classid', 'cx', 'cy', 'x2', 'y2', 'c=0'],
    ['classid', 'nx1', 'ny2', 'ncx', 'nh'],
])
def test_round_trip(data_fmt):
    fields = compute_fields(BOX, 640, 480, CLASSES, "dog.jpg")
    row = format_row(fields, data_fmt)
    assert build_box(parse_row(row, data_fmt), 640, 480, CLASSES) == BOX


# txt / csv files

def test_write_gt_file(tmp_path):
    fmt = {'gt_file_ext': "txt", 'delimiter': " "}
    path = tmp_path / "gt" / "dog.txt"
    write_gt_file(path, [["0", "0.3125", "0.3125", "0.3125", "0.416667"]], fmt)
    assert path.read_text(encoding='utf-8') == "0 0.3125 0.3125 0.3125 0.416667\n"


def test_write_gt_file_csv_ignores_delimiter(tmp_path):
    fmt = {'gt_file_ext': "csv", 'delimiter': " "}
    path = tmp_path / "dog.csv"
    write_gt_file(path, [["target", "100", "50"]], fmt)
    assert path.read_text(encoding='utf-8') == "target,100,50\n"


def test_write_gt_file_failure_keeps_original(tmp_path):
    path = tmp_path / "dog.txt"
    path.write_text("original\n", encoding='utf-8')
    with pytest.raises(TypeError):
        write_gt_file(path, [["0"], [1]], {'gt_file_ext': "txt", 'delimiter': " "})
    assert path.read_text(encoding='utf-8') == "original\n"
    assert list(tmp_path.iterdir()) == [path]


def test_write_gt_file_leaves_no_temp(tmp_path):
    path = tmp_path / "dog.txt"
    write_gt_file(path, [["0", "1"]], {'gt_file_ext': "txt", 'delimiter': " "})
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('gt_path_root, merged, expected', [
    (None, 0, "/data/dogs/dog.txt"),
    ("", 0, "/data/dogs/dog.txt"),
    ("labels", 0, "/data/dogs/labels/dog.txt"),
    ("../labels", 0, "/data/labels/dog.txt"),
    ("/gt", 0, "/gt/dog.txt"),
    (None, 1, "/data/dogs/dogs.txt"),
    ("/gt", 1, "/gt/dogs.txt"),
])
def test_resolve_gt_path(gt_path_root, merged, expected):
    fmt = {'gt_merged': merged, 'gt_file_ext': "txt"}
    assert resolve_gt_path(Path("/data/dogs/dog.jpg"), fmt, gt_path_root) == Path(expected)


def test_read_gt_file(tmp_path):
    path = tmp_path / "dog.txt"
    path.write_bytes("\ufeff0 0.3125  0.3125 0.3125 0.416667\r\n\r\n1 0.5 0.5 0.1 0.1\r\n".encode('utf-8'))
    fmt = {'gt_file_ext': "txt", 'delimiter': " "}
    assert read_gt_file(path, fmt) == [
        ["0", "0.3125", "0.3125", "0.3125", "0.416667"],
        ["1", "0.5", "0.5", "0.1", "0.1"],
    ]


def test_read_gt_file_missing(tmp_path):
    assert read_gt_file(tmp_path / "missing.txt", {'gt_file_ext': "txt", 'delimiter': " "}) == []


# VOC XML files

def test_build_voc():
    annotation = build_voc(Path("/data/dogs/dog.jpg"), [BOX], 640, 480, CLASSES)
    assert annotation.findtext('folder') == "dogs"
    assert annotation.findtext('filename') == "dog.jpg"
    assert annotation.findtext('size/width') == "640"
    assert annotation.findtext('size/height') == "480"
    obj = annotation.find('object')
    assert obj.findtext('name') == "target"
    assert obj.findtext('difficult') == "0"
    assert [obj.findtext(f"bndbox/{tag}") for tag in ('xmin', 'ymin', 'xmax', 'ymax')] == ["100", "50", "300", "250"]


def test_write_voc_file(tmp_path):
    path = tmp_path / "dog.xml"
    write_voc_file(path, build_voc(Path("/data/dogs/dog.jpg"), [BOX], 640, 480, CLASSES))
    text = path.read_text(encoding='utf-8')
    assert text.startswith("<annotation>\n  <folder>dogs</folder>\n")
    assert "    <bndbox>\n      <xmin>100</xmin>\n" in text
    assert list(tmp_path.iterdir()) == [path]


def test_read_voc_file(tmp_path):
    path = tmp_path / "dog.xml"
    write_voc_file(path, build_voc(Path("/data/dogs/dog.jpg"), [BOX], 640, 480, CLASSES))
    assert read_voc_file(path) == [
        {'cname': "target", 'difficult': 0, 'x1': 100.0, 'y1': 50.0, 'x2': 300.0, 'y2': 250.0}]


def test_read_voc_file_missing(tmp_path):
    assert read_voc_file(tmp_path / "dog.xml") == []


@pytest.mark.parametrize('text, message', [
    ("<annotation><object>", "invalid XML"),
    ("<annotation><object><name>target</name></object></annotation>", "object 1 is missing"),
    ("<annotation><object><name>target</name><bndbox><xmin>a</xmin><ymin>1</ymin><xmax>2</xmax><ymax>3</ymax></bndbox></object></annotation>",
     "object 1"),
])
def test_read_voc_file_errors(tmp_path, text, message):
    path = tmp_path / "dog.xml"
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match=message):
        read_voc_file(path)


# load_boxes / save_boxes

def test_load_boxes_per_image(tmp_path):
    image_path = tmp_path / "dog.jpg"
    (tmp_path / "dog.txt").write_text("0 0.3125 0.3125 0.3125 0.416667\n", encoding='utf-8')
    assert load_boxes(image_path, 640, 480, YOLO, CLASSES) == [BOX]


def test_load_boxes_merged(tmp_path):
    folder = tmp_path / "dogs"
    folder.mkdir()
    (folder / "dogs.txt").write_text("dog.jpg,0,100,50,300,250\ncat.jpg,1,10,10,20,20\n", encoding='utf-8')
    assert load_boxes(folder / "dog.jpg", 640, 480, MERGED, CLASSES) == [BOX]


def test_load_boxes_error_names_file(tmp_path):
    (tmp_path / "dog.txt").write_text("0 abc 0.3125 0.3125 0.416667\n", encoding='utf-8')
    with pytest.raises(ValueError, match="dog.txt"):
        load_boxes(tmp_path / "dog.jpg", 640, 480, YOLO, CLASSES)


def test_save_boxes_per_image(tmp_path):
    image_path = tmp_path / "dog.jpg"
    save_boxes(image_path, [BOX], 640, 480, YOLO, CLASSES)
    assert (tmp_path / "dog.txt").read_text(encoding='utf-8') == "0 0.3125 0.3125 0.3125 0.416667\n"
    assert load_boxes(image_path, 640, 480, YOLO, CLASSES) == [BOX]


def test_save_boxes_merged_keeps_other_images(tmp_path):
    folder = tmp_path / "dogs"
    folder.mkdir()
    gt_path = folder / "dogs.txt"
    gt_path.write_text("cat.jpg,1,10,10,20,20\ndog.jpg,1,0,0,5,5\nemu.jpg,0,1,1,2,2\n", encoding='utf-8')
    save_boxes(folder / "dog.jpg", [BOX], 640, 480, MERGED, CLASSES)
    assert gt_path.read_text(encoding='utf-8') == "cat.jpg,1,10,10,20,20\ndog.jpg,0,100,50,300,250\nemu.jpg,0,1,1,2,2\n"


def test_save_boxes_merged_no_boxes(tmp_path):
    folder = tmp_path / "dogs"
    folder.mkdir()
    gt_path = folder / "dogs.txt"
    gt_path.write_text("cat.jpg,1,10,10,20,20\ndog.jpg,1,0,0,5,5\n", encoding='utf-8')
    save_boxes(folder / "dog.jpg", [], 640, 480, MERGED, CLASSES)
    assert gt_path.read_text(encoding='utf-8') == "cat.jpg,1,10,10,20,20\n"


def test_save_boxes_class_out_of_range(tmp_path):
    with pytest.raises(ValueError, match="out of range"):
        save_boxes(tmp_path / "dog.jpg", [{**BOX, 'cls': 5}], 640, 480, YOLO, CLASSES)
    assert not (tmp_path / "dog.txt").exists()


def test_save_and_load_boxes_voc(tmp_path):
    image_path = tmp_path / "dog.jpg"
    save_boxes(image_path, [BOX], 640, 480, VOC, CLASSES)
    assert (tmp_path / "dog.xml").is_file()
    assert load_boxes(image_path, 640, 480, VOC, CLASSES) == [BOX]


def test_load_boxes_voc_error_names_file(tmp_path):
    (tmp_path / "dog.xml").write_text("<annotation><object>", encoding='utf-8')
    with pytest.raises(ValueError, match="dog.xml: invalid XML"):
        load_boxes(tmp_path / "dog.jpg", 640, 480, VOC, CLASSES)
