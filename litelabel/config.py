from pathlib import Path

import yaml

from litelabel.utility import resolve_app_directory

INHERITED_KEYS = ('gt_file_ext', 'gt_merged', 'delimiter', 'classes_set')
SPECIFIERS = {
    'iname', 'classid', 'cname', 'difficult',
    'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'w', 'h',
    'nx1', 'ny1', 'nx2', 'ny2', 'ncx', 'ncy', 'nw', 'nh',
}
AXES = {'x': ('x1', 'x2', 'cx', 'w'), 'y': ('y1', 'y2', 'cy', 'h')}
GT_FILE_EXTS = ('txt', 'csv', 'xml')

def load_config(path: Path|None=None) -> dict:
    path = path or resolve_app_directory() / "config.yml"
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with open(path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    except yaml.YAMLError as error:
        mark = getattr(error, 'problem_mark', None)
        location = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        problem = getattr(error, 'problem', None) or error
        raise ValueError(f"Invalid YAML in {path}{location}: {problem}") from error
    # an empty file loads as None and a lone value as a scalar; neither holds settings
    if not isinstance(config, dict):
        raise ValueError(f"Config file has no settings: {path}")
    return config

def list_formats(config: dict) -> list[str]:
    return [f"format{n}" for n in range(100) if f"format{n}" in config]

def resolve_format(config: dict, key: str) -> dict:
    if key not in config:
        raise KeyError(f"Format config not found: {key}")
    if not isinstance(config[key], dict):
        raise ValueError(f"Format config has invalid settings: {key}")
    defaults = {name: config[name] for name in INHERITED_KEYS if name in config}
    fmt: dict = {'fixed_filetype': 0, **defaults, **config[key]}
    if 'name' not in fmt:
        number = key.removeprefix('format')
        fmt['name'] = f"[fmt{number}] [{', '.join(map(str, fmt.get('data_fmt', [])))}]"
    return fmt

def validate_format(config: dict, key: str, fmt: dict) -> None:
    data_fmt = fmt.get('data_fmt')
    if not isinstance(data_fmt, list) or not data_fmt:
        raise ValueError(f"{key}: data_fmt must be a non-empty list")
    unknown = [str(spec) for spec in data_fmt if spec not in SPECIFIERS and not str(spec).startswith('c=')]
    if unknown:
        raise ValueError(f"{key}: unknown data_fmt specifiers: {', '.join(unknown)}")
    if 'classid' not in data_fmt and 'cname' not in data_fmt:
        raise ValueError(f"{key}: data_fmt needs classid or cname")
    # any two of start, end, center and size pin down a box along one axis; normalized values count too
    for axis, quantities in AXES.items():
        found = {spec.removeprefix('n') for spec in data_fmt} & set(quantities)
        if len(found) < 2:
            raise ValueError(f"{key}: data_fmt needs two of {', '.join(quantities)} to rebuild the box along {axis}")
    if fmt.get('gt_file_ext') not in GT_FILE_EXTS:
        raise ValueError(f"{key}: gt_file_ext must be one of {', '.join(GT_FILE_EXTS)}")
    if fmt.get('gt_merged') not in (0, 1):
        raise ValueError(f"{key}: gt_merged must be 0 or 1")
    # rows in a merged file can only be matched back to their image by name
    if fmt['gt_merged'] == 1 and 'iname' not in data_fmt:
        raise ValueError(f"{key}: merged GT files need iname in data_fmt")
    delimiter = fmt.get('delimiter')
    if fmt['gt_file_ext'] == 'txt' and not (isinstance(delimiter, str) and delimiter):
        raise ValueError(f"{key}: txt files need a delimiter")
    classes_set = fmt.get('classes_set')
    if not isinstance(classes_set, str) or not isinstance(config.get(classes_set), list):
        raise ValueError(f"{key}: classes_set '{classes_set}' is not a class list in the config")
