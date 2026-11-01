# LiteLabel

Bounding-box labeling tool for images. Saves YOLO, RF-DETR, Pascal VOC or any custom txt/csv format.

### Download
[Latest releases](https://github.com/aj-peng/litelabel/releases/tag/v1.0)

Unzip and run `LiteLabel.exe` or `LiteLabel.app`, keeping `config.yml` in the same folder.

- **Windows:** on "Windows protected your PC", click **More info > Run anyway**.
- **macOS:** run `xattr -dr com.apple.quarantine path/to/LiteLabel` once, then open the app.

### Usage

| Action | How |
|---|---|
| Open folder | **Open Folder...** or Ctrl/Cmd+O |
| Draw / move / resize | drag on the image / a box / its edge |
| Delete box | Delete or Backspace |
| Previous / next image | `a` / `d` (saves automatically) |
| Save | Ctrl/Cmd+S |
| Zoom | scroll |

Formats, classes, hotkeys and box style are set in `config.yml`.

### Build

```bash
pip install -r requirements-dev.txt
pytest
python scripts/build.py   # writes dist/LiteLabel-<platform>.zip
```