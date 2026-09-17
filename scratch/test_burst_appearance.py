import cv2
import numpy as np
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.video_processor import process_video_file
from core.crypto import stamp_optical_markers
def test_late_appearing_zone():
    tmp_dir = tempfile.mkdtemp()
    orig_path = os.path.join(tmp_dir, "test_orig.mp4")
    enc_path = os.path.join(tmp_dir, "test_enc.mp4")
    dec_path = os.path.join(tmp_dir, "test_dec.mp4")
    w, h, fps, total_frames = 320, 240, 20.0, 40
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(orig_path, fourcc, fps, (w, h))
    for f in range(total_frames):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :, 0] = (f * 6) % 255
        img[:, :, 1] = 120
        img[:, :, 2] = 200
        cv2.putText(img, f"Frame {f}", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        out.write(img)
    out.release()
    enc_opts = {
        'process_video': True,
        'process_audio': False,
        'reverse': False,
        'cols': 4,
        'rows': 4,
        'seed': 777,
        'vid_codec': 'libx264',
        'vid_preset': 'ultrafast',
        'export_svg': False,
        'use_gpu': False,
        'optical_markers': True,
        'marker_placement': 'outside',
        'patch_segments': [
            {'start': 1.0, 'end': 2.0, 'roi': [0.2, 0.2, 0.8, 0.8]}
        ]
    }
    print("Encrypting video with late-appearing zone (starts at sec 1.0 / frame 20)...")
    process_video_file(orig_path, enc_path, enc_opts, {}, 'test_late_enc')
    dec_opts = {
        'process_video': True,
        'process_audio': False,
        'reverse': True,
        'cols': 4,
        'rows': 4,
        'seed': 777,
        'vid_codec': 'libx264',
        'vid_preset': 'ultrafast',
        'export_svg': False,
        'use_gpu': False,
        'optical_markers': True,
        'marker_placement': 'outside'
    }
    print("Decrypting video with auto-detection...")
    process_video_file(enc_path, dec_path, dec_opts, {}, 'test_late_dec')
    cap_orig = cv2.VideoCapture(orig_path)
    cap_enc = cv2.VideoCapture(enc_path)
    cap_dec = cv2.VideoCapture(dec_path)
    f_idx = 0
    diffs_enc = []
    diffs_dec = []
    while True:
        r1, f_orig = cap_orig.read()
        r2, f_enc = cap_enc.read()
        r3, f_dec = cap_dec.read()
        if not r1 or not r2 or not r3:
            break
        roi_y1, roi_y2 = int(0.25 * h), int(0.75 * h)
        roi_x1, roi_x2 = int(0.25 * w), int(0.75 * w)
        diff_enc = np.mean(np.abs(f_enc[roi_y1:roi_y2, roi_x1:roi_x2].astype(float) - f_orig[roi_y1:roi_y2, roi_x1:roi_x2].astype(float)))
        diff_dec = np.mean(np.abs(f_dec[roi_y1:roi_y2, roi_x1:roi_x2].astype(float) - f_orig[roi_y1:roi_y2, roi_x1:roi_x2].astype(float)))
        diffs_enc.append(diff_enc)
        diffs_dec.append(diff_dec)
        if 18 <= f_idx <= 24:
            print(f"Frame {f_idx:02d}: diff_enc = {diff_enc:.1f}, diff_dec = {diff_dec:.1f}")
        f_idx += 1
    cap_orig.release()
    cap_enc.release()
    cap_dec.release()
    assert diffs_enc[20] > 10.0, f"Frame 20 should be encrypted, but diff was {diffs_enc[20]}"
    assert diffs_dec[20] < 15.0, f"Frame 20 should be decrypted immediately, but diff was {diffs_dec[20]}"
    assert diffs_dec[21] < 15.0, f"Frame 21 should be decrypted, but diff was {diffs_dec[21]}"
    print("SUCCESS: Zone decrypted on frame 20 immediately upon appearance without missing 5 frames!")
if __name__ == "__main__":
    test_late_appearing_zone()
