#!/usr/bin/env bash
# Build dist/WDF2CSV.app (and a shareable zip) on a Mac. See docs/build-macos.md.
#
#   bash packaging/build_macos.sh                 # uses python3.12 if present, else python3
#   PYTHON=/usr/local/bin/python3.12 bash packaging/build_macos.sh
#   SKIP_TESTS=1 bash packaging/build_macos.sh    # skip pytest before building
#
# Everything is installed into .venv-macos inside the repo; nothing system-wide is changed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${VENV:-.venv-macos}"
TARGET_ARCH="${WDF2CSV_TARGET_ARCH:-arm64}"
export WDF2CSV_TARGET_ARCH="$TARGET_ARCH"

die() { echo "error: $*" >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || die "this script builds the macOS app and must run on macOS (PyInstaller cannot cross-compile)."

if [[ -z "${PYTHON:-}" ]]; then
  if command -v python3.12 >/dev/null 2>&1; then PYTHON=python3.12; else PYTHON=python3; fi
fi
command -v "$PYTHON" >/dev/null 2>&1 || die "$PYTHON not found. Install Python 3.12 from python.org (see docs/build-macos.md)."

# The Python must run natively for the target architecture; an x86_64 Python under Rosetta
# would produce (or fail to produce) an Intel app.
PY_ARCH="$("$PYTHON" -c 'import platform; print(platform.machine())')"
[[ "$PY_ARCH" == "$TARGET_ARCH" ]] || die "$PYTHON runs as $PY_ARCH but the target is $TARGET_ARCH. Use a native Python (python.org universal2 installer) or set WDF2CSV_TARGET_ARCH."

"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python >= 3.10 is required ($("$PYTHON" -V))."

# Tkinter must be importable and Tk must be 8.6+ (Apple's /usr/bin/python3 ships the old,
# deprecated Tk 8.5; Homebrew Python needs `brew install python-tk@3.12`).
"$PYTHON" - <<'PY' || die "Tkinter is missing or too old. See 'Tkinter' in docs/build-macos.md."
import tkinter
v = tkinter.TkVersion
print(f"Tk {v}")
raise SystemExit(0 if v >= 8.6 else 1)
PY

echo "==> Python: $("$PYTHON" -V) ($PY_ARCH) at $(command -v "$PYTHON")"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "==> Creating $VENV"
  "$PYTHON" -m venv "$VENV"
fi
VPY="$VENV/bin/python"

echo "==> Installing dependencies into $VENV"
"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install -e ".[app,dev]"

if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
  echo "==> Running tests"
  "$VPY" -m pytest -q
fi

echo "==> Building WDF2CSV.app ($TARGET_ARCH)"
rm -rf build/wdf2csv dist/WDF2CSV dist/WDF2CSV.app
"$VPY" -m PyInstaller packaging/wdf2csv.spec --noconfirm

APP="dist/WDF2CSV.app"
[[ -d "$APP" ]] || die "$APP was not created; see the PyInstaller output above."

echo "==> Checking the result"
lipo -archs "$APP/Contents/MacOS/WDF2CSV"
if codesign --verify --deep --strict "$APP"; then echo "ad-hoc signature OK"; else echo "warning: codesign --verify failed; the app may not start on Apple Silicon" >&2; fi

# ditto keeps the symlinks, permissions and signature inside the bundle; Finder's
# "Compress" works too, but plain `zip -r` breaks the app.
ZIP="dist/WDF2CSV-macos-$TARGET_ARCH.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"

echo
echo "Built: $ROOT/$APP"
echo "Zip:   $ROOT/$ZIP"
echo "Run:   open \"$APP\""
