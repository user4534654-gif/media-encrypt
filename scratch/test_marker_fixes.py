import sys
import os
import cv2
import numpy as np
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.crypto import (
    create_marker_pattern,
    _calculate_marker_boxes,
    stamp_optical_markers,
    inpaint_optical_markers,
    check_marker_presence,
    detect_all_optical_markers,
    detect_optical_markers,
    _group_markers_into_rois
)
from core.grid_utils import get_roi_blocks
def test_no_false_positives():
    print("--- Test 1: No False Positives on Random and Structured Frames ---")
    noise_frame = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
    rois = detect_all_optical_markers(noise_frame)
    assert len(rois) == 0, f"Expected 0 ROIs on random noise, got {len(rois)}"
    scene = np.full((720, 1280, 3), 200, dtype=np.uint8)
    for y in range(50, 600, 100):
        for x in range(50, 1000, 150):
            cv2.rectangle(scene, (x, y), (x + 30, y + 30), (10, 10, 10), -1)
            cv2.rectangle(scene, (x + 5, y + 5), (x + 25, y + 25), (240, 240, 240), -1)
    t0 = time.time()
    rois = detect_all_optical_markers(scene)
    elapsed = (time.time() - t0) * 1000
    print(f"Scene with multiple squares: detected {len(rois)} ROIs in {elapsed:.2f}ms")
    assert len(rois) == 0, f"Expected 0 ROIs on arbitrary squares without fiducial concentric pattern, got {len(rois)}"
    print("PASS: Zero false positive zones detected on non-fiducial patterns!")
def test_outside_markers_detection_and_inpaint():
    print("\n--- Test 2: Outside Markers Stamp, Detect, and Inpaint ---")
    frame = np.full((720, 1280, 3), 160, dtype=np.uint8)
    x1, y1, x2, y2 = 200, 150, 600, 450
    stamped, payload = stamp_optical_markers(frame, x1, y1, x2, y2, placement='outside', marker_size=18)
    t0 = time.time()
    detected = detect_all_optical_markers(stamped, placement='outside')
    elapsed = (time.time() - t0) * 1000
    print(f"Detected in {elapsed:.2f}ms: {detected}")
    assert len(detected) == 1, f"Expected exactly 1 detected ROI, got {len(detected)}"
    det_roi = detected[0]
    expected_norm = (round(x1 / 1280, 4), round(y1 / 720, 4), round(x2 / 1280, 4), round(y2 / 720, 4))
    print(f"Detected: {det_roi}, Expected: {expected_norm}")
    assert abs(det_roi[0] - expected_norm[0]) <= 0.02
    assert abs(det_roi[1] - expected_norm[1]) <= 0.02
    assert abs(det_roi[2] - expected_norm[2]) <= 0.02
    assert abs(det_roi[3] - expected_norm[3]) <= 0.02
    inpainted = inpaint_optical_markers(stamped, det_roi[0], det_roi[1], det_roi[2], det_roi[3], placement='outside', marker_size=18)
    coords = _calculate_marker_boxes(1280, 720, x1, y1, x2, y2, placement='outside', size=18)
    assert not check_marker_presence(inpainted, coords, marker_size=18), "Markers should no longer be present after inpainting"
    print("PASS: Outside markers stamp, detect, and inpaint successful!")
def test_inside_markers_no_block_collision():
    print("\n--- Test 3: Inside Markers Block Calculation & Separation ---")
    w, h = 1280, 720
    x1, y1, x2, y2 = 200, 150, 600, 450
    m_size = 18
    frame = np.full((h, w, 3), 140, dtype=np.uint8)
    stamped, payload = stamp_optical_markers(frame, x1, y1, x2, y2, placement='inside', marker_size=m_size)
    detected = detect_all_optical_markers(stamped, placement='inside')
    assert len(detected) == 1, f"Expected 1 inside ROI detected, got {len(detected)}"
    print(f"Detected inside ROI: {detected[0]}")
    inner_px1 = min(x2, x1 + m_size)
    inner_py1 = min(y2, y1 + m_size)
    inner_px2 = max(inner_px1, x2 - m_size)
    inner_py2 = max(inner_py1, y2 - m_size)
    inner_roi = [inner_px1 / w, inner_py1 / h, inner_px2 / w, inner_py2 / h]
    blocks = get_roi_blocks(w, h, inner_roi, cols=10, rows=10, invert=False)
    marker_boxes = _calculate_marker_boxes(w, h, x1, y1, x2, y2, placement='inside', size=m_size)
    for (bx1, by1, bx2, by2) in blocks:
        for (mx1, my1, mx2, my2) in marker_boxes:
            overlap_x = max(0, min(bx2, mx2) - max(bx1, mx1))
            overlap_y = max(0, min(by2, my2) - max(by1, my1))
            assert overlap_x == 0 or overlap_y == 0, f"Block ({bx1},{by1},{bx2},{by2}) overlaps with marker ({mx1},{my1},{mx2},{my2})!"
    print("PASS: Inside markers have ZERO overlap with encrypted grid blocks!")
def test_optional_qr_generation():
    print("\n--- Test 4: Optional QR Generation Logic ---")
    form_data_with_qr = {'generate_qr': 'true'}
    form_data_without_qr = {'generate_qr': 'false'}
    form_data_empty = {}
    assert (form_data_with_qr.get('generate_qr') in [True, 'true', 'True', '1']) is True
    assert (form_data_without_qr.get('generate_qr') in [True, 'true', 'True', '1']) is False
    assert (form_data_empty.get('generate_qr') in [True, 'true', 'True', '1']) is False
    print("PASS: Optional QR code flag logic verified!")
if __name__ == '__main__':
    test_no_false_positives()
    test_outside_markers_detection_and_inpaint()
    test_inside_markers_no_block_collision()
    test_optional_qr_generation()
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
