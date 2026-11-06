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


def test_cli_refuses_clashing_output_names(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # The same file name from two folders into one output folder must not overwrite.
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "same.wdf").write_bytes(SAMPLE.read_bytes())
    out = tmp_path / "out"
    assert main([str(tmp_path / "a" / "same.wdf"), str(tmp_path / "b" / "same.wdf"), "-o", str(out)]) == 1
    assert [p.name for p in out.iterdir()] == ["same.csv"]
    err = capsys.readouterr().err
    assert "clashes with" in err and str(tmp_path / "a" / "same.wdf") in err


def test_result_path_is_named_after_input() -> None:
    from wdf_openspecy_bridge.openspecy import result_path

    assert result_path(Path("out") / "16GF-A-01.csv") == Path("out") / "16GF-A-01-OpenSpecy.csv"


RESULT_HEADER = [
    "input_file",
    "object_id",
    "rank",
    "match_val",
    "material_class",
    "spectrum_identity",
    "spectrum_type",
]


def write_result(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([RESULT_HEADER, *rows])
    return path


def test_format_score_is_percent_with_one_decimal() -> None:
    from wdf_openspecy_bridge.openspecy import format_score

    assert format_score("0.768") == "76.8%"
    assert format_score("0.626436622821646") == "62.6%"
    assert format_score("1") == "100.0%"
    assert format_score("NA") == "n/a"


def test_summarize_result_lists_top_three(tmp_path: Path) -> None:
    from wdf_openspecy_bridge.openspecy import summarize_result

    result = write_result(
        tmp_path / "a-OpenSpecy.csv",
        [
            ["a.csv", "intensity", "2", "0.70", "polyolefins", "polypropylene", "raman"],
            ["a.csv", "intensity", "1", "0.768", "polyolefins", "polyethylene", "raman"],
            ["a.csv", "intensity", "3", "0.5", "mineral", "", "raman"],
            ["a.csv", "intensity", "4", "0.4", "mineral", "calcite", "raman"],
        ],
    )
    assert summarize_result(result) == [
        "  1. polyethylene   76.8%  (polyolefins, raman)",
        "  2. polypropylene  70.0%  (polyolefins, raman)",
        "  3. mineral        50.0%  (mineral, raman)",
    ]


def test_summarize_result_groups_spectra_of_a_map(tmp_path: Path) -> None:
    from wdf_openspecy_bridge.openspecy import summarize_result

    rows = [
        ["m.csv", oid, str(r), "0.5", "c", f"{oid}-{r}", "raman"]
        for oid in ("p1", "p2")
        for r in (1, 2, 3, 4)
    ]
    lines = summarize_result(write_result(tmp_path / "m-OpenSpecy.csv", rows))
    assert lines[0] == "  spectrum p1:" and lines[4] == "  spectrum p2:"
    assert lines[1] == "    1. p1-1  50.0%  (c, raman)"
    assert len(lines) == 8


def test_cli_logs_top_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from wdf_openspecy_bridge import cli
    from wdf_openspecy_bridge.openspecy import result_path

    def fake_match(csv_files: list[Path], *_a: object, **_k: object) -> list[Path]:
        rows = [["x", "intensity", "1", "0.768", "polyolefins", "polyethylene", "raman"]]
        return [write_result(result_path(f), rows) for f in csv_files]

    monkeypatch.setattr(cli, "run_match", fake_match)
    assert main([str(SAMPLE), "-o", str(tmp_path), "--match"]) == 0
    assert "  1. polyethylene  76.8%  (polyolefins, raman)" in capsys.readouterr().out.splitlines()


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


needs_r = pytest.mark.skipif(
    __import__("wdf_openspecy_bridge.openspecy").openspecy.find_rscript() is None,
    reason="R / OpenSpecy not installed",
)


def test_run_match_rejects_unknown_options() -> None:
    from wdf_openspecy_bridge.openspecy import run_match

    with pytest.raises(ValueError, match="preset"):
        run_match([], preset="website")
    with pytest.raises(ValueError, match="spectrum_type"):
        run_match([], spectrum_type="uv")


@needs_r
@pytest.mark.parametrize("preset", ["web", "legacy"])
def test_openspecy_match_end_to_end(tmp_path: Path, preset: str) -> None:
    from wdf_openspecy_bridge.openspecy import run_match

    (spec,) = convert_file(SAMPLE, tmp_path)
    other = tmp_path / "second.csv"
    other.write_bytes(spec.read_bytes())
    outs = run_match([spec, other], top_n=3, preset=preset)
    # One result file per input, named after it, each holding only its own matches.
    assert [p.name for p in outs] == ["1013-lens5x-fit-pinhole-01-OpenSpecy.csv", "second-OpenSpecy.csv"]
    assert {r[0] for r in read_rows(outs[1])[1:]} == {"second.csv"}
    rows = read_rows(outs[0])
    header, body = rows[0], rows[1:]
    assert len(body) == 3
    assert {r[header.index("input_file")] for r in body} == {spec.name}
    rank = header.index("rank")
    score = [float(r[header.index("match_val")]) for r in body]
    assert [r[rank] for r in body] == ["1", "2", "3"]
    assert score == sorted(score, reverse=True)
    assert "material_class" in header
    types = {r[header.index("spectrum_type")] for r in body}
    # legacy searches Raman only; the web preset searches every technique like openspecy.org
    if preset == "legacy":
        assert types == {"raman"}
    from wdf_openspecy_bridge.openspecy import summarize_result

    lines = summarize_result(outs[0])
    assert [line.split(".")[0].strip() for line in lines] == ["1", "2", "3"]
    assert f"{score[0] * 100:.1f}%" in lines[0]
