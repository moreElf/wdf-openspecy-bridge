"""Minimal Tkinter GUI: ``wdf2csv-gui``."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from .convert import convert_file, output_key
from .openspecy import find_rscript, run_match


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("WDF → OpenSpecy CSV")
        self.geometry("640x420")
        self.files: list[Path] = []
        self.out_dir = tk.StringVar()
        self.header = tk.StringVar(value="standard")
        self.do_match = tk.BooleanVar(value=False)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Add .wdf files…", command=self.add_files).pack(side="left")
        ttk.Button(top, text="Clear", command=self.clear).pack(side="left", padx=4)
        self.count = ttk.Label(top, text="0 files")
        self.count.pack(side="left", padx=8)

        row = ttk.Frame(self, padding=(8, 0))
        row.pack(fill="x")
        ttk.Label(row, text="Output folder:").pack(side="left")
        ttk.Entry(row, textvariable=self.out_dir).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row, text="Browse…", command=self.pick_out).pack(side="left")

        opts = ttk.Frame(self, padding=8)
        opts.pack(fill="x")
        ttk.Radiobutton(opts, text="wavenumber,intensity", variable=self.header, value="standard").pack(
            side="left"
        )
        ttk.Radiobutton(opts, text="#Wave,#Intensity", variable=self.header, value="hash").pack(
            side="left", padx=8
        )
        match_cb = ttk.Checkbutton(opts, text="Identify with OpenSpecy (R)", variable=self.do_match)
        match_cb.pack(side="left", padx=8)
        if find_rscript() is None:
            match_cb.state(["disabled"])

        self.run_btn = ttk.Button(self, text="Convert", command=self.run)
        self.run_btn.pack(pady=4)
        self.log = scrolledtext.ScrolledText(self, height=14, state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)

    def add_files(self) -> None:
        picked = filedialog.askopenfilenames(filetypes=[("Renishaw WiRE", "*.wdf"), ("All files", "*.*")])
        self.files.extend(Path(p) for p in picked)
        self.count.config(text=f"{len(self.files)} files")

    def clear(self) -> None:
        self.files.clear()
        self.count.config(text="0 files")

    def pick_out(self) -> None:
        d = filedialog.askdirectory()
        if d:
            self.out_dir.set(d)

    def write(self, msg: str) -> None:
        def append() -> None:
            self.log.config(state="normal")
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.log.config(state="disabled")

        self.after(0, append)

    def run(self) -> None:
        if not self.files:
            self.write("Add at least one .wdf file.")
            return
        self.run_btn.state(["disabled"])
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        out_dir = self.out_dir.get() or None
        written: list[Path] = []
        claimed: dict[str, Path] = {}
        for f in self.files:
            key = output_key(f, out_dir)
            if key in claimed:
                self.write(f"FAIL {f.name}: output name clashes with {claimed[key]}; convert it separately")
                continue
            claimed[key] = f
            try:
                outs = convert_file(f, out_dir, self.header.get())  # type: ignore[arg-type]
                written.extend(outs)
                self.write(f"OK   {f.name} -> {len(outs)} CSV")
            except Exception as e:
                self.write(f"FAIL {f.name}: {e}")
        if self.do_match.get() and written:
            self.write("Running OpenSpecy match (first run downloads the library)…")
            try:
                for csv_file, result in zip(written, run_match(written), strict=True):
                    self.write(f"OK   {csv_file.name} matches -> {result.name}")
            except RuntimeError as e:
                self.write(str(e))
        self.write("done")
        self.after(0, lambda: self.run_btn.state(["!disabled"]))


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
