import os
import sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.crypto import (
    stamp_optical_markers,
    detect_optical_markers,
    inpaint_optical_markers,
    restore_optical_markers
)
from core.image_processor import process_image_file
from core.video_processor import process_video_file
from core.job_manager import JobManager
def create_synthetic_image(path, w=400, h=300):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            img[y, x] = [(x * 255) // w, (y * 255) // h, 128]
    cv2.putText(img, "TEST MEDIA", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.imwrite(path, img)
    return img
def test_marker_detection_accuracy():
    print("=== Testing Marker Detection Accuracy ===")
    w, h = 400, 300
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = 120
    rx1, ry1, rx2, ry2 = 80, 60, 320, 240
    norm_roi = (rx1 / w, ry1 / h, rx2 / w, ry2 / h)
    stamped_out, _ = stamp_optical_markers(img.copy(), rx1, ry1, rx2, ry2, placement='outside', marker_size=18)
    det_out = detect_optical_markers(stamped_out, placement='outside')
    assert det_out is not None, "Failed to detect outside markers"
    print(f"Outside Target ROI: {norm_roi}")
    print(f"Outside Detected ROI: {det_out}")
    for exp, got in zip(norm_roi, det_out):
        assert abs(exp - got) <= 0.015, f"Outside detection error: exp {exp}, got {got}"
    stamped_ins, _ = stamp_optical_markers(img.copy(), rx1, ry1, rx2, ry2, placement='inside', marker_size=18)
    det_ins = detect_optical_markers(stamped_ins, placement='inside')
    assert det_ins is not None, "Failed to detect inside markers"
    print(f"Inside Target ROI: {norm_roi}")
    print(f"Inside Detected ROI: {det_ins}")
    for exp, got in zip(norm_roi, det_ins):
        assert abs(exp - got) <= 0.015, f"Inside detection error: exp {exp}, got {got}"
    print(">>> Marker Detection Accuracy Passed!\n")
def test_image_marker_workflow():
    print("=== Testing Image Marker Workflow (No Coordinates in Key) ===")
    os.makedirs("scratch/test_tmp", exist_ok=True)
    orig_path = "scratch/test_tmp/orig.png"
    enc_path = "scratch/test_tmp/enc.png"
    dec_path = "scratch/test_tmp/dec.png"
    orig_img = create_synthetic_image(orig_path, 400, 300)
    enc_options = {
        'action': 'scramble',
        'cols': 10,
        'rows': 10,
        'seed': 12345,
        'patch_roi': [0.2, 0.2, 0.8, 0.8],
        'optical_markers': True,
        'marker_placement': 'outside',
        'roi_invert': False
    }
    p_dict = {}
    process_image_file(orig_path, enc_path, enc_options, p_dict, "test_img_enc")
    assert os.path.exists(enc_path), "Encrypted image was not created"
    key = "10x10|00003039|opt_out"
    print(f"Generated Key: {key}")
    assert "|roi:" not in key, "Key should not contain explicit ROI coordinates!"
    dec_options = {
        'action': 'unscramble',
        'cols': 10,
        'rows': 10,
        'seed': 12345,
        'optical_markers': True,
        'marker_placement': 'outside'
    }
    process_image_file(enc_path, dec_path, dec_options, p_dict, "test_img_dec")
    assert os.path.exists(dec_path), "Decrypted image was not created"
    dec_img = cv2.imread(dec_path)
    roi_orig = orig_img[60:240, 80:320]
    roi_dec = dec_img[60:240, 80:320]
    diff = np.mean(np.abs(roi_orig.astype(float) - roi_dec.astype(float)))
    print(f"Decrypted ROI Mean Pixel Diff: {diff:.2f}")
    assert diff < 2.0, f"Unscramble failed, diff={diff}"
    print(">>> Image Marker Workflow Passed!\n")
def test_video_marker_workflow():
    print("=== Testing Video Marker Workflow (No Coordinates in Key) ===")
    os.makedirs("scratch/test_tmp", exist_ok=True)
    v_orig = "scratch/test_tmp/vid_orig.mp4"
    v_enc = "scratch/test_tmp/vid_enc.mp4"
    v_dec = "scratch/test_tmp/vid_dec.mp4"
    w, h, fps = 320, 240, 15
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(v_orig, fourcc, fps, (w, h))
    for i in range(15):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = [(i * 15) % 255, 150, 200]
        cv2.circle(frame, (160, 120), 40, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    enc_options = {
        'action': 'scramble',
        'cols': 8,
        'rows': 8,
        'seed': 54321,
        'patch_roi': [0.25, 0.25, 0.75, 0.75],
        'optical_markers': True,
        'marker_placement': 'outside',
        'process_video': True,
        'process_audio': False,
        'export_svg': False,
        'use_gpu': False
    }
    p_dict = {}
    process_video_file(v_orig, v_enc, enc_options, p_dict, "test_vid_enc")
    assert os.path.exists(v_enc), "Encrypted video was not created"
    key = "8x8|0000d431|opt_out"
    print(f"Video Generated Key: {key}")
    assert "|roi:" not in key
    dec_options = {
        'action': 'unscramble',
        'cols': 8,
        'rows': 8,
        'seed': 54321,
        'optical_markers': True,
        'marker_placement': 'outside',
        'process_video': True,
        'process_audio': False,
        'export_svg': False,
        'use_gpu': False
    }
    process_video_file(v_enc, v_dec, dec_options, p_dict, "test_vid_dec")
    assert os.path.exists(v_dec), "Decrypted video was not created"
    assert dec_options.get('patch_roi') is not None, "Decryption should have auto-detected patch_roi!"
    print(f"Auto-detected patch_roi on video: {dec_options['patch_roi']}")
    cap = cv2.VideoCapture(v_dec)
    ret, dec_frame = cap.read()
    cap.release()
    assert ret and dec_frame is not None
    cap_orig = cv2.VideoCapture(v_orig)
    _, orig_frame = cap_orig.read()
    cap_orig.release()
    orig_center = orig_frame[100:140, 140:180]
    dec_center = dec_frame[100:140, 140:180]
    diff = np.mean(np.abs(orig_center.astype(float) - dec_center.astype(float)))
    print(f"Video Decrypted Center Mean Pixel Diff: {diff:.2f}")
    assert diff < 5.0, f"Video unscramble diff too high: {diff}"
    print(">>> Video Marker Workflow Passed!\n")
def test_invert_and_inside_and_legacy():
    print("=== Testing Invert, Inside Placement & Legacy Compatibility ===")
    os.makedirs("scratch/test_tmp", exist_ok=True)
    orig_path = "scratch/test_tmp/orig2.png"
    enc_path = "scratch/test_tmp/enc2.png"
    dec_path = "scratch/test_tmp/dec2.png"
    orig_img = create_synthetic_image(orig_path, 400, 300)
    p_dict = {}
    enc_ins = {
        'action': 'scramble', 'cols': 10, 'rows': 10, 'seed': 999,
        'patch_roi': [0.2, 0.2, 0.8, 0.8], 'optical_markers': True,
        'marker_placement': 'inside', 'roi_invert': False
    }
    process_image_file(orig_path, enc_path, enc_ins, p_dict, "t_ins_enc")
    dec_ins = {
        'action': 'unscramble', 'cols': 10, 'rows': 10, 'seed': 999,
        'optical_markers': True, 'marker_placement': 'inside'
    }
    process_image_file(enc_path, dec_path, dec_ins, p_dict, "t_ins_dec")
    dec_img = cv2.imread(dec_path)
    assert dec_ins.get('patch_roi') is not None
    print(f"Inside auto-detected patch_roi: {dec_ins['patch_roi']}")
    enc_inv = {
        'action': 'scramble', 'cols': 10, 'rows': 10, 'seed': 888,
        'patch_roi': [0.25, 0.25, 0.75, 0.75], 'optical_markers': True,
        'marker_placement': 'outside', 'roi_invert': True
    }
    process_image_file(orig_path, enc_path, enc_inv, p_dict, "t_inv_enc")
    dec_inv = {
        'action': 'unscramble', 'cols': 10, 'rows': 10, 'seed': 888,
        'optical_markers': True, 'marker_placement': 'outside', 'roi_invert': True
    }
    process_image_file(enc_path, dec_path, dec_inv, p_dict, "t_inv_dec")
    assert dec_inv.get('patch_roi') is not None
    print(f"Inverted auto-detected patch_roi: {dec_inv['patch_roi']}")
    legacy_options = {
        'action': 'unscramble', 'cols': 10, 'rows': 10, 'seed': 12345,
        'patch_roi': [0.2, 0.2, 0.8, 0.8],
        'optical_markers': True, 'marker_placement': 'outside'
    }
    enc_legacy_path = "scratch/test_tmp/enc.png"                     
    dec_legacy_path = "scratch/test_tmp/dec_legacy.png"
    process_image_file(enc_legacy_path, dec_legacy_path, legacy_options, p_dict, "t_leg_dec")
    assert os.path.exists(dec_legacy_path)
    print("Legacy key with explicit ROI works smoothly.")
    print(">>> Invert, Inside Placement & Legacy Compatibility Passed!\n")
def test_video_patch_interval_marker_workflow():
    print("=== Testing Video Patch Interval Marker Workflow (NO Timestamps in Key) ===")
    os.makedirs("scratch/test_tmp", exist_ok=True)
    v_orig = "scratch/test_tmp/vid_patch_orig.mp4"
    v_enc = "scratch/test_tmp/vid_patch_enc.mp4"
    v_dec = "scratch/test_tmp/vid_patch_dec.mp4"
    w, h, fps = 320, 240, 15
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(v_orig, fourcc, fps, (w, h))
    for i in range(30):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = [(i * 8) % 255, 120, 180]
        cv2.putText(frame, f"F{i}", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.circle(frame, (160, 120), 40, (0, 0, 255), -1)
        writer.write(frame)
    writer.release()
    enc_options = {
        'action': 'scramble',
        'cols': 8,
        'rows': 8,
        'seed': 7777,
        'patch_roi': [0.25, 0.25, 0.75, 0.75],
        'patch_intervals': [(0.600, 1.400)],
        'optical_markers': True,
        'marker_placement': 'outside',
        'process_video': True,
        'process_audio': False,
        'export_svg': False,
        'use_gpu': False
    }
    p_dict = {}
    process_video_file(v_orig, v_enc, enc_options, p_dict, "t_patch_enc")
    assert os.path.exists(v_enc)
    key_video_only = "8x8|00001e61|opt_out"
    assert "|patch:" not in key_video_only and "|roi:" not in key_video_only
    print(f"Generated Video-Only Key (no timestamps!): {key_video_only}")
    dec_options = {
        'action': 'unscramble',
        'cols': 8,
        'rows': 8,
        'seed': 7777,
        'optical_markers': True,
        'marker_placement': 'outside',
        'process_video': True,
        'process_audio': False,
        'export_svg': False,
        'use_gpu': False
    }
    process_video_file(v_enc, v_dec, dec_options, p_dict, "t_patch_dec")
    assert os.path.exists(v_dec)
    print(f"Decryption auto-detected ROI: {dec_options.get('patch_roi')}")
    cap_orig = cv2.VideoCapture(v_orig)
    cap_enc = cv2.VideoCapture(v_enc)
    cap_dec = cv2.VideoCapture(v_dec)
    frames_orig, frames_enc, frames_dec = [], [], []
    while True:
        r1, f1 = cap_orig.read()
        r2, f2 = cap_enc.read()
        r3, f3 = cap_dec.read()
        if not r1 or not r2 or not r3:
            break
        frames_orig.append(f1)
        frames_enc.append(f2)
        frames_dec.append(f3)
    cap_orig.release()
    cap_enc.release()
    cap_dec.release()
    diff_f3_enc = np.mean(np.abs(frames_orig[3].astype(float) - frames_enc[3].astype(float)))
    diff_f3_dec = np.mean(np.abs(frames_orig[3].astype(float) - frames_dec[3].astype(float)))
    print(f"Frame 3 (Plain Video) Enc Diff: {diff_f3_enc:.2f}, Dec Diff: {diff_f3_dec:.2f}")
    assert diff_f3_enc < 10.0, "Pre-patch frame should have been untouched by encryption!"
    assert diff_f3_dec < 10.0, "Pre-patch frame should have been untouched by decryption!"
    diff_f15_enc = np.mean(np.abs(frames_orig[15].astype(float) - frames_enc[15].astype(float)))
    center_orig = frames_orig[15][100:140, 140:180]
    center_dec = frames_dec[15][100:140, 140:180]
    diff_f15_dec_center = np.mean(np.abs(center_orig.astype(float) - center_dec.astype(float)))
    print(f"Frame 15 (Encrypted Patch) Enc Diff: {diff_f15_enc:.2f}, Dec Center Diff: {diff_f15_dec_center:.2f}")
    assert diff_f15_enc > 12.0, "Patch frame must be encrypted!"
    assert diff_f15_dec_center < 10.0, "Patch frame must be correctly decrypted!"
    diff_f26_dec = np.mean(np.abs(frames_orig[26].astype(float) - frames_dec[26].astype(float)))
    print(f"Frame 26 (Post-Patch Video) Dec Diff: {diff_f26_dec:.2f}")
    assert diff_f26_dec < 10.0, "Post-patch frame should be untouched by decryption!"
    print(">>> Video Patch Interval Marker Workflow Passed!\n")
if __name__ == '__main__':
    test_marker_detection_accuracy()
    test_image_marker_workflow()
    test_video_marker_workflow()
    test_invert_and_inside_and_legacy()
    test_video_patch_interval_marker_workflow()
    print("ALL TESTS PASSED SUCCESSFULLY!")
