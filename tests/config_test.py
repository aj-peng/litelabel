import pytest

from litelabel.config import list_formats, load_config, resolve_format, validate_format
from litelabel.gt import write_gt_file

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

BOX = ['classid', 'x1', 'y1', 'x2', 'y2']

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
    ({'data_fmt': [*BOX, 'xmin']}, "unknown"),
    ({'data_fmt': ['x1', 'y1', 'x2', 'y2']}, "classid or cname"),
    ({'data_fmt': ['classid', 'x1', 'y1', 'y2']}, "along x"),
    ({'data_fmt': ['classid', 'x1', 'nx1', 'y1', 'y2']}, "along x"),
    ({'data_fmt': BOX, 'gt_file_ext': "json"}, "gt_file_ext"),
    ({'data_fmt': BOX, 'gt_merged': 2}, "gt_merged"),
    ({'data_fmt': BOX, 'gt_merged': 1}, "iname"),
    ({'data_fmt': BOX, 'gt_file_ext': "txt", 'delimiter': ""}, "delimiter"),
    ({'data_fmt': BOX, 'classes_set': "missing_classes"}, "classes_set"),
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
