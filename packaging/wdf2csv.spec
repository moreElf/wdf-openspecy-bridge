# PyInstaller spec for the desktop app (Windows and macOS). Build from the repo root:
#   pyinstaller packaging/wdf2csv.spec --noconfirm
# PyInstaller cannot cross-compile: build the Windows app on Windows and the Mac app on a Mac
# (see docs/build-macos.md and packaging/build_macos.sh).
# Output:
#   Windows: dist/WDF2CSV/WDF2CSV.exe (a folder app; zip the WDF2CSV folder to share it)
#   macOS:   dist/WDF2CSV.app        (zip it with `ditto -c -k --keepParent`)
# R is not bundled: identification uses an R + OpenSpecy install if one is found.

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is defined by PyInstaller
PKG = ROOT / "src" / "wdf_openspecy_bridge"
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

binaries = []
if IS_WINDOWS:
    # An Anaconda-based Python keeps the DLLs of _tkinter, _ctypes, _ssl etc. in Library\bin,
    # where PyInstaller does not look; without them the app dies on "import tkinter".
    # A python.org Python has none of this and needs nothing extra.
    CONDA_BIN = Path(sys.base_prefix) / "Library" / "bin"
    CONDA_DLLS = ["tcl86t.dll", "tk86t.dll", "ffi.dll", "ffi-8.dll", "ffi-7.dll", "libcrypto-3-x64.dll",
                  "libssl-3-x64.dll", "liblzma.dll", "libbz2.dll", "libexpat.dll", "zlib.dll"]
    binaries = [(str(CONDA_BIN / dll), ".") for dll in CONDA_DLLS if (CONDA_BIN / dll).exists()]

# macOS architecture. "arm64" (Apple Silicon) by default rather than "universal2": a
# universal2 build needs every compiled dependency as a fat binary, but numpy publishes
# separate arm64 and x86_64 wheels, so universal2 fails. Intel Macs: set
# WDF2CSV_TARGET_ARCH=x86_64 and build on an Intel Mac (or an x86_64 Python under Rosetta).
TARGET_ARCH = os.environ.get("WDF2CSV_TARGET_ARCH", "arm64") if IS_MACOS else None

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "wdf2csv_app.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    # The R script is run by Rscript from the package folder, so ship it next to the modules.
    # In a .app PyInstaller puts it in Contents/Resources and links it from Contents/Frameworks,
    # where the frozen modules' __file__ points, so Path(__file__).with_name() still finds it.
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
    console=False,  # GUI app: no terminal window (= --windowed)
    argv_emulation=False,  # files are picked in the dialog, not dropped on the icon
    target_arch=TARGET_ARCH,
    codesign_identity=None,  # macOS: ad-hoc signature only (required to run on arm64)
)
coll = COLLECT(exe, a.binaries, a.datas, name="WDF2CSV")  # noqa: F821

if IS_MACOS:
    app = BUNDLE(  # noqa: F821
        coll,
        name="WDF2CSV.app",
        icon=None,
        bundle_identifier="io.github.moreelf.wdf2csv",
        version="0.1.0",
        info_plist={
            "CFBundleName": "WDF2CSV",
            "CFBundleDisplayName": "WDF2CSV",
            "NSHighResolutionCapable": True,  # sharp text on Retina screens
            "LSMinimumSystemVersion": "11.0",  # first macOS release for Apple Silicon
        },
    )
