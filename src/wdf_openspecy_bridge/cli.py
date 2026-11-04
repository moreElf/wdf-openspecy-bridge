"""Command line interface: ``wdf2csv``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import collect_inputs, convert_file
from .openspecy import run_match


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wdf2csv",
        description="Convert Renishaw .wdf files to OpenSpecy-compatible CSV.",
    )
    p.add_argument("inputs", nargs="+", help=".wdf files or folders containing them")
    p.add_argument("-o", "--out-dir", help="output folder (default: next to each input)")
    p.add_argument(
        "--header",
        choices=["standard", "hash"],
        default="standard",
        help="'standard' = wavenumber,intensity (default); 'hash' = #Wave,#Intensity",
    )
    p.add_argument(
        "--split",
        action="store_true",
        help="write multi-spectrum files as one long CSV per spectrum instead of one OpenSpecy wide CSV",
    )
    p.add_argument(
        "--match",
        action="store_true",
        help="(Phase 2, needs R + OpenSpecy) identify spectra and write openspecy_matches.csv",
    )
    p.add_argument("--library", default="derivative", help="OpenSpecy library (default: derivative)")
    p.add_argument("--top-n", type=int, default=5, help="number of matches per spectrum")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = collect_inputs(args.inputs)
    if not inputs:
        print("no .wdf files found", file=sys.stderr)
        return 1

    written: list[Path] = []
    failures = 0
    for wdf in inputs:
        try:
            outs = convert_file(wdf, args.out_dir, args.header, args.split)
        except Exception as e:  # report and continue with remaining files
            failures += 1
            print(f"FAIL {wdf}: {e}", file=sys.stderr)
            continue
        written.extend(outs)
        print(f"OK   {wdf} -> {len(outs)} CSV ({outs[0].name}{' ...' if len(outs) > 1 else ''})")

    if args.match and written:
        out_csv = Path(args.out_dir or written[0].parent) / "openspecy_matches.csv"
        try:
            run_match(written, out_csv, args.library, args.top_n)
        except RuntimeError as e:
            print(f"MATCH FAIL: {e}", file=sys.stderr)
            return 1
        print(f"OK   matches -> {out_csv}")

    print(f"done: {len(inputs) - failures}/{len(inputs)} files converted")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
