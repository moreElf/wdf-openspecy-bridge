# wdf-openspecy-bridge

A local tool that converts Renishaw WiRE `.wdf` Raman spectra into CSV files you can load into [OpenSpecy](https://openanalysis.org/openspecy/). It runs on Windows and macOS.

- **Phase 1 (included):** `.wdf` → CSV, with a CLI (`wdf2csv`) and a small GUI (`wdf2csv-gui`). It reads files with the open-source [renishawWiRE](https://github.com/alchem0x2A/py-wdf-reader) `WDFReader`. Renishaw's WiRE software is not needed.
- **Phase 2 (optional):** identifies each spectrum through the OpenSpecy **R package** (`read_any` → `process_spec` → `match_spec`) and writes the top-N library matches. This needs R. It does not use openspecy.org or any browser automation.

## Install

Requires Python ≥ 3.10.

```bash
git clone <this repo> && cd wdf-openspecy-bridge
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS: source .venv/bin/activate
pip install -e .            # add ".[dev]" for tests/lint
```

The GUI uses Tkinter. It ships with the python.org and Anaconda installers. On Homebrew Python, run `brew install python-tk`.

## Usage

### CLI

```bash
wdf2csv sample.wdf                       # writes sample.csv next to the input
wdf2csv a.wdf b.wdf -o out/              # several files at once
wdf2csv data_folder/ -o out/             # every .wdf in a folder (not recursive)
wdf2csv sample.wdf --header hash         # header #Wave,#Intensity instead of wavenumber,intensity
wdf2csv map.wdf --wide                   # multi-spectrum file -> one wide CSV
```

Output format (default):

```csv
wavenumber,intensity
301.0771,7.50701
302.3633,49.311
...
```

- Rows are sorted by ascending wavenumber. WiRE stores them in descending order.
- A single-spectrum file produces `<name>.csv`.
- A multi-spectrum file (map or series) produces one file per spectrum, `<name>_0001.csv`, `<name>_0002.csv` and so on. With `--wide` it produces a single `<name>_wide.csv` that has one wavenumber column plus `intensity_0001…`.
- The exit code is non-zero if any file fails. The remaining files are still converted.

### GUI

```bash
wdf2csv-gui
```

Add `.wdf` files, optionally choose an output folder, pick a header style, and press **Convert**.

## Phase 2: OpenSpecy identification (optional)

1. Install R ≥ 4.1 from https://cran.r-project.org/. Make sure `Rscript` is on PATH. On Windows the tool also finds `C:\Program Files\R\R-*\bin\Rscript.exe`.
2. In R, run `install.packages("OpenSpecy")`.
3. Run:

```bash
wdf2csv data_folder/ -o out/ --match             # top 5 matches, "derivative" library
wdf2csv sample.wdf --match --library nobaseline --top-n 10
```

The first run downloads the OpenSpecy reference library through `get_lib()`. This is a large download, and it is cached afterwards. Results go to `out/openspecy_matches.csv`, with columns `input_file, rank, match_val, spectrum_identity, material_class, …`. The GUI shows an "Identify with OpenSpecy" checkbox, but only when R is detected.

Processing follows the OpenSpecy defaults for each library:
- `derivative`: conform to the library wavenumbers, Savitzky–Golay smoothing with first derivative (poly 3, window 11), then normalise.
- `nobaseline`: conform, baseline subtraction, then normalise.

The R script is `src/wdf_openspecy_bridge/openspecy_match.R`. You can also run it directly:
`Rscript openspecy_match.R out.csv derivative 5 in1.csv in2.csv`.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy
```

`tests/fixtures/1013-lens5x-fit-pinhole-01.wdf` is a real single-spectrum sample (1555 points, about 301–2001 cm⁻¹).

## Limitations

- Only spectral intensities and wavenumbers are exported. Metadata such as the laser wavelength, map coordinates and the white-light image is not written to the CSV. Map positions are available through `WDFReader.xpos/ypos` if you need them.
- Map support covers splitting into per-spectrum CSVs and wide CSV. It was tested with synthetic data only, because no map `.wdf` sample was available.
- Phase 2 targets OpenSpecy ≥ 1.0. It has not been run end-to-end in CI or on the author's machine because R was not installed there. The OpenSpecy API changed between 0.x and 1.x, so check `packageVersion("OpenSpecy")` if it fails.
- File parsing depends on renishawWiRE. Very new or unusual WiRE file versions may not be supported.
