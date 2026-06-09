import os
import sys
from pathlib import Path


def _set_tk_env():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    tcl_dir = base / "tcl"
    tk_dir = tcl_dir / "tk8.6"
    tcl_lib_dir = tcl_dir / "tcl8.6"
    if tk_dir.exists():
        os.environ["TK_LIBRARY"] = str(tk_dir)
    if tcl_lib_dir.exists():
        os.environ["TCL_LIBRARY"] = str(tcl_lib_dir)


_set_tk_env()
