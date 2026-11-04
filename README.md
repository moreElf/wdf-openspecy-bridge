# wdf-openspecy-bridge

A local tool that converts Renishaw WiRE `.wdf` Raman spectra into CSV files you can load into [OpenSpecy](https://openanalysis.org/openspecy/). It runs on Windows and macOS.

- **Phase 1 (included):** `.wdf` → CSV, with a CLI (`wdf2csv`) and a small GUI (`wdf2csv-gui`). It reads files with Renishaw's open-source (Apache-2.0) Python reader [`renishaw-wdf`](https://pypi.org/project/renishaw-wdf/). The WiRE software itself is not needed. The output is a CSV that OpenSpecy can read, because OpenSpecy cannot open `.wdf` files and has no REST API.
- **Phase 2 (optional):** identifies each spectrum through the OpenSpecy **R package** (`read_any` → `filter_spec` (Raman) → `process_spec` → `match_spec(conform = TRUE)`) and writes the top-N library matches. This needs R. It does not use openspecy.org or any browser automation.

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
wdf2csv map.wdf --split                  # multi-spectrum file -> one long CSV per spectrum
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
- A multi-spectrum file (map or series) produces one `<name>.csv` in OpenSpecy's native wide format. Each row is a spectrum. The columns are integer wavenumbers, followed by `x,y,file_name`, where `x,y` are the stage positions (left blank if the file has none). This is the same layout that OpenSpecy's `write_spec()` produces. OpenSpecy only recognises the layout when the column names are integers. So if the point spacing is below about 1 cm⁻¹, which happens near 2000 cm⁻¹ in the sample, the spectra are linearly interpolated onto a 1 cm⁻¹ grid. Otherwise each wavenumber is simply rounded. With `--split` it writes long-format `<name>_0001.csv`, `<name>_0002.csv` and so on.
- The exit code is non-zero if any file fails. The remaining files are still converted.

### GUI

```bash
wdf2csv-gui
```

Add `.wdf` files, optionally choose an output folder, pick a header style, and press **Convert**.

## Phase 2: OpenSpecy identification (optional)

1. Install R ≥ 4.1 from https://cran.r-project.org/. Make sure `Rscript` is on PATH. On Windows the tool also looks in `C:\Program Files\R\R-*` and in the per-user location `%LOCALAPPDATA%\Programs\R\R-*`. For a per-user install without admin rights, run `winget install RProject.R --override "/VERYSILENT /CURRENTUSER"`.
2. In R, run `install.packages("OpenSpecy")` (CRAN 2.0.x).
3. Run:

```bash
wdf2csv data_folder/ -o out/ --match             # top 5 matches, "derivative" library
wdf2csv sample.wdf --match --library nobaseline --top-n 10
```

The first run downloads the OpenSpecy reference library through `get_lib()` (`derivative` is about 46 MB). It is cached inside the R package folder. Results go to `out/openspecy_matches.csv`, with columns `input_file, rank, match_val, spectrum_identity, material_class, …`. The GUI shows an "Identify with OpenSpecy" checkbox, but only when R is detected.

Only the Raman part of the library is used (`lib$raman` in OpenSpecy 2.x, `filter_spec` for older combined libraries). Each spectrum gets its own top N, sorted by `match_val` (Pearson correlation). Processing follows the OpenSpecy defaults for each library, and `match_spec(conform = TRUE)` then aligns each spectrum to the library axis:
- `derivative`: Savitzky–Golay smoothing with first derivative (poly 3, window 11), then normalise.
- `nobaseline`: baseline subtraction, then normalise.

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

- Only spectral intensities and wavenumbers are exported. Metadata such as the laser wavelength and the white-light image is not written to the CSV. Map stage positions are written only in the wide format.
- Map/wide output was tested with synthetic data built from the sample, including through OpenSpecy's `read_any` and `match_spec`. It has not been tested with a real map `.wdf`.
- Phase 2 was verified end to end with R 4.6.2 and OpenSpecy 2.0.3 on Windows, using both the `derivative` and `nobaseline` libraries. Other OpenSpecy versions may differ, so check `packageVersion("OpenSpecy")` if it fails. The test suite runs an R end-to-end test when Rscript is found and skips it otherwise.
- The match scores are only a screening aid. On the sample, the best `derivative` match scores about 0.42 (whewellite) and the best `nobaseline` match about 0.69 (phlogopite). These are low correlations, so check the spectra by eye before trusting an identification.
- File parsing depends on `renishaw-wdf`. Multitrack files export track 0 only.
