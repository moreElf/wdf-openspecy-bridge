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
- Every output is named after its input, so a batch never mixes files up. Running the same input again replaces its own outputs and nothing else.
- If two inputs in one batch would write the same name, the second is reported as `FAIL` and skipped instead of overwriting the first. This happens with `a/x.wdf` and `b/x.wdf` going to one `-o` folder; letter case is ignored, as on Windows and macOS. Convert such files into separate folders.
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
wdf2csv data_folder/ -o out/ --match                          # openspecy.org defaults, top 5
wdf2csv sample.wdf --match --spectrum-type raman              # Raman references only
wdf2csv sample.wdf --match --lib-type full --top-n 10         # full library instead of medoids
wdf2csv sample.wdf --match --preset legacy                    # pipeline used before v0.2
```

The first run downloads the selected OpenSpecy reference library through `get_lib()` (`medoid_derivative` is about 5 MB; the full `derivative` library is about 46 MB). It is cached inside the R package folder.

Each converted CSV gets its own result file, named after it and written next to it, with columns `input_file, rank, match_val, material_class, spectrum_identity, spectrum_type, organization, …`. Each spectrum gets its own top N, sorted by `match_val` (Pearson correlation).

| Input | Converted CSV | Result |
|---|---|---|
| `16GF-A-01.wdf` (one spectrum) | `16GF-A-01.csv` | `16GF-A-01-OpenSpecy.csv` |
| `map.wdf` (many spectra) | `map.csv` (wide) | `map-OpenSpecy.csv`, all spectra together; `object_id` tells them apart |
| `map.wdf` with `--split` | `map_0001.csv`, `map_0002.csv`, … | `map_0001-OpenSpecy.csv`, `map_0002-OpenSpecy.csv`, … |

A batch of several files produces one result file per CSV. The reference library is still loaded only once. Re-running an input replaces only its own result file.

The console log also shows the top 3 matches of each spectrum, whatever `--top-n` is set to; the result file still holds all N:

```text
$ wdf2csv tests/fixtures/1013-lens5x-fit-pinhole-01.wdf -o out --match --spectrum-type raman
OK   1013-lens5x-fit-pinhole-01.csv matches -> out/1013-lens5x-fit-pinhole-01-OpenSpecy.csv
  1. (03) pp                                   51.1%  (polypropylene, raman)
  2. polyethylene_oxide_higher_weight_aldrich  50.1%  (polyethers, raman)
  3. polyethylene_glycol_6000_bdh              50.1%  (polyethers, raman)
```

Names are printed exactly as the library stores them.

- Each line shows the rank, the material name (`spectrum_identity`, or `material_class` when that is empty), and the score. In brackets come the material class and the reference's spectrum type.
- The score is `match_val`, the Pearson correlation, written as a percentage with one decimal: 0.768 becomes `76.8%`. A missing score is shown as `n/a`.
- A wide map CSV with several spectra gets a `spectrum <object_id>:` heading followed by that spectrum's top 3.

The GUI shows an "Identify with OpenSpecy" checkbox, but only when R is detected. It always uses the web preset and names its results the same way. Its log window shows the same top 3 lines.

### Presets

**`web` (default)** reproduces the defaults of openspecy.org. The settings are taken from the Shiny app source bundled in the OpenSpecy package (`inst/shiny`). The website appears to run this app: its signal-to-noise value and result summary match the bundled code.

| Setting | openspecy.org default | `web` preset |
|---|---|---|
| Library type | Medoid | `medoid_derivative` (`--lib-type full` for the full library) |
| Spectrum type | All (FTIR + Raman + NIR) | `all` (`--spectrum-type raman` etc.) |
| Smoothing / derivative | polynomial 3, 1st derivative, absolute value, 90 cm⁻¹ window | same; window converted to points with `calc_window_points()` |
| Conform wavenumbers | "Mean Up", 6 cm⁻¹ | same: if the upload is finer than 6 cm⁻¹ its axis is kept and the library is conformed onto it, otherwise the upload is resampled |
| Baseline, intensity, range, CO₂, spike, saturation | off | off |
| Matching | `match_spec(conform = FALSE, type = "roll")` | same |

Note that "All" searches FTIR and NIR references too, as the website does. For a Raman measurement you may prefer `--spectrum-type raman`.

**`legacy`** is the pipeline used before v0.2: the full Raman library, a fixed 11-point smoothing window (or baseline subtraction for `nobaseline`), and `match_spec(conform = TRUE)`. Its results can differ a lot from the website. On one test spectrum the best match changed from a mineral (marshite, 0.60) to polyethylene (0.67).

The R script is `src/wdf_openspecy_bridge/openspecy_match.R`. You can also run it directly:
`Rscript openspecy_match.R web derivative medoid all 5 in1.csv in1-OpenSpecy.csv in2.csv in2-OpenSpecy.csv` (input and output paths in pairs).

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
- The match scores are only a screening aid. Check the spectra by eye before trusting an identification.
- The web preset reproduces the website's processing, but not always its exact score. On one spectrum the website and this tool agree on the top material class (polyethylene) and on the signal-to-noise value (7.89). However, the website reports a correlation of 0.704 and this tool 0.667. The website may be running a slightly different app revision or library revision.
- File parsing depends on `renishaw-wdf`. Multitrack files export track 0 only.
