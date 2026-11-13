"""Platform branches, checked for every OS on whatever machine runs the tests."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from wdf_openspecy_bridge import openspecy, platform_utils
from wdf_openspecy_bridge.platform_utils import (
    MACOS_RSCRIPT_PATHS,
    background_process_kwargs,
    rscript_candidates,
    wdf_filetypes,
)


def test_platform_defaults_to_sys_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert platform_utils.is_macos() and not platform_utils.is_windows()
    monkeypatch.setattr(sys, "platform", "win32")
    assert platform_utils.is_windows() and not platform_utils.is_macos()


def test_macos_rscript_candidates_cover_cran_and_homebrew(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    paths = [p.as_posix() for p in rscript_candidates(environ={})]
    assert paths == [
        "/Library/Frameworks/R.framework/Resources/bin/Rscript",
        "/opt/homebrew/bin/Rscript",
        "/usr/local/bin/Rscript",
    ]


def test_linux_rscript_candidates() -> None:
    paths = [p.as_posix() for p in rscript_candidates("linux", environ={})]
    assert paths == ["/usr/bin/Rscript", "/usr/local/bin/Rscript"]


def make_rscript(base: Path, version: str) -> Path:
    exe = base / "R" / f"R-{version}" / "bin" / "Rscript.exe"
    exe.parent.mkdir(parents=True)
    exe.touch()
    return exe


def test_windows_rscript_candidates_newest_first_then_per_user(tmp_path: Path) -> None:
    program_files = tmp_path / "pf"
    local = tmp_path / "local"
    old = make_rscript(program_files, "4.3.1")
    new = make_rscript(program_files, "4.6.2")
    user = make_rscript(local / "Programs", "4.5.0")
    env = {"ProgramFiles": str(program_files), "LOCALAPPDATA": str(local)}
    assert rscript_candidates("win32", environ=env) == [new, old, user]


def test_windows_rscript_candidates_without_localappdata(tmp_path: Path) -> None:
    exe = make_rscript(tmp_path, "4.6.2")
    assert rscript_candidates("win32", environ={"ProgramFiles": str(tmp_path)}) == [exe]


def test_background_process_kwargs_hide_console_only_on_windows() -> None:
    assert background_process_kwargs("win32") == {"creationflags": 0x08000000}
    assert background_process_kwargs("darwin") == {}
    assert background_process_kwargs("linux") == {}


def test_wdf_filetypes_all_files_pattern_per_os() -> None:
    assert wdf_filetypes("win32") == [("Renishaw WiRE", "*.wdf"), ("All files", "*.*")]
    assert wdf_filetypes("darwin") == [("Renishaw WiRE", "*.wdf"), ("All files", "*")]


def test_find_rscript_prefers_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openspecy.shutil, "which", lambda _name: "/somewhere/Rscript")
    monkeypatch.setattr(openspecy, "rscript_candidates", lambda: pytest.fail("PATH hit should win"))
    assert openspecy.find_rscript() == "/somewhere/Rscript"


def test_find_rscript_macos_app_with_minimal_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A Finder-started .app has no Rscript on PATH; the CRAN framework location is probed."""
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(openspecy.shutil, "which", lambda _name: None)
    fake_root = tmp_path / "root"
    rscript = fake_root / "Library/Frameworks/R.framework/Resources/bin/Rscript"
    rscript.parent.mkdir(parents=True)
    rscript.touch(mode=0o755)
    # Re-root the absolute macOS locations into tmp_path so they can exist on any machine;
    # the real rscript_candidates() still picks the macOS list because of sys.platform.
    rerooted = tuple(str(fake_root / p.lstrip("/")) for p in MACOS_RSCRIPT_PATHS)
    monkeypatch.setattr(platform_utils, "MACOS_RSCRIPT_PATHS", rerooted)
    assert openspecy.find_rscript() == str(rscript)


def test_find_rscript_skips_missing_candidates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(openspecy.shutil, "which", lambda _name: None)
    monkeypatch.setattr(openspecy, "rscript_candidates", lambda: [tmp_path / "nope" / "Rscript"])
    assert openspecy.find_rscript() is None


def test_run_match_passes_platform_kwargs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(openspecy, "find_rscript", lambda: "Rscript")
    monkeypatch.setattr(openspecy.subprocess, "run", fake_run)
    for platform, expected in (("darwin", None), ("win32", 0x08000000)):
        monkeypatch.setattr(sys, "platform", platform)
        seen.clear()
        openspecy.run_match([tmp_path / "a.csv"])
        assert seen.get("creationflags") == expected
        assert seen["encoding"] == "utf-8"


@pytest.mark.skipif(os.name != "nt", reason="CREATE_NO_WINDOW is only defined on Windows")
def test_create_no_window_constant_matches_stdlib() -> None:
    assert background_process_kwargs("win32")["creationflags"] == subprocess.CREATE_NO_WINDOW
