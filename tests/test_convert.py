import csv
from pathlib import Path

import pytest

from wdf_openspecy_bridge.cli import main
from wdf_openspecy_bridge.convert import collect_inputs, convert_file, read_wdf

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURES / "1013-lens5x-fit-pinhole-01.wdf"


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.reader(f))


def test_read_sample() -> None:
    data = read_wdf(SAMPLE)
    assert data.intensities.shape == (1, data.wavenumber.size)
    assert data.wavenumber.size == 1555
    assert (data.wavenumber[1:] > data.wavenumber[:-1]).all()


def test_convert_single(tmp_path: Path) -> None:
    (out,) = convert_file(SAMPLE, tmp_path)
    rows = read_rows(out)
    assert out.name == "1013-lens5x-fit-pinhole-01.csv"
    assert rows[0] == ["wavenumber", "intensity"]
    assert len(rows) == 1556
    wn = [float(r[0]) for r in rows[1:]]
    assert wn == sorted(wn)
    assert 300 < wn[0] < 310 and 1995 < wn[-1] < 2005
    assert all(len(r) == 2 for r in rows[1:])


def test_hash_header(tmp_path: Path) -> None:
    (out,) = convert_file(SAMPLE, tmp_path, header="hash")
    assert read_rows(out)[0] == ["#Wave", "#Intensity"]


def test_cli_batch_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert collect_inputs([FIXTURES]) == [SAMPLE]
    assert main([str(FIXTURES), "-o", str(tmp_path)]) == 0
    assert (tmp_path / "1013-lens5x-fit-pinhole-01.csv").exists()
    assert "1/1 files converted" in capsys.readouterr().out


def test_cli_reports_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "broken.wdf"
    bad.write_bytes(b"not a wdf")
    assert main([str(SAMPLE), str(bad), "-o", str(tmp_path / "out")]) == 1
    assert (tmp_path / "out" / "1013-lens5x-fit-pinhole-01.csv").exists()


def test_multi_spectrum_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    from wdf_openspecy_bridge import convert

    fake = convert.WdfData(
        source=tmp_path / "map.wdf",
        title="map",
        wavenumber=np.array([100.2, 200.0, 300.0]),
        intensities=np.arange(6, dtype=np.float64).reshape(2, 3),
        x=np.array([0.0, 5.0]),
        y=np.array([1.0, 1.0]),
    )
    monkeypatch.setattr(convert, "read_wdf", lambda _p: fake)

    (wide,) = convert.convert_file(fake.source, tmp_path / "wide")
    assert wide.name == "map.csv"
    assert read_rows(wide) == [
        ["100", "200", "300", "x", "y", "file_name"],
        ["0", "1", "2", "0.0000", "1.0000", "map.wdf"],
        ["3", "4", "5", "5.0000", "1.0000", "map.wdf"],
    ]

    outs = convert.convert_file(fake.source, tmp_path / "split", split=True)
    assert [p.name for p in outs] == ["map_0001.csv", "map_0002.csv"]
    assert read_rows(outs[1])[1:] == [["100.2000", "3"], ["200.0000", "4"], ["300.0000", "5"]]


def test_integer_axis_resamples_dense_spectra() -> None:
    import numpy as np

    from wdf_openspecy_bridge.convert import integer_axis

    wn = np.array([100.0, 100.5, 101.0, 101.5, 102.0])
    axis, y = integer_axis(wn, np.array([[0.0, 1.0, 2.0, 3.0, 4.0]]))
    assert axis.tolist() == [100, 101, 102]
    assert y.tolist() == [[0.0, 2.0, 4.0]]


def test_wide_csv_of_sample_has_integer_columns(tmp_path: Path) -> None:
    from wdf_openspecy_bridge.convert import write_wide_csv

    data = read_wdf(SAMPLE)
    out = tmp_path / "wide.csv"
    write_wide_csv(out, data)
    header = read_rows(out)[0]
    assert header[-3:] == ["x", "y", "file_name"]
    labels = header[:-3]
    assert all(h.isdigit() for h in labels)
    assert len(set(labels)) == len(labels)


@pytest.mark.skipif(
    __import__("wdf_openspecy_bridge.openspecy").openspecy.find_rscript() is None,
    reason="R / OpenSpecy not installed",
)
def test_openspecy_match_end_to_end(tmp_path: Path) -> None:
    from wdf_openspecy_bridge.openspecy import run_match

    (spec,) = convert_file(SAMPLE, tmp_path)
    out = run_match([spec], tmp_path / "matches.csv", top_n=3)
    rows = read_rows(out)
    header, body = rows[0], rows[1:]
    assert len(body) == 3
    rank = header.index("rank")
    score = [float(r[header.index("match_val")]) for r in body]
    assert [r[rank] for r in body] == ["1", "2", "3"]
    assert score == sorted(score, reverse=True)
