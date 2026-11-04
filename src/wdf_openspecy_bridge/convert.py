"""Convert Renishaw .wdf files to OpenSpecy-friendly CSV using Renishaw's renishaw-wdf."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from wdf.origin import WdfDataType
from wdf.wdf import Wdf

HeaderStyle = Literal["standard", "hash"]

HEADERS: dict[HeaderStyle, tuple[str, str]] = {
    "standard": ("wavenumber", "intensity"),
    "hash": ("#Wave", "#Intensity"),
}


@dataclass
class WdfData:
    source: Path
    title: str
    wavenumber: NDArray[np.float64]
    # shape (n_spectra, n_points), aligned with `wavenumber`
    intensities: NDArray[np.float64]
    # stage positions per spectrum, or None when the file has no spatial origin
    x: NDArray[np.float64] | None = None
    y: NDArray[np.float64] | None = None


def _origin(w: Wdf, kind: WdfDataType, n: int) -> NDArray[np.float64] | None:
    try:
        origin = w.origins.get(kind)
    except EOFError:
        return None
    if origin is None:
        return None
    return np.array([float(origin[i]) for i in range(n)], dtype=np.float64)


def read_wdf(path: str | Path) -> WdfData:
    """Read a .wdf file and return spectra sorted by ascending wavenumber."""
    path = Path(path)
    with Wdf(str(path)) as w:  # type: ignore[no-untyped-call]
        n = len(w)
        x = np.asarray(w.xlist(), dtype=np.float64)
        raw = w.spectrum(slice(0, n)) if n > 1 else (w.spectrum(0),)
        y = np.asarray(raw, dtype=np.float64).reshape(n, x.size)
        title = str(w.hdr.title)
        pos_x = _origin(w, WdfDataType.Spatial_X, n)
        pos_y = _origin(w, WdfDataType.Spatial_Y, n)
    order = np.argsort(x)
    return WdfData(path, title, x[order], y[:, order], pos_x, pos_y)


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


def wavenumber_labels(wavenumber: NDArray[np.float64]) -> list[str]:
    """Integer column names as in OpenSpecy's wide format; decimals if rounding collides."""
    rounded = np.rint(wavenumber).astype(np.int64)
    if np.unique(rounded).size == rounded.size:
        return [str(v) for v in rounded]
    return [f"{v:.4f}" for v in wavenumber]


def write_wide_csv(out_path: Path, data: WdfData) -> None:
    """OpenSpecy native wide CSV: one row per spectrum, wavenumber columns, then x,y,file_name."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = data.intensities.shape[0]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([*wavenumber_labels(data.wavenumber), "x", "y", "file_name"])
        for i in range(n):
            px = f"{data.x[i]:.4f}" if data.x is not None else ""
            py = f"{data.y[i]:.4f}" if data.y is not None else ""
            w.writerow([*(f"{v:.6g}" for v in data.intensities[i]), px, py, data.source.name])


def convert_file(
    wdf_path: str | Path,
    out_dir: str | Path | None = None,
    header: HeaderStyle = "standard",
    split: bool = False,
) -> list[Path]:
    """Convert one .wdf file. Returns the written CSV paths.

    Single-spectrum files produce ``<stem>.csv`` (wavenumber,intensity). Multi-spectrum
    files (maps, series) produce one OpenSpecy wide ``<stem>.csv``, or with ``split=True``
    one long-format ``<stem>_0001.csv`` ... per spectrum.
    """
    data = read_wdf(wdf_path)
    dest = Path(out_dir) if out_dir is not None else data.source.parent
    stem = data.source.stem
    n = data.intensities.shape[0]

    if n == 1:
        out = dest / f"{stem}.csv"
        write_spectrum_csv(out, data.wavenumber, data.intensities[0], header)
        return [out]
    if not split:
        out = dest / f"{stem}.csv"
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
