"""Convert Renishaw .wdf files to OpenSpecy-friendly CSV using renishawWiRE."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from renishawWiRE import WDFReader

HeaderStyle = Literal["standard", "hash"]

HEADERS: dict[HeaderStyle, tuple[str, str]] = {
    "standard": ("wavenumber", "intensity"),
    "hash": ("#Wave", "#Intensity"),
}


@dataclass
class WdfData:
    source: Path
    title: str
    measurement_type: str
    wavenumber: NDArray[np.float64]
    # shape (n_spectra, n_points), aligned with `wavenumber`
    intensities: NDArray[np.float64]


def read_wdf(path: str | Path) -> WdfData:
    """Read a .wdf file and return spectra sorted by ascending wavenumber."""
    path = Path(path)
    reader = WDFReader(str(path))
    try:
        x = np.asarray(reader.xdata, dtype=np.float64)
        y = np.asarray(reader.spectra, dtype=np.float64).reshape(-1, x.size)
        title = str(reader.title)
        mtype = str(getattr(reader.measurement_type, "name", reader.measurement_type))
    finally:
        reader.close()
    order = np.argsort(x)
    return WdfData(path, title, mtype, x[order], y[:, order])


def write_spectrum_csv(
    out_path: Path,
    wavenumber: NDArray[np.float64],
    intensity: NDArray[np.float64],
    header: HeaderStyle = "standard",
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS[header])
        for wn, it in zip(wavenumber, intensity, strict=True):
            w.writerow((f"{wn:.4f}", f"{it:.6g}"))


def write_wide_csv(out_path: Path, data: WdfData) -> None:
    """One wavenumber column plus one intensity column per spectrum."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = data.intensities.shape[0]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["wavenumber", *(f"intensity_{i + 1:04d}" for i in range(n))])
        for j, wn in enumerate(data.wavenumber):
            w.writerow([f"{wn:.4f}", *(f"{v:.6g}" for v in data.intensities[:, j])])


def convert_file(
    wdf_path: str | Path,
    out_dir: str | Path | None = None,
    header: HeaderStyle = "standard",
    wide: bool = False,
) -> list[Path]:
    """Convert one .wdf file. Returns the written CSV paths.

    Single-spectrum files produce ``<stem>.csv``. Multi-spectrum files (maps,
    series) produce ``<stem>_0001.csv`` ... or, with ``wide=True``, a single
    ``<stem>_wide.csv``.
    """
    data = read_wdf(wdf_path)
    dest = Path(out_dir) if out_dir is not None else data.source.parent
    stem = data.source.stem
    n = data.intensities.shape[0]

    if n == 1:
        out = dest / f"{stem}.csv"
        write_spectrum_csv(out, data.wavenumber, data.intensities[0], header)
        return [out]
    if wide:
        out = dest / f"{stem}_wide.csv"
        write_wide_csv(out, data)
        return [out]
    outs = []
    for i in range(n):
        out = dest / f"{stem}_{i + 1:04d}.csv"
        write_spectrum_csv(out, data.wavenumber, data.intensities[i], header)
        outs.append(out)
    return outs


def collect_inputs(paths: list[str | Path]) -> list[Path]:
    """Expand directories to the .wdf files they contain (non-recursive)."""
    found: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            found.extend(sorted(q for q in p.iterdir() if q.suffix.lower() == ".wdf"))
        else:
            found.append(p)
    return found
