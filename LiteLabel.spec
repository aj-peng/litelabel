# -*- mode: python ; coding: utf-8 -*-
import sys

# EXE takes the .ico on Windows only; BUNDLE (macOS) converts the same .ico to .icns with Pillow
ICON = 'assets/app.ico' if sys.platform == 'win32' else None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LiteLabel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LiteLabel',
)
app = BUNDLE(
    coll,
    name='LiteLabel.app',
    icon='assets/app.ico',
    bundle_identifier=None,
)