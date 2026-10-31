import re
import sys
from pathlib import Path

IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp')


def resolve_app_directory() -> Path:
    # the exe's folder when packaged, otherwise the repo root one level above this package
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # write a temporary file, then swap it in, so a failed save never leaves a half-written file
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(text, encoding='utf-8')
        temp_path.replace(path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def natural_key(path: Path) -> list[str | int]:
    # split digits from text so numbers compare by value: img2 comes before img10
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', path.name)]


def list_images(folder: Path) -> list[Path]:
    images = [
        path for path in folder.iterdir()
        # skip hidden files, e.g. the ._dog.jpg copies macOS leaves on external drives
        if path.is_file() and not path.name.startswith('.') and path.suffix.lower() in IMAGE_EXTS
    ]
    return sorted(images, key=natural_key)
