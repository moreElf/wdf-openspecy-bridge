"""Everything that differs between Windows, macOS and Linux, in one place.

Each function takes an optional ``platform`` (a ``sys.platform`` value) so the
branches for other operating systems can be unit-tested on any machine.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# Where the CRAN installer, Homebrew (Apple Silicon / Intel) and Linux distributions put Rscript.
# A macOS .app started from Finder gets a minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin), so
# shutil.which() does not see these; they have to be probed explicitly.
MACOS_RSCRIPT_PATHS = (
    "/Library/Frameworks/R.framework/Resources/bin/Rscript",  # CRAN .pkg installer
    "/opt/homebrew/bin/Rscript",  # Homebrew on Apple Silicon
    "/usr/local/bin/Rscript",  # Homebrew on Intel, or the CRAN installer's symlink
)
LINUX_RSCRIPT_PATHS = ("/usr/bin/Rscript", "/usr/local/bin/Rscript")


def _platform(platform: str | None) -> str:
    return sys.platform if platform is None else platform


def is_windows(platform: str | None = None) -> bool:
    return _platform(platform) == "win32"


def is_macos(platform: str | None = None) -> bool:
    return _platform(platform) == "darwin"


def rscript_candidates(platform: str | None = None, environ: Mapping[str, str] | None = None) -> list[Path]:
    """Standard Rscript install locations to try when Rscript is not on PATH.

    On Windows, newest version first, from ``Program Files\\R\\R-*`` and the per-user
    ``%LOCALAPPDATA%\\Programs\\R\\R-*``. The candidates are not checked for existence,
    except that Windows globs only return folders that are there.
    """
    env = os.environ if environ is None else environ
    if is_windows(platform):
        bases = [Path(env.get("ProgramFiles", r"C:\Program Files")) / "R"]
        if env.get("LOCALAPPDATA"):
            bases.append(Path(env["LOCALAPPDATA"]) / "Programs" / "R")  # per-user install
        found: list[Path] = []
        for base in bases:
            found.extend(sorted(base.glob("R-*/bin/Rscript.exe"), reverse=True))
        return found
    if is_macos(platform):
        return [Path(p) for p in MACOS_RSCRIPT_PATHS]
    return [Path(p) for p in LINUX_RSCRIPT_PATHS]


def background_process_kwargs(platform: str | None = None) -> dict[str, Any]:
    """Extra ``subprocess.run`` arguments for running a console program from the GUI.

    On Windows, Rscript is a console program and would flash a terminal window from the
    windowed app, so it gets ``CREATE_NO_WINDOW``. Other systems need nothing.
    """
    if is_windows(platform):
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def wdf_filetypes(platform: str | None = None) -> list[tuple[str, str]]:
    """``filetypes`` for the Tk open dialog.

    ``*.*`` means "all files" on Windows, but on macOS (and Linux) it only matches names
    that contain a dot, so "all files" there is ``*``.
    """
    all_files = "*.*" if is_windows(platform) else "*"
    return [("Renishaw WiRE", "*.wdf"), ("All files", all_files)]
