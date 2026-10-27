from pathlib import Path

import pytest

from litelabel.config import list_formats, load_config, resolve_format, validate_format
from litelabel.gt import write_gt_file, resolve_gt_path, read_gt_file, load_boxes, save_boxes, build_voc, \
    write_voc_file, read_voc_file


def test_load_config(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text('delimiter: ","\ndefault_classes: ["target"]\n', encoding='utf-8')
    config = load_config(path)
    assert config['delimiter'] == ","
    assert config['default_classes'] == ["target"]

def test_load_config_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "config.yml")

def test_load_config_syntax_error(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text('format0:\n  data_fmt: [classid, ncx, ncy\n', encoding='utf-8')
    with pytest.raises(ValueError, match="line"):
        load_config(path)

def test_load_config_empty(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("", encoding='utf-8')
    with pytest.raises(ValueError, match="no settings"):
        load_config(path)

CONFIG = {
    'gt_file_ext': "txt",
    'gt_merged': 0,
    'delimiter': ",",
    'classes_set': "default_classes",
    'default_classes': ["target"],
    'format0': {'name': "darknet yolo", 'fixed_filetype': 1, 'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'],
                'gt_file_ext': "txt", 'gt_merged': 0, 'delimiter': " "},
    'format1': {'name': "pascal voc", 'fixed_filetype': 1, 'data_fmt': ['cname', 'difficult', 'x1', 'y1', 'x2', 'y2'],
                'gt_file_ext': "xml", 'gt_merged': 0},
    'format5': {'data_fmt': ['cname', 'x1', 'y1', 'w', 'h']},
    'format10': {'name': "ten", 'data_fmt': ['classid', 'x1', 'y1', 'x2', 'y2']},
    'format2': {'name': "two", 'data_fmt': ['classid', 'x1', 'y1', 'x2', 'y2']},
    'format_notes': "not a format",
    'format05': {'name': "padded number"},
}

def test_list_formats_numeric_order():
    assert list_formats(CONFIG) == ['format0', 'format1', 'format2', 'format5', 'format10']

def test_resolve_format_inherits_defaults():
    fmt = resolve_format(CONFIG, 'format1')
    assert fmt['delimiter'] == ","
    assert fmt['classes_set'] == "default_classes"
    assert fmt['gt_file_ext'] == "xml"

def test_resolve_format_own_settings_win():
    assert resolve_format(CONFIG, 'format0')['delimiter'] == " "

def test_resolve_format_name_fallback():
    fmt = resolve_format(CONFIG, 'format5')
    assert fmt['name'] == "[fmt5] [cname, x1, y1, w, h]"
    assert fmt['fixed_filetype'] == 0

def test_resolve_format_unknown():
    with pytest.raises(KeyError):
        resolve_format(CONFIG, 'format42')

BOX_FMT = ['classid', 'x1', 'y1', 'x2', 'y2']

def test_validate_format_accepts_config():
    for key in list_formats(CONFIG):
        validate_format(CONFIG, key, resolve_format(CONFIG, key))

@pytest.mark.parametrize('data_fmt', [
    ['c=0', 'classid', 'x1', 'y1', 'w', 'h'],
    ['cname', 'ncx', 'ncy', 'nw', 'nh'],
    ['iname', 'classid', 'cx', 'y1', 'x2', 'h'],
])
def test_validate_format_accepts_data_fmt(data_fmt):
    config = {**CONFIG, 'format9': {'data_fmt': data_fmt}}
    validate_format(config, 'format9', resolve_format(config, 'format9'))

@pytest.mark.parametrize('settings, message', [
    ({'data_fmt': []}, "non-empty list"),
    ({'data_fmt': [*BOX_FMT, 'xmin']}, "unknown"),
    ({'data_fmt': ['x1', 'y1', 'x2', 'y2']}, "classid or cname"),
    ({'data_fmt': ['classid', 'x1', 'y1', 'y2']}, "along x"),
    ({'data_fmt': ['classid', 'x1', 'nx1', 'y1', 'y2']}, "along x"),
    ({'data_fmt': BOX_FMT, 'gt_file_ext': "json"}, "gt_file_ext"),
    ({'data_fmt': BOX_FMT, 'gt_merged': 2}, "gt_merged"),
    ({'data_fmt': BOX_FMT, 'gt_merged': 1}, "iname"),
    ({'data_fmt': BOX_FMT, 'gt_file_ext': "txt", 'delimiter': ""}, "delimiter"),
    ({'data_fmt': BOX_FMT, 'classes_set': "missing_classes"}, "classes_set"),
    ({'data_fmt': ['iname', *BOX_FMT], 'gt_file_ext': "xml", 'gt_merged': 1}, "can't be merged"),
])
def test_validate_format_rejects(settings, message):
    config = {**CONFIG, 'format9': settings}
    with pytest.raises(ValueError, match=message):
        validate_format(config, 'format9', resolve_format(config, 'format9'))

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

@pytest.mark.parametrize('gt_path_root, merged, expected', [
    (None, 0, "/data/dogs/dog.txt"),
    ("", 0, "/data/dogs/dog.txt"),
    ("labels", 0, "/data/dogs/labels/dog.txt"),
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

YOLO = {'data_fmt': ['classid', 'ncx', 'ncy', 'nw', 'nh'], 'gt_file_ext': "txt", 'gt_merged': 0, 'delimiter': " "}
MERGED = {'data_fmt': ['iname', 'classid', 'x1', 'y1', 'x2', 'y2'], 'gt_file_ext': "txt", 'gt_merged': 1, 'delimiter': ","}
CLASSES = ["target", "person"]
BOX = {'cls': 0, 'x1': 100, 'y1': 50, 'x2': 300, 'y2': 250, 'difficult': 0}

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
    assert read_voc_file(path) == [{'cname': "target", 'difficult': 0, 'x1': 100.0, 'y1': 50.0, 'x2': 300.0, 'y2': 250.0}]

def test_read_voc_file_missing(tmp_path):
    assert read_voc_file(tmp_path / "dog.xml") == []

@pytest.mark.parametrize('text, message', [
    ("<annotation><object>", "invalid XML"),
    ("<annotation><object><name>target</name></object></annotation>", "object 1 is missing"),
    ("<annotation><object><name>target</name><bndbox><xmin>a</xmin><ymin>1</ymin><xmax>2</xmax><ymax>3</ymax></bndbox></object></annotation>", "object 1"),
])
def test_read_voc_file_errors(tmp_path, text, message):
    path = tmp_path / "dog.xml"
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match=message):
        read_voc_file(path)

VOC = {'data_fmt': ['cname', 'difficult', 'x1', 'y1', 'x2', 'y2'], 'gt_file_ext': "xml", 'gt_merged': 0}

def test_save_and_load_boxes_voc(tmp_path):
    image_path = tmp_path / "dog.jpg"
    save_boxes(image_path, [BOX], 640, 480, VOC, CLASSES)
    assert (tmp_path / "dog.xml").is_file()
    assert load_boxes(image_path, 640, 480, VOC, CLASSES) == [BOX]

def test_load_boxes_voc_error_names_file(tmp_path):
    (tmp_path / "dog.xml").write_text("<annotation><object>", encoding='utf-8')
    with pytest.raises(ValueError, match="dog.xml: invalid XML"):
        load_boxes(tmp_path / "dog.jpg", 640, 480, VOC, CLASSES)