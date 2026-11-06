"""Optional Phase 2: identify spectra with the OpenSpecy R package via Rscript."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

R_SCRIPT = Path(__file__).with_name("openspecy_match.R")


def find_rscript() -> str | None:
    """Locate Rscript on PATH, or in the standard Windows install locations."""
    found = shutil.which("Rscript")
    if found:
        return found
    if os.name == "nt":
        bases = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "R",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "R",  # per-user install
        ]
        for base in bases:
            candidates = sorted(base.glob("R-*/bin/Rscript.exe"), reverse=True)
            if candidates:
                return str(candidates[0])
    return None


PRESETS = ("web", "legacy")
TRANSFORMATIONS = ("derivative", "nobaseline")
LIB_TYPES = ("medoid", "full")
SPECTRUM_TYPES = ("all", "raman", "ftir", "nir")

RESULT_SUFFIX = "-OpenSpecy"


def result_path(csv_file: Path) -> Path:
    """Where the matches for one input CSV go: ``<stem>-OpenSpecy.csv`` next to it."""
    return csv_file.with_name(f"{csv_file.stem}{RESULT_SUFFIX}.csv")


def run_match(
    csv_files: list[Path],
    library: str = "derivative",
    top_n: int = 5,
    preset: str = "web",
    lib_type: str = "medoid",
    spectrum_type: str = "all",
) -> list[Path]:
    """Match CSV spectra against an OpenSpecy library, one result file per input.

    Each input ``<stem>.csv`` gets ``<stem>-OpenSpecy.csv`` in the same folder (see
    ``result_path``); a wide CSV with many spectra gets one file holding all of them.
    The library is loaded once for the whole batch. Returns the result paths, in input order.

    ``preset="web"`` reproduces the openspecy.org defaults; ``"legacy"`` is the
    pre-0.2 pipeline (full Raman library). ``lib_type`` and ``spectrum_type``
    only apply to the web preset.

    Raises RuntimeError if Rscript is not available or the R script fails.
    """
    for name, value, allowed in (
        ("preset", preset, PRESETS),
        ("library", library, TRANSFORMATIONS),
        ("lib_type", lib_type, LIB_TYPES),
        ("spectrum_type", spectrum_type, SPECTRUM_TYPES),
    ):
        if value not in allowed:
            raise ValueError(f"{name} must be one of {allowed}, got {value!r}")
    rscript = find_rscript()
    if rscript is None:
        raise RuntimeError(
            "Rscript not found. Install R and the OpenSpecy package to enable matching (see README, Phase 2)."
        )
    outs = [result_path(Path(f)) for f in csv_files]
    pairs = [str(p) for f, out in zip(csv_files, outs, strict=True) for p in (f, out)]
    cmd = [rscript, str(R_SCRIPT), preset, library, lib_type, spectrum_type, str(top_n), *pairs]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"OpenSpecy match failed:\n{proc.stderr.strip()}")
    return outs
