"""Build LiteLabel with PyInstaller and put config.yml next to the executable."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_pyinstaller(spec: Path) -> None:
    # the same interpreter as this script, so the build uses this venv's packages
    subprocess.run([sys.executable, '-m', 'PyInstaller', str(spec), '--noconfirm'], cwd=ROOT, check=True)


def copy_config(app_dir: Path) -> Path:
    target = app_dir / "config.yml"
    shutil.copy2(ROOT / "config.yml", target)
    return target


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    run_pyinstaller(ROOT / "LiteLabel.spec")
    print(f"Copied {copy_config(ROOT / 'dist' / 'LiteLabel')}")
    # on macOS the build also makes LiteLabel.app, which reads the config next to the .app
    if (ROOT / "dist" / "LiteLabel.app").exists():
        print(f"Copied {copy_config(ROOT / 'dist')}")


if __name__ == "__main__":
    main()
