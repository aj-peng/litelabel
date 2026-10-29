from litelabel.utility import list_images

def test_list_images_filters_and_sorts(tmp_path):
    for name in ["frame10.jpg", "frame2.jpg", "Frame1.PNG", "frame2.txt", "._frame3.jpg", "notes.md"]:
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "frames.jpg").mkdir()
    assert [path.name for path in list_images(tmp_path)] == ["Frame1.PNG", "frame2.jpg", "frame10.jpg"]

def test_list_images_empty(tmp_path):
    assert list_images(tmp_path) == []