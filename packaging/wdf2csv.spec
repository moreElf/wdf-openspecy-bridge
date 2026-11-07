# PyInstaller spec for the Windows desktop app. Build from the repo root:
#   pyinstaller packaging/wdf2csv.spec --noconfirm
# Output: dist/WDF2CSV/WDF2CSV.exe (a folder app; zip the WDF2CSV folder to share it).
# R is not bundled: identification uses an R + OpenSpecy install if one is found.

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is defined by PyInstaller
PKG = ROOT / "src" / "wdf_openspecy_bridge"

# An Anaconda-based Python keeps the DLLs of _tkinter, _ctypes, _ssl etc. in Library\bin,
# where PyInstaller does not look; without them the app dies on "import tkinter".
# A python.org Python has none of this and needs nothing extra.
CONDA_BIN = Path(sys.base_prefix) / "Library" / "bin"
CONDA_DLLS = ["tcl86t.dll", "tk86t.dll", "ffi.dll", "ffi-8.dll", "ffi-7.dll", "libcrypto-3-x64.dll",
              "libssl-3-x64.dll", "liblzma.dll", "libbz2.dll", "libexpat.dll", "zlib.dll"]
binaries = [(str(CONDA_BIN / dll), ".") for dll in CONDA_DLLS if (CONDA_BIN / dll).exists()]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "wdf2csv_app.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    # The R script is run by Rscript from the package folder, so ship it next to the modules.
    datas=[(str(PKG / "openspecy_match.R"), "wdf_openspecy_bridge")],
    excludes=["matplotlib", "pandas", "scipy", "PIL", "IPython", "pytest"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WDF2CSV",
    console=False,  # GUI app: no terminal window
)
coll = COLLECT(exe, a.binaries, a.datas, name="WDF2CSV")  # noqa: F821
