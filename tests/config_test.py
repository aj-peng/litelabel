import pytest

from litelabel.config import list_formats, load_config, load_formats, resolve_format, validate_format

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
BOX_FMT = ['classid', 'x1', 'y1', 'x2', 'y2']


# load_config

def test_load_config(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text('delimiter: ","\ndefault_classes: ["target"]\n', encoding='utf-8')
    config = load_config(path)
    assert config['delimiter'] == ","
    assert config['default_classes'] == ["target"]


def test_load_config_fills_defaults(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text('default_classes: ["target"]\nbox_line_width: 4\n', encoding='utf-8')
    config = load_config(path)
    assert config['box_line_width'] == 4
    assert config['min_object_size'] == 10
    assert config['hotkey_right'] == "d"


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


# list_formats / resolve_format

def test_list_formats_numeric_order():
    assert list_formats(CONFIG) == ['format0', 'format1', 'format2', 'format5', 'format10']


def test_resolve_format_inherits_defaults():
    fmt = resolve_format(CONFIG, 'format1')
    assert fmt['delimiter'] == ","
    assert fmt['classes_set'] == "default_classes"
    assert fmt['gt_file_ext'] == "xml"


def test_resolve_format_own_settings_win():
    assert resolve_format(CONFIG, 'format0')['delimiter'] == " "


def test_resolve_format_gt_path_root():
    config = {**CONFIG, 'gt_path_root': "", 'format9': {'data_fmt': BOX_FMT, 'gt_path_root': "../labels"}}
    assert resolve_format(config, 'format9')['gt_path_root'] == "../labels"
    assert resolve_format(config, 'format0')['gt_path_root'] == ""


def test_resolve_format_name_fallback():
    fmt = resolve_format(CONFIG, 'format5')
    assert fmt['name'] == "[fmt5] [cname, x1, y1, w, h]"
    assert fmt['fixed_filetype'] == 0


def test_resolve_format_unknown():
    with pytest.raises(KeyError):
        resolve_format(CONFIG, 'format42')


# validate_format

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


# load_formats

def test_load_formats():
    formats = load_formats(CONFIG)
    assert list(formats) == ['format0', 'format1', 'format2', 'format5', 'format10']
    assert formats['format1']['delimiter'] == ","


def test_load_formats_rejects_broken_format():
    with pytest.raises(ValueError, match="format9"):
        load_formats({**CONFIG, 'format9': {'data_fmt': []}})


def test_load_formats_none():
    with pytest.raises(ValueError, match="no formats"):
        load_formats({'default_classes': ["target"]})
