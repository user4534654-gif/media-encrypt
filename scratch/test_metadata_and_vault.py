import os
import sys
import json
sys.path.insert(0, os.path.abspath('.'))
from core.metadata import load_project_metadata
def test_metadata():
    print("Testing metadata loader...")
    meta = load_project_metadata()
    assert meta.get('name') == 'Media-Encrypt Studio', f"Unexpected name: {meta}"
    assert meta.get('version') == '2.2', f"Unexpected version: {meta}"
    print(f"  PASS: Loaded metadata: {meta}")
def test_flask_index_and_api():
    print("\nTesting Flask index rendering and /api/metadata route...")
    from main import app
    client = app.test_client()
    res_meta = client.get('/api/metadata')
    assert res_meta.status_code == 200, f"Failed /api/metadata: {res_meta.status_code}"
    meta_json = res_meta.get_json()
    assert meta_json['version'] == '2.2', f"Bad API version: {meta_json}"
    print(f"  PASS: /api/metadata returned {meta_json}")
    res_index = client.get('/')
    assert res_index.status_code == 200, f"Failed GET /: {res_index.status_code}"
    html = res_index.get_data(as_text=True)
    assert 'Media-Encrypt Studio v2.2' in html, "Version 2.2 not rendered in index HTML"
    assert 'pickerTabInput' in html and 'pickerTabEncrypted' in html and 'pickerTabDecrypted' in html, "3-folder tabs missing from HTML"
    assert 'modal-close' in html, "modal-close missing from HTML"
    print("  PASS: Index HTML contains version 2.2 and 3-folder picker tabs!")
if __name__ == '__main__':
    test_metadata()
    test_flask_index_and_api()
    print("\nALL VERIFICATION CHECKS PASSED!")
