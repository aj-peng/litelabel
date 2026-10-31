"""Build LiteLabel with PyInstaller, put config.yml next to the executable and zip it for a release."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

def run_pyinstaller(spec: Path) -> None:
    # the same interpreter as this script, so the build uses this venv's packages
    subprocess.run([sys.executable, '-m', 'PyInstaller', str(spec), '--noconfirm'], cwd=ROOT, check=True)

def copy_config(app_dir: Path) -> Path:
    target = app_dir / "config.yml"
    shutil.copy2(ROOT / "config.yml", target)
    return target

def resolve_platform_name() -> str:
    return {'darwin': "macos", 'win32': "windows"}.get(sys.platform, sys.platform)

def make_zip() -> Path:
    archive = DIST / f"LiteLabel-{resolve_platform_name()}.zip"
    archive.unlink(missing_ok=True)
    if sys.platform == 'darwin':
        staging = DIST / "release" / "LiteLabel"
        shutil.rmtree(staging.parent, ignore_errors=True)
        staging.mkdir(parents=True)
        shutil.copytree(DIST / "LiteLabel.app", staging / "LiteLabel.app", symlinks=True)
        copy_config(staging)
        subprocess.run(['ditto', '-c', '-k', '--keepParent', str(staging), str(archive)], check=True)
    else:
        shutil.make_archive(str(archive.with_suffix('')), 'zip', root_dir=DIST, base_dir="LiteLabel")
    return archive

def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    run_pyinstaller(ROOT / "LiteLabel.spec")
    print(f"Copied {copy_config(DIST / 'LiteLabel')}")
    if (DIST / "LiteLabel.app").exists():
        print(f"Copied {copy_config(DIST)}")
    print(f"Created {make_zip()}")

if __name__ == "__main__":
    main()