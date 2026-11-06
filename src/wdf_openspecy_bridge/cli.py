"""Command line interface: ``wdf2csv``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import collect_inputs, convert_file, output_key
from .openspecy import LIB_TYPES, PRESETS, SPECTRUM_TYPES, TRANSFORMATIONS, run_match


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
        help="(Phase 2, needs R + OpenSpecy) identify spectra; writes <name>-OpenSpecy.csv next to each CSV",
    )
    p.add_argument(
        "--preset",
        choices=PRESETS,
        default="web",
        help="'web' = openspecy.org defaults (default); 'legacy' = pre-0.2 full Raman-library pipeline",
    )
    p.add_argument(
        "--library",
        choices=TRANSFORMATIONS,
        default="derivative",
        help="library transformation (default: derivative)",
    )
    p.add_argument(
        "--lib-type",
        choices=LIB_TYPES,
        default="medoid",
        help="web preset: medoid (default, as openspecy.org) or full library",
    )
    p.add_argument(
        "--spectrum-type",
        choices=SPECTRUM_TYPES,
        default="all",
        help="web preset: reference spectrum types to search (default: all, as openspecy.org)",
    )
    p.add_argument("--top-n", type=int, default=5, help="number of matches per spectrum")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = collect_inputs(args.inputs)
    if not inputs:
        print("no .wdf files found", file=sys.stderr)
        return 1

    written: list[Path] = []
    claimed: dict[str, Path] = {}  # output_key -> input that owns it
    failures = 0
    for wdf in inputs:
        key = output_key(wdf, args.out_dir)
        if key in claimed:
            # Same file name from two folders into one output folder: don't overwrite the first.
            failures += 1
            print(
                f"FAIL {wdf}: output name clashes with {claimed[key]}; convert it separately or rename it",
                file=sys.stderr,
            )
            continue
        claimed[key] = wdf
        try:
            outs = convert_file(wdf, args.out_dir, args.header, args.split)
        except Exception as e:  # report and continue with remaining files
            failures += 1
            print(f"FAIL {wdf}: {e}", file=sys.stderr)
            continue
        written.extend(outs)
        print(f"OK   {wdf} -> {len(outs)} CSV ({outs[0].name}{' ...' if len(outs) > 1 else ''})")

    if args.match and written:
        try:
            results = run_match(
                written,
                args.library,
                args.top_n,
                preset=args.preset,
                lib_type=args.lib_type,
                spectrum_type=args.spectrum_type,
            )
        except RuntimeError as e:
            print(f"MATCH FAIL: {e}", file=sys.stderr)
            return 1
        for csv_file, result in zip(written, results, strict=True):
            print(f"OK   {csv_file.name} matches -> {result}")

    print(f"done: {len(inputs) - failures}/{len(inputs)} files converted")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
