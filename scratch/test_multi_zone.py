import os
import sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.video_processor import process_video_file
os.makedirs("scratch/test_tmp", exist_ok=True)
vid_orig = "scratch/test_tmp/multi_zone_orig.mp4"
vid_enc = "scratch/test_tmp/multi_zone_enc.mp4"
vid_dec = "scratch/test_tmp/multi_zone_dec.mp4"
w, h, fps = 320, 240, 20
total_frames = 80              
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(vid_orig, fourcc, fps, (w, h))
for f in range(total_frames):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = ((f * 3) % 255, (f * 5 + 50) % 255, (f * 7 + 100) % 255)
    cv2.circle(img, (80, 60), 30, (255, 255, 0), -1)
    cv2.rectangle(img, (200, 140), (280, 200), (0, 255, 255), -1)
    cv2.putText(img, f"F:{f}", (120, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    out.write(img)
out.release()
patch_segments = [
    {"start": 0.5, "end": 1.8, "roi": [0.1, 0.1, 0.45, 0.45]},
    {"start": 2.2, "end": 3.5, "roi": [0.55, 0.55, 0.9, 0.9]}
]
enc_opts = {
    'action': 'scramble',
    'cols': 8,
    'rows': 8,
    'seed': 4321,
    'patch_segments': patch_segments,
    'optical_markers': True,
    'marker_placement': 'outside',
    'process_video': True,
    'process_audio': False,
    'export_svg': False,
    'use_gpu': False
}
print("=== 1. Encrypting Multi-Zone Video ===")
process_video_file(vid_orig, vid_enc, enc_opts, {}, 'multi_enc')
dec_opts = {
    'action': 'unscramble',
    'cols': 8,
    'rows': 8,
    'seed': 4321,
    'optical_markers': True,
    'marker_placement': 'outside',
    'process_video': True,
    'process_audio': False,
    'export_svg': False,
    'use_gpu': False
}
print("=== 2. Decrypting Multi-Zone Video with Optical Markers ===")
process_video_file(vid_enc, vid_dec, dec_opts, {}, 'multi_dec')
cap_orig = cv2.VideoCapture(vid_orig)
cap_enc = cv2.VideoCapture(vid_enc)
cap_dec = cv2.VideoCapture(vid_dec)
cap_orig.set(cv2.CAP_PROP_POS_FRAMES, 20)
cap_enc.set(cv2.CAP_PROP_POS_FRAMES, 20)
cap_dec.set(cv2.CAP_PROP_POS_FRAMES, 20)
_, f_o_20 = cap_orig.read()
_, f_e_20 = cap_enc.read()
_, f_d_20 = cap_dec.read()
z1_enc_diff = np.mean(np.abs(f_o_20[24:108, 32:144].astype(float) - f_e_20[24:108, 32:144].astype(float)))
z1_dec_diff = np.mean(np.abs(f_o_20[24:108, 32:144].astype(float) - f_d_20[24:108, 32:144].astype(float)))
print(f"Zone 1 (Frame 20 @ 1.0s) -> Enc Diff: {z1_enc_diff:.2f}, Dec Diff: {z1_dec_diff:.2f}")
cap_orig.set(cv2.CAP_PROP_POS_FRAMES, 55)
cap_enc.set(cv2.CAP_PROP_POS_FRAMES, 55)
cap_dec.set(cv2.CAP_PROP_POS_FRAMES, 55)
_, f_o_55 = cap_orig.read()
_, f_e_55 = cap_enc.read()
_, f_d_55 = cap_dec.read()
z2_enc_diff = np.mean(np.abs(f_o_55[132:216, 176:288].astype(float) - f_e_55[132:216, 176:288].astype(float)))
z2_dec_diff = np.mean(np.abs(f_o_55[132:216, 176:288].astype(float) - f_d_55[132:216, 176:288].astype(float)))
print(f"Zone 2 (Frame 55 @ 2.75s) -> Enc Diff: {z2_enc_diff:.2f}, Dec Diff: {z2_dec_diff:.2f}")
cap_orig.release()
cap_enc.release()
cap_dec.release()
assert z1_enc_diff > 10.0, "Zone 1 should be heavily scrambled during encryption"
assert z1_dec_diff < 8.0, "Zone 1 should be cleanly unscrambled on decryption"
assert z2_enc_diff > 10.0, "Zone 2 should be heavily scrambled during encryption"
assert z2_dec_diff < 8.0, "Zone 2 should be cleanly unscrambled on decryption"
print(">>> MULTI-ZONE OPTICAL MARKER DECRYPTION TEST PASSED 100%! <<<")
