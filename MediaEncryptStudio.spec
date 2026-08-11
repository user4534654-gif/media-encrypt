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

# ── Paths ─────────────────────────────────────────────────────────────────────
spec_dir = os.path.abspath(SPECPATH)          # directory containing this .spec

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden = [
    # Flask internals
    "flask",
    "webview",
    "jinja2",
    "click",
    # pywebview (Windows GUI shell)
    "webview",
    "webview.platforms.winforms",
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

# ── Data files (non-Python assets bundled into the exe) ───────────────────────
datas = [
    (os.path.join(spec_dir, "templates"),  "templates"),
    (os.path.join(spec_dir, "static"),     "static"),
    (os.path.join(spec_dir, "context"),    "context"),
    (os.path.join(spec_dir, "icon.png"),   "."),
    *collect_data_files("imageio_ffmpeg"),
    *collect_data_files("soundfile"),
]

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
    ],
    noarchive=False,
)

# ── PYZ archive (compiled .pyc files) ─────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data)

# ── Target Definitions ────────────────────────────────────────────────────────
if one_file:
    # 1. ONEFILE mode (Single self-contained .exe)
    # Bundle everything (binaries, zipfiles, datas) directly into the EXE file.
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
        icon=os.path.join(spec_dir, "icon.png"),
        onefile=True,
    )
else:
    # 2. ONEDIR mode (Folder with .exe + DLLs)
    # Exclude binaries/zipfiles/datas from the EXE itself, collect them in the directory.
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
        icon=os.path.join(spec_dir, "icon.png"),
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
