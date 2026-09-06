import json
import os
METADATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "version.json")
def load_project_metadata():
    default_metadata = {
        "name": "Media-Encrypt Studio",
        "version": "2.2",
        "author": "dev-media-crypto",
        "description": "Cross-platform Media Encryption & Decryption Studio"
    }
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_metadata.update(data)
        except Exception as e:
            print(f"Warning: Failed to parse {METADATA_FILE}: {e}")
    return default_metadata
