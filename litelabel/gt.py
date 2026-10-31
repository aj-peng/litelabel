import os
import xml.etree.ElementTree as ET
from pathlib import Path

from litelabel.config import AXES
from litelabel.utility import write_atomic

VOC_CORNERS = (('xmin', 'x1'), ('ymin', 'y1'), ('xmax', 'x2'), ('ymax', 'y2'))


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


def format_value(value: str | int | float) -> str:
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
        start: float | None,
        end: float | None,
        center: float | None,
        size: float | None
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
    write_atomic(path, ''.join(delimiter.join(row) + '\n' for row in rows))


def resolve_gt_path(image_path: Path, fmt: dict, gt_path_root: str | None = None) -> Path:
    gt_dir = Path(os.path.normpath(image_path.parent / (gt_path_root or '')))
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


def load_boxes(
        image_path: Path,
        width: int,
        height: int,
        fmt: dict,
        classes: list[str],
        gt_path_root: str | None = None
) -> list[dict]:
    gt_path = resolve_gt_path(image_path, fmt, gt_path_root)
    try:
        if fmt['gt_file_ext'] == 'xml':
            entries = read_voc_file(gt_path)
        else:
            entries = [parse_row(row, fmt['data_fmt']) for row in read_gt_file(gt_path, fmt)]
        # a merged file holds every image's rows; keep only this image's
        if fmt['gt_merged']:
            entries = [fields for fields in entries if fields['iname'] == image_path.name]
        return [build_box(fields, width, height, classes) for fields in entries]
    except ValueError as error:
        raise ValueError(f"{gt_path}: {error}") from error


def save_boxes(
        image_path: Path,
        boxes: list[dict],
        width: int,
        height: int,
        fmt: dict,
        classes: list[str],
        gt_path_root: str | None = None
) -> None:
    for box in boxes:
        if not 0 <= box['cls'] < len(classes):
            raise ValueError(f"Class id {box['cls']} out of range for {len(classes)} classes")
    gt_path = resolve_gt_path(image_path, fmt, gt_path_root)
    if fmt['gt_file_ext'] == 'xml':
        write_voc_file(gt_path, build_voc(image_path, boxes, width, height, classes))
        return
    rows = [format_row(compute_fields(box, width, height, classes, image_path.name), fmt['data_fmt']) for box in boxes]
    if fmt['gt_merged']:
        # replace this image's rows, keep every other image's, ordered by image name
        index = fmt['data_fmt'].index('iname')
        others = [row for row in read_gt_file(gt_path, fmt) if row[index].strip() != image_path.name]
        rows = sorted(others + rows, key=lambda row: row[index].strip())
    write_gt_file(gt_path, rows, fmt)


def build_voc(
        image_path: Path,
        boxes: list[dict],
        width: int,
        height: int,
        classes: list[str],
        depth: int = 3
) -> ET.Element:
    annotation = ET.Element('annotation')
    ET.SubElement(annotation, 'folder').text = image_path.parent.name
    ET.SubElement(annotation, 'filename').text = image_path.name
    size = ET.SubElement(annotation, 'size')
    for tag, value in (('width', width), ('height', height), ('depth', depth)):
        ET.SubElement(size, tag).text = str(value)
    for box in boxes:
        fields = compute_fields(box, width, height, classes, image_path.name)
        obj = ET.SubElement(annotation, 'object')
        ET.SubElement(obj, 'name').text = fields['cname']
        ET.SubElement(obj, 'difficult').text = format_value(fields['difficult'])
        bndbox = ET.SubElement(obj, 'bndbox')
        for tag, key in VOC_CORNERS:
            ET.SubElement(bndbox, tag).text = format_value(fields[key])
    return annotation


def write_voc_file(path: Path, annotation: ET.Element) -> None:
    ET.indent(annotation)
    write_atomic(path, ET.tostring(annotation, encoding='unicode') + '\n')


def read_voc_file(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        annotation = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"invalid XML: {error}") from error
    objects = []
    for number, obj in enumerate(annotation.findall('object'), start=1):
        name = obj.findtext('name')
        corners = [obj.findtext(f"bndbox/{tag}") for tag, _ in VOC_CORNERS]
        if name is None or None in corners:
            raise ValueError(f"object {number} is missing its name or a bndbox value")
        try:
            objects.append({
                'cname': name.strip(),
                'difficult': int(obj.findtext('difficult') or 0),
                **{key: float(value) for (_, key), value in zip(VOC_CORNERS, corners)},
            })
        except ValueError as error:
            raise ValueError(f"object {number}: {error}") from error
    return objects
