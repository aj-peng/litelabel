import sys
from pathlib import Path

def resolve_app_directory() -> Path:
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