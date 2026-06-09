# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_dir = Path.cwd()
python_dir = Path(r"C:\Users\sinzo\AppData\Local\Programs\Python\Python313")
tcl_root = python_dir / "tcl"
tkdnd_root = python_dir / "Lib" / "site-packages" / "tkinterdnd2" / "tkdnd"
ffmpeg_bin = Path(r"C:\ffmpeg-7.1.1-essentials_build\bin")

datas = [
    (str(project_dir / "gzya5-3b5gl-001.ico"), "."),
    (str(tcl_root), "tcl"),
]

if tkdnd_root.exists():
    datas.append((str(tkdnd_root), "tkinterdnd2/tkdnd"))

datas += collect_data_files("tkinterdnd2")

binaries = [
    (str(ffmpeg_bin / "ffmpeg.exe"), "."),
    (str(ffmpeg_bin / "ffprobe.exe"), "."),
    (str(python_dir / "DLLs" / "tcl86t.dll"), "."),
    (str(python_dir / "DLLs" / "tk86t.dll"), "."),
]

hiddenimports = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.simpledialog",
    "tkinterdnd2",
    "tkinterdnd2.TkinterDnD",
]

hiddenimports += collect_submodules("tkinterdnd2")

a = Analysis(
    ["main.py"],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_dir / "pyi_rth_tk_env.py")],
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
    name="小丸工具箱粉丝致敬版 v1.1.2",
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
    icon=[str(project_dir / "gzya5-3b5gl-001.ico")],
)
