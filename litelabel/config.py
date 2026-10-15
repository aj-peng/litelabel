from pathlib import Path

import yaml

from litelabel.utility import resolve_app_directory

INHERITED_KEYS = ('gt_file_ext', 'gt_merged', 'delimiter', 'classes_set')

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
        fmt['name'] = f"[fmt{number}] [{', '.join(fmt.get('data_fmt', []))}]"
    return fmt
