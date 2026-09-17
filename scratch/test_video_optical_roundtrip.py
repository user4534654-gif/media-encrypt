import os
import sys
import cv2
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.video_processor import process_video_file
import tempfile
def create_sample_video(path, w=320, h=240, frames=30, fps=15):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    for i in range(frames):
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :] = (i * 8 % 255, 120, 180)
        cx = int(50 + (i * 6) % (w - 100))
        cy = int(50 + (i * 4) % (h - 100))
        cv2.circle(img, (cx, cy), 30, (0, 255, 0), -1)
        out.write(img)
    out.release()
def test_optical_roundtrip(placement='outside'):
    print(f"\n--- Testing Video Optical Marker Roundtrip ({placement}) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        in_vid = os.path.join(tmpdir, "orig.mp4")
        enc_vid = os.path.join(tmpdir, "enc.mp4")
        dec_vid = os.path.join(tmpdir, "dec.mp4")
        create_sample_video(in_vid, w=320, h=240, frames=20, fps=10)
        roi = [0.15, 0.15, 0.65, 0.65]
        enc_options = {
            'process_video': True,
            'process_audio': False,
            'reverse': False,
            'cols': 4,
            'rows': 4,
            'seed': 42,
            'vid_codec': 'libx264',
            'vid_preset': 'ultrafast',
            'export_svg': False,
            'use_gpu': False,
            'optical_markers': True,
            'marker_placement': placement,
            'patch_segments': [{'start': 0.0, 'end': 2.0, 'roi': roi}]
        }
        print("Encrypting with optical markers...")
        process_video_file(in_vid, enc_vid, enc_options, {}, 'test_enc')
        assert os.path.exists(enc_vid), "Encrypted video must exist"
        print(f"Encrypted video size: {os.path.getsize(enc_vid)} bytes")
        dec_options = {
            'process_video': True,
            'process_audio': False,
            'reverse': True,
            'cols': 4,
            'rows': 4,
            'seed': 42,
            'vid_codec': 'libx264',
            'vid_preset': 'ultrafast',
            'export_svg': False,
            'use_gpu': False,
            'optical_markers': True,
            'marker_placement': placement
        }
        print("Decrypting with auto-detected optical markers...")
        process_video_file(enc_vid, dec_vid, dec_options, {}, 'test_dec')
        assert os.path.exists(dec_vid), "Decrypted video must exist"
        print(f"Decrypted video size: {os.path.getsize(dec_vid)} bytes")
        cap = cv2.VideoCapture(dec_vid)
        read_frames = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            read_frames += 1
        cap.release()
        assert read_frames > 0, "Decrypted video must have frames"
        print(f"PASS: Video roundtrip with placement={placement} passed ({read_frames} frames processed)!")
if __name__ == '__main__':
    test_optical_roundtrip('outside')
    test_optical_roundtrip('inside')
    print("\nALL OPTICAL ROUNDTRIP TESTS PASSED!")
