#!/usr/bin/env bash
# Build Media-Encrypt Studio for Linux.
#
# PyInstaller does NOT cross-compile: this script has to run on the target
# Linux. A native Ubuntu/WSL2 distro is perfectly fine for that. From
# Windows, run it through WSL:
#
#   wsl -d Ubuntu -- bash ./build_linux.sh
#
# Usage:
#   ./build_linux.sh                    # onedir  -> dist/MediaEncryptStudio/
#   BUILD_MODE=onefile ./build_linux.sh # single self-contained binary
#
# Notes:
#   - pywebview is skipped: the app only starts the standalone window on
#     Windows. On Linux it serves HTTP and opens the system browser, so the
#     GTK / WebKit2GTK / PyGObject stack is not needed.
#   - The GUI is the browser: open http://127.0.0.1:5050 after the start.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
BUILD_MODE="${BUILD_MODE:-onedir}"
VENV="${VENV:-.venv-linux}"

echo "==> Python: $("$PYTHON" --version 2>&1)"

if [ ! -d "$VENV" ]; then
    echo "==> Creating virtualenv: $VENV"
    "$PYTHON" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Installing runtime dependencies (pywebview skipped on Linux)"
grep -v -i '^pywebview' requirements.txt > "$VENV/requirements-linux.txt"
pip install --upgrade pip
pip install -r "$VENV/requirements-linux.txt"
pip install pyinstaller

echo "==> Building (BUILD_MODE=$BUILD_MODE)"
BUILD_MODE="$BUILD_MODE" pyinstaller --clean --noconfirm MediaEncryptStudio.spec

echo "==> Build finished:"
ls -lah dist/
echo
echo "Run it with:  ./dist/MediaEncryptStudio/MediaEncryptStudio   (onedir)"
echo "or:          ./dist/MediaEncryptStudio                      (onefile)"
echo "Then open:   http://127.0.0.1:5050"
