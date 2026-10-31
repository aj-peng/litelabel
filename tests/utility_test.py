import sys
from pathlib import Path

from litelabel.utility import list_images, resolve_app_directory, write_atomic


# resolve_app_directory

def test_app_directory_contains_main():
    assert (resolve_app_directory() / "main.py").exists()


def test_app_directory_when_packaged(monkeypatch):
    # fake a PyInstaller build; raising=False because sys.frozen doesn't exist normally
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', "/fake/dist/LiteLabel/LiteLabel.exe")
    assert resolve_app_directory() == Path("/fake/dist/LiteLabel").resolve()


def test_app_directory_in_mac_app_bundle(monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', "/fake/dist/LiteLabel.app/Contents/MacOS/LiteLabel")
    assert resolve_app_directory() == Path("/fake/dist").resolve()


# write_atomic

def test_write_atomic_creates_folders(tmp_path):
    path = tmp_path / "labels" / "dog.txt"
    write_atomic(path, "0 0.5 0.5 0.1 0.1\n")
    assert path.read_text(encoding='utf-8') == "0 0.5 0.5 0.1 0.1\n"
    assert list(path.parent.iterdir()) == [path]


# list_images

def test_list_images_filters_and_sorts(tmp_path):
    # out-of-order numbers, an uppercase extension, a GT file, a macOS hidden file and a folder named like an image
    for name in ["frame10.jpg", "frame2.jpg", "Frame1.PNG", "frame2.txt", "._frame3.jpg", "notes.md"]:
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "frames.jpg").mkdir()
    assert [path.name for path in list_images(tmp_path)] == ["Frame1.PNG", "frame2.jpg", "frame10.jpg"]


def test_list_images_empty(tmp_path):
    assert list_images(tmp_path) == []
