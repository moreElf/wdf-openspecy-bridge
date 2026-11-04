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


def run_match(
    csv_files: list[Path],
    out_csv: Path,
    library: str = "derivative",
    top_n: int = 5,
) -> Path:
    """Match CSV spectra against an OpenSpecy library and write top hits to out_csv.

    Raises RuntimeError if Rscript is not available or the R script fails.
    """
    rscript = find_rscript()
    if rscript is None:
        raise RuntimeError(
            "Rscript not found. Install R and the OpenSpecy package to enable matching (see README, Phase 2)."
        )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cmd = [rscript, str(R_SCRIPT), str(out_csv), library, str(top_n), *map(str, csv_files)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"OpenSpecy match failed:\n{proc.stderr.strip()}")
    return out_csv
