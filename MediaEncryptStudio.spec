# MediaEncryptStudio.spec
# PyInstaller build specification file.
#
# DO NOT run PyInstaller with long CLI flags — use this file instead:
#   pyinstaller MediaEncryptStudio.spec
#
# Two build modes are controlled by the BUILD_MODE environment variable
# (set by the GitHub Actions workflow):
#   BUILD_MODE=onefile  →  single self-contained .exe
#   BUILD_MODE=onedir   →  folder with .exe + DLLs  (default if unset)
#
# To build locally:
#   set BUILD_MODE=onefile && pyinstaller MediaEncryptStudio.spec
#   set BUILD_MODE=onedir  && pyinstaller MediaEncryptStudio.spec

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Build mode ────────────────────────────────────────────────────────────────
# Read from env var; default to onedir so local builds are faster.
build_mode = os.environ.get("BUILD_MODE", "onedir").strip().lower()
one_file   = (build_mode == "onefile")

# ── Platform ─────────────────────────────────────────────────────────────────
# PyInstaller does not cross-compile: a Linux binary must be built on Linux
# (WSL included) and a Windows binary on Windows. The spec adapts itself to
# the host platform.
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

# ── Paths ─────────────────────────────────────────────────────────────────────
spec_dir = os.path.abspath(SPECPATH)          # directory containing this .spec

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden = [
    # Flask internals
    "flask",
    "jinja2",
    "click",
    # Media / audio
    "imageio_ffmpeg",
    "soundfile",
    "cv2",          # opencv-python
    "numpy",
    "PIL",          # Pillow
    "PIL.Image",
    # Core subpackage
    *collect_submodules("core"),
]

if IS_WINDOWS:
    # pywebview (Windows GUI shell) — the only platform that starts the
    # standalone window (see main.py).
    hidden += ["webview", "webview.platforms.winforms"]
# Linux/other: the app serves HTTP and opens the system browser, so the GUI
# toolkit stack (PyGObject / WebKit2GTK) is not needed. pywebview is not
# installed there at all (see build_linux.sh) and is excluded below, so
# bundling it would only drag in PyGObject — which needs GTK development
# headers to build.

# ── Data files (non-Python assets bundled into the exe) ───────────────────────
datas = [
    *collect_data_files("imageio_ffmpeg"),
    *collect_data_files("soundfile"),
]

for item, dst in [("templates", "templates"), ("static", "static"), ("context", "context"), ("icon.png", ".")]:
    full_path = os.path.join(spec_dir, item)
    if os.path.exists(full_path):
        datas.append((full_path, dst))

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],                    # entry-point script
    pathex=[spec_dir],              # extra sys.path entries
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "google.colab",
        "IPython",
        "matplotlib",
        "tkinter",
        "unittest",
    ] + ([] if IS_WINDOWS else ["webview"]),
    noarchive=False,
)

# ── PYZ archive (compiled .pyc files) ─────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data)

# ── Target Definitions ────────────────────────────────────────────────────────
# The icon is a Windows-only bootloader resource; Linux uses the desktop
# entry point / icon theme instead.
icon_arg = os.path.join(spec_dir, "icon.png") if IS_WINDOWS else None

if one_file:
    # 1. ONEFILE mode (Single self-contained executable)
    # Bundle everything (binaries, zipfiles, datas) directly into the binary.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        name="MediaEncryptStudio",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,                  # Keep log console open for debugging/output!
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_arg,
        onefile=True,
    )
else:
    # 2. ONEDIR mode (Folder with the binary + its dependencies)
    # Exclude binaries/zipfiles/datas from the binary itself, collect them in the directory.
    exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name="MediaEncryptStudio",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,                  # Keep log console open for debugging/output!
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_arg,
        onefile=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="MediaEncryptStudio",
    )
