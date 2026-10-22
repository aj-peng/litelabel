from pathlib import Path

from litelabel.config import AXES

def compute_fields(box: dict, width: int, height: int, classes: list[str], image_name: str) -> dict:
    x1, y1, x2, y2 = box['x1'], box['y1'], box['x2'], box['y2']
    w, h = x2 - x1, y2 - y1
    cx, cy = x1 + w / 2, y1 + h / 2
    return {
        'iname': image_name,
        'classid': box['cls'],
        'cname': classes[box['cls']],
        'difficult': box.get('difficult', 0),
        'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
        'cx': cx, 'cy': cy, 'w': w, 'h': h,
        'nx1': x1 / width, 'ny1': y1 / height, 'nx2': x2 / width, 'ny2': y2 / height,
        'ncx': cx / width, 'ncy': cy / height, 'nw': w / width, 'nh': h / height,
    }

def format_value(value: str|int|float) -> str:
    # 6 significant digits: 200.0 -> '200', 0.41666... -> '0.416667'
    return value if isinstance(value, str) else f"{value:g}"

def format_row(fields: dict, data_fmt: list[str]) -> list[str]:
    row = []
    for spec in data_fmt:
        if spec.startswith('c='):
            row.append(spec[2:])
        else:
            row.append(format_value(fields[spec]))
    return row

def parse_row(row: list[str], data_fmt: list[str]) -> dict:
    if len(row) != len(data_fmt):
        raise ValueError(f"Row has {len(row)} columns but data_fmt has {len(data_fmt)}: {row}")
    fields = {}
    for spec, value in zip(data_fmt, row):
        value = value.strip()
        if spec.startswith('c='):
            continue
        if spec in ('iname', 'cname'):
            fields[spec] = value
        elif spec in ('classid', 'difficult'):
            fields[spec] = int(value)
        else:
            fields[spec] = float(value)
    return fields

def resolve_span(
        start: float|None,
        end: float|None,
        center: float|None,
        size: float|None
) -> tuple[float, float]:
    if start is not None and end is not None:
        return start, end
    if start is not None and size is not None:
        return start, start + size
    if end is not None and size is not None:
        return end - size, end
    if center is not None and size is not None:
        return center - size / 2, center + size / 2
    if center is not None and start is not None:
        return start, 2 * center - start
    if center is not None and end is not None:
        return 2 * center - end, end
    raise ValueError("Not enough coordinates to rebuild the box")

def build_box(fields: dict, width: int, height: int, classes: list[str]) -> dict:
    if 'classid' in fields:
        cls = fields['classid']
    elif fields['cname'] in classes:
        cls = classes.index(fields['cname'])
    else:
        raise ValueError(f"Class name not in classes_set: {fields['cname']}")
    if not 0 <= cls < len(classes):
        raise ValueError(f"Class id {cls} out of range for {len(classes)} classes")
    pixels = {}
    for axis, size in (('x', width), ('y', height)):
        for quantity in AXES[axis]:
            if quantity in fields:
                pixels[quantity] = fields[quantity]
            elif f"n{quantity}" in fields:
                pixels[quantity] = fields[f"n{quantity}"] * size
    x1, x2 = resolve_span(*(pixels.get(quantity) for quantity in AXES['x']))
    y1, y2 = resolve_span(*(pixels.get(quantity) for quantity in AXES['y']))
    # integer pixel boxes; stops 6-digit normalized values drifting on every save
    return {
        'cls': cls,
        'x1': round(x1), 'y1': round(y1), 'x2': round(x2), 'y2': round(y2),
        'difficult': fields.get('difficult', 0),
    }


def resolve_delimiter(fmt: dict) -> str:
    # apply the delimiter setting to txt; csv is always comma-separated
    return fmt['delimiter'] if fmt['gt_file_ext'] == 'txt' else ','

def write_gt_file(path: Path, rows: list[list[str]], fmt: dict) -> None:
    delimiter = resolve_delimiter(fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        for row in rows:
            file.write(delimiter.join(row) + '\n')

def resolve_gt_path(image_path: Path, fmt: dict, gt_path_root: str|None=None) -> Path:
    # an absolute root replaces the image folder; a relative one goes inside it
    gt_dir = image_path.parent / (gt_path_root or '')
    name = image_path.parent.name if fmt['gt_merged'] else image_path.stem
    return gt_dir / f"{name}.{fmt['gt_file_ext']}"

def read_gt_file(path: Path, fmt: dict) -> list[list[str]]:
    if not path.is_file():
        return []
    delimiter = resolve_delimiter(fmt)
    rows = []
    # utf-8-sig also reads files saved with a byte order mark
    with open(path, 'r', encoding='utf-8-sig') as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(line.split() if delimiter == ' ' else line.split(delimiter))
    return rows
