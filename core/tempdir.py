"""Dedicated temporary directory for Media-Encrypt Studio.

All short-lived working files (intermediate WAVs, etc.) are written here so the
project folder stays clean during and after processing. A fresh directory is
created per process under the OS temp location and removed on exit; a stale
directory left behind by a crashed run is cleaned up on the next start.
"""

import os
import re
import atexit
import tempfile
import shutil

_PREFIX = "media_encrypt_studio_"

_TEMP_DIR = None


def _cleanup_stale_roots():
    """Remove leftover project temp dirs from earlier (possibly crashed) runs."""
    tmp_root = tempfile.gettempdir()
    try:
        names = os.listdir(tmp_root)
    except OSError:
        return
    pattern = re.compile(r"^" + re.escape(_PREFIX) + r"\d+$")
    for name in names:
        if not pattern.match(name):
            continue
        candidate = os.path.join(tmp_root, name)
        if os.path.isdir(candidate):
            # Don't touch our live directory.
            if _TEMP_DIR and os.path.abspath(candidate) == os.path.abspath(_TEMP_DIR):
                continue
            shutil.rmtree(candidate, ignore_errors=True)


def get_temp_dir():
    """Return the per-process temp directory (created on first use)."""
    global _TEMP_DIR
    if _TEMP_DIR is None:
        _TEMP_DIR = tempfile.mkdtemp(prefix=_PREFIX)
        atexit.register(cleanup_all)
        _cleanup_stale_roots()
    return _TEMP_DIR


def get_temp_file_path(filename):
    """Return an absolute path inside the dedicated temp dir for ``filename``."""
    return os.path.join(get_temp_dir(), filename)


def cleanup_all():
    """Remove the current temp directory (called automatically at exit)."""
    global _TEMP_DIR
    if _TEMP_DIR and os.path.isdir(_TEMP_DIR):
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    _TEMP_DIR = None