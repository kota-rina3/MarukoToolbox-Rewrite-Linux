# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('C:\\ffmpeg-7.1.1-essentials_build\\bin\\ffmpeg.exe', '.'), ('C:\\ffmpeg-7.1.1-essentials_build\\bin\\ffprobe.exe', '.')],
    datas=[('gzya5-3b5gl-001.ico', '.')],
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
    a.binaries,
    a.datas,
    [],
    name='小丸工具箱粉丝致敬版 v1.1.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['gzya5-3b5gl-001.ico'],
)
