import os
import sys
import tempfile
import cv2
import numpy as np
sys.path.insert(0, os.path.abspath('.'))
from core.video_processor import process_video_file, build_video_encoder_args
def calculate_psnr(img1, img2):
    mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
    if mse == 0:
        return float('inf'), 0.0
    max_pixel = 255.0
    psnr = 20 * np.log10(max_pixel / np.sqrt(mse))
    return psnr, mse
def test_encoder_args():
    print("Testing build_video_encoder_args...")
    args_off = build_video_encoder_args('libx264', '3000k', 'medium', spatial_mode='off')
    assert '-b:v' in args_off and '3000k' in args_off
    assert '-crf' not in args_off
    print("  PASS: Mode off args correct:", args_off)
    args_zone = build_video_encoder_args('libx264', '4000k', 'medium', spatial_mode='zone')
    assert '-crf' in args_zone and '-maxrate' in args_zone and '4000k' in args_zone
    assert '-aq-mode' in args_zone
    print("  PASS: Mode zone args correct:", args_zone)
    args_tiles = build_video_encoder_args('libx264', '5000k', 'medium', spatial_mode='tiles', rows=4)
    assert '-slices' in args_tiles and '-crf' in args_tiles
    assert '-flags' in args_tiles and '-loop' in args_tiles
    print("  PASS: Mode tiles args correct:", args_tiles)
def test_full_pipeline():
    print("\nTesting full video encrypt & decrypt roundtrip across all modes...")
    temp_dir = tempfile.mkdtemp()
    orig_vid_path = os.path.join(temp_dir, "orig.mp4")
    w, h, fps, n_frames = 160, 120, 15.0, 10
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    vw = cv2.VideoWriter(orig_vid_path, fourcc, fps, (w, h))
    for f_idx in range(n_frames):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(0, h, 20):
            for x in range(0, w, 20):
                if ((x // 20) + (y // 20) + f_idx) % 2 == 0:
                    frame[y:y+20, x:x+20] = (255, 255, 255)
                else:
                    frame[y:y+20, x:x+20] = (15, 15, 15)
        vw.write(frame)
    vw.release()
    modes = ['off', 'zone', 'tiles']
    results = {}
    for mode in modes:
        enc_vid = os.path.join(temp_dir, f"enc_{mode}.mp4")
        dec_vid = os.path.join(temp_dir, f"dec_{mode}.mp4")
        seed = 998877
        cols, rows = 4, 3
        enc_opts = {
            'process_video': True,
            'process_audio': False,
            'reverse': False,
            'cols': cols,
            'rows': rows,
            'seed': seed,
            'vid_codec': 'libx264',
            'vid_bitrate': '5000k',
            'vid_preset': 'ultrafast',
            'spatial_compression_mode': mode,
            'export_svg': False,
            'use_gpu': False
        }
        process_video_file(orig_vid_path, enc_vid, enc_opts, {}, f"task_enc_{mode}")
        assert os.path.exists(enc_vid) and os.path.getsize(enc_vid) > 0, f"Enc video missing for {mode}"
        dec_opts = {
            'process_video': True,
            'process_audio': False,
            'reverse': True,
            'cols': cols,
            'rows': rows,
            'seed': seed,
            'vid_codec': 'libx264',
            'vid_bitrate': '5000k',
            'vid_preset': 'ultrafast',
            'spatial_compression_mode': mode,
            'export_svg': False,
            'use_gpu': False
        }
        process_video_file(enc_vid, dec_vid, dec_opts, {}, f"task_dec_{mode}")
        assert os.path.exists(dec_vid) and os.path.getsize(dec_vid) > 0, f"Dec video missing for {mode}"
        cap_orig = cv2.VideoCapture(orig_vid_path)
        _, f_orig = cap_orig.read()
        cap_orig.release()
        cap_dec = cv2.VideoCapture(dec_vid)
        _, f_dec = cap_dec.read()
        cap_dec.release()
        psnr, mse = calculate_psnr(f_orig, f_dec)
        enc_size = os.path.getsize(enc_vid)
        results[mode] = {'psnr': psnr, 'mse': mse, 'size': enc_size}
        print(f"  Mode '{mode}': PSNR = {psnr:.2f} dB, MSE = {mse:.2f}, Encrypted File Size = {enc_size} bytes")
    print("\nSummary Results:")
    for mode, data in results.items():
        print(f"  {mode.upper()}: PSNR: {data['psnr']:.2f} dB | MSE: {data['mse']:.2f} | Size: {data['size']} bytes")
    for f in os.listdir(temp_dir):
        try: os.remove(os.path.join(temp_dir, f))
        except: pass
    try: os.rmdir(temp_dir)
    except: pass
    print("\nALL TESTS PASSED SUCCESSFULLY!")
if __name__ == '__main__':
    test_encoder_args()
    test_full_pipeline()
