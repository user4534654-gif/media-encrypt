
import os
import re
import atexit
import tempfile
import shutil
_PREFIX = "media_encrypt_studio_"
_TEMP_DIR = None
def _cleanup_stale_roots():
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
            if _TEMP_DIR and os.path.abspath(candidate) == os.path.abspath(_TEMP_DIR):
                continue
            shutil.rmtree(candidate, ignore_errors=True)
def get_temp_dir():
    global _TEMP_DIR
    if _TEMP_DIR is None:
        _TEMP_DIR = tempfile.mkdtemp(prefix=_PREFIX)
        atexit.register(cleanup_all)
        _cleanup_stale_roots()
    return _TEMP_DIR
def get_temp_file_path(filename):
    return os.path.join(get_temp_dir(), filename)
def cleanup_all():
    global _TEMP_DIR
    if _TEMP_DIR and os.path.isdir(_TEMP_DIR):
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    _TEMP_DIR = None
