# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_dir = Path.cwd()
python_dir = Path(r"C:\Users\sinzo\AppData\Local\Programs\Python\Python313")
tcl_root = python_dir / "tcl"
ffmpeg_bin = Path(r"C:\ffmpeg-7.1.1-essentials_build\bin")
tkdnd_root = python_dir / "Lib" / "site-packages" / "tkinterdnd2" / "tkdnd"

datas = [
    (str(project_dir / "gzya5-3b5gl-001.ico"), "."),
    (str(tcl_root / "tcl8.6"), "_tcl_data"),
    (str(tcl_root / "tk8.6"), "_tk_data"),
]

if (tcl_root / "tcl8").exists():
    datas.append((str(tcl_root / "tcl8"), "tcl8"))

if tkdnd_root.exists():
    datas.append((str(tkdnd_root), "tkinterdnd2/tkdnd"))

datas += collect_data_files("tkinterdnd2")

binaries = [
    (str(ffmpeg_bin / "ffmpeg.exe"), "."),
    (str(ffmpeg_bin / "ffprobe.exe"), "."),
    (str(python_dir / "DLLs" / "_tkinter.pyd"), "."),
    (str(python_dir / "DLLs" / "tcl86t.dll"), "."),
    (str(python_dir / "DLLs" / "tk86t.dll"), "."),
]

hiddenimports = [
    "tkinter",
    "_tkinter",
    "tkinterdnd2",
    "tkinterdnd2.TkinterDnD",
]
hiddenimports += collect_submodules("tkinter")
hiddenimports += collect_submodules("tkinterdnd2")

a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(project_dir / "hooks")],
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
    name="小丸工具箱粉丝致敬版 v1.1.2 onedir",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(project_dir / "gzya5-3b5gl-001.ico")],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="小丸工具箱粉丝致敬版 v1.1.2 onedir",
)
