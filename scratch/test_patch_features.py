import os
import sys
import numpy as np
import cv2
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.crypto import (
    compress_key, decompress_key, generate_qr_code,
    stamp_optical_markers, restore_optical_markers, detect_optical_markers
)
from core.grid_utils import get_roi_blocks
from core.image_processor import process_image_file
from core.job_manager import JobManager
def test_key_compression():
    print("=== Testing Key Compression & Decompression ===")
    sample_key = "10x10|mysecretseed123|roi:0.1,0.2,0.6,0.8|psegs:[{\"start\":0,\"end\":3,\"roi\":[0.1,0.1,0.5,0.5]}]"
    compressed = compress_key(sample_key)
    print("Original key length:", len(sample_key))
    print("Compressed key:", compressed)
    assert compressed.startswith("K85:"), "Compressed key must start with K85:"
    decompressed, opt_payload = decompress_key(compressed)
    assert decompressed == sample_key, f"Decompression mismatch: {decompressed} vs {sample_key}"
    assert opt_payload is None, "Expected None marker payload for plain key"
    print("✓ Plain key compression and roundtrip passed!")
    dummy_payload = {"coords": [[0, 0, 18, 18]], "patches": ["iVBORw0KGgoAAAANSUhEUg=="]}
    compressed_opt = compress_key(sample_key, extra_payload=dummy_payload)
    print("Optical key compressed length:", len(compressed_opt))
    assert compressed_opt.startswith("K85:")
    decompressed_opt, extracted_payload = decompress_key(compressed_opt)
    assert decompressed_opt == sample_key
    assert extracted_payload == dummy_payload
    print("✓ Key with optical payload compression and roundtrip passed!")
def test_qr_code_roundtrip():
    print("\n=== Testing QR Code Generation and Scanning ===")
    key = "10x10|seed987|roi:0.2,0.2,0.8,0.8"
    qr_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_qr.png"))
    generate_qr_code(key, qr_path)
    assert os.path.exists(qr_path), "QR code file was not created"
    img = cv2.imread(qr_path)
    detector = cv2.QRCodeDetector()
    val, pts, _ = detector.detectAndDecode(img)
    print("QR decoded text:", val)
    assert val == key, f"QR decoded text mismatch: '{val}' vs '{key}'"
    print("✓ QR code generation and decoding passed!")
def test_optical_markers_lossless():
    print("\n=== Testing Lossless Optical Marker Stamping & Restoration ===")
    h, w = 400, 600
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            img[y, x] = [(x * 255) // w, (y * 255) // h, ((x + y) * 255) // (w + h)]
    orig_copy = img.copy()
    rx1, ry1, rx2, ry2 = int(0.2 * w), int(0.2 * h), int(0.8 * w), int(0.8 * h)
    stamped_img, marker_payload = stamp_optical_markers(img.copy(), rx1, ry1, rx2, ry2, placement='outside', marker_size=24)
    print("Optical marker payload generated (len):", len(marker_payload.get('patches', [])))
    assert marker_payload, "Marker payload should not be empty"
    diff_stamped = np.max(np.abs(orig_copy.astype(int) - stamped_img.astype(int)))
    assert diff_stamped > 0, "Stamping should modify pixels"
    roi = (0.2, 0.2, 0.8, 0.8)
    detected_roi = detect_optical_markers(stamped_img)
    print("Auto-detected optical ROI:", detected_roi)
    if detected_roi:
        print(f"Detected: {detected_roi}, expected approx: {roi}")
        assert abs(detected_roi[0] - roi[0]) < 0.08
        assert abs(detected_roi[1] - roi[1]) < 0.08
        assert abs(detected_roi[2] - roi[2]) < 0.08
        assert abs(detected_roi[3] - roi[3]) < 0.08
        print("✓ Optical marker auto-detection verified!")
    restored_img = restore_optical_markers(stamped_img, marker_payload)
    max_diff = np.max(np.abs(orig_copy.astype(int) - restored_img.astype(int)))
    print("Max pixel difference after restoration:", max_diff)
    assert max_diff == 0, f"Expected 0 pixel difference, got {max_diff}"
    print("✓ 100% Lossless Optical Marker Restoration verified!")
def test_spatial_image_scramble_roundtrip():
    print("\n=== Testing Spatial Image Scramble & Unscramble Roundtrip ===")
    h, w = 300, 300
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            img[y, x] = [x % 256, y % 256, (x * y) % 256]
    in_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "orig.png"))
    scrambled_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "scrambled.png"))
    decrypted_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "decrypted.png"))
    cv2.imwrite(in_path, img)
    roi = (0.2, 0.2, 0.8, 0.8)
    cols, rows, seed = 5, 5, 42
    progress_dict = {}
    options_scramble = {
        'process_video': True,
        'reverse': False,
        'cols': cols,
        'rows': rows,
        'seed': seed,
        'patch_roi': roi,
        'roi_invert': False,
        'optical_markers': True,
        'marker_placement': 'outside'
    }
    process_image_file(in_path, scrambled_path, options_scramble, progress_dict, "task1")
    scrambled_img = cv2.imread(scrambled_path)
    top_diff = np.max(np.abs(img[:40, 100:200].astype(int) - scrambled_img[:40, 100:200].astype(int)))
    assert top_diff == 0, f"Region far outside ROI was modified! Max diff: {top_diff}"
    print("✓ Region outside ROI is untouched as expected!")
    marker_payload = options_scramble.get('optical_payload')
    print("Optical marker payload generated:", bool(marker_payload))
    assert marker_payload, "Marker payload should be returned in options for key packaging"
    options_descramble = {
        'process_video': True,
        'reverse': True,
        'cols': cols,
        'rows': rows,
        'seed': seed,
        'patch_roi': roi,
        'roi_invert': False,
        'optical_markers': True,
        'optical_payload': marker_payload
    }
    process_image_file(scrambled_path, decrypted_path, options_descramble, progress_dict, "task2")
    decrypted_img = cv2.imread(decrypted_path)
    total_diff = np.max(np.abs(img.astype(int) - decrypted_img.astype(int)))
    print("Total max difference across all pixels after full roundtrip:", total_diff)
    assert total_diff == 0, f"Decrypted image does not match original! Max diff: {total_diff}"
    print("✓ Full spatial image scramble + optical markers + unscramble roundtrip is 100% pixel-perfect!")
if __name__ == '__main__':
    try:
        test_key_compression()
        test_qr_code_roundtrip()
        test_optical_markers_lossless()
        test_spatial_image_scramble_roundtrip()
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
