import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import cv2
import soundfile as sf
import subprocess
import imageio_ffmpeg as iff

from core.video_processor import process_video_file
from core.crypto import hash_str

def run_reproduction_test():
    print("Testing Bug 1 & Bug 2 reproduction and fix...")
    ffmpeg_exe = iff.get_ffmpeg_exe()
    temp_dir = os.path.join(os.getcwd(), "scratch", "test_tmp")
    os.makedirs(temp_dir, exist_ok=True)

    # 1. Create a 2-second background video (20 frames @ 10fps) with 440Hz tone
    bg_path = os.path.join(temp_dir, "bg_2s.mp4")
    ct_path = os.path.join(temp_dir, "ct_2s.mp4")
    custom_aud_path = os.path.join(temp_dir, "custom_10s.wav")
    enc_out_path = os.path.join(temp_dir, "enc_out.mp4")
    dec_out_path = os.path.join(temp_dir, "dec_out.mp4")

    sr = 22050
    # Custom audio is 10 seconds long (440Hz tone)
    t_10s = np.linspace(0, 10.0, int(sr * 10.0), endpoint=False)
    custom_wav = (0.5 * np.sin(2 * np.pi * 500 * t_10s)).astype(np.float32)
    sf.write(custom_aud_path, custom_wav, sr)

    # Generate 2s video clips
    def make_clip(p, color):
        vraw = p.replace('.mp4', '_raw.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        wr = cv2.VideoWriter(vraw, fourcc, 10.0, (128, 96))
        for _ in range(20): # 20 frames = 2 seconds
            f = np.full((96, 128, 3), color, dtype=np.uint8)
            wr.write(f)
        wr.release()
        # Add audio track of 2s
        w_2s = p.replace('.mp4', '_tone.wav')
        t_2s = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
        tone_wav = (0.5 * np.sin(2 * np.pi * 300 * t_2s)).astype(np.float32)
        sf.write(w_2s, tone_wav, sr)
        subprocess.run([ffmpeg_exe, '-y', '-i', vraw, '-i', w_2s, '-c:v', 'copy', '-c:a', 'aac', '-shortest', p],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(vraw): os.remove(vraw)
        if os.path.exists(w_2s): os.remove(w_2s)

    make_clip(bg_path, (100, 50, 50))
    make_clip(ct_path, (50, 100, 50))

    # Test settings:
    # Selective spatial zones + Dual Track + Center video + Custom audio longer than video (10s vs 2s)
    enc_options = {
        'process_video': True,
        'process_audio': True,
        'reverse': False,
        'cols': 4,
        'rows': 4,
        'seed': hash_str("seed123"),
        'aud_key': hash_str("seed123"),
        'center': True,
        'center_path': ct_path,
        'center_size': '1/4',
        'dual_track': True,
        'aud_track': 'both', # User report: aud_track set to both in UI
        'patch_roi': [0.2, 0.2, 0.8, 0.8],
        'patch_intervals': [(0.0, 1.0)],
        'custom_audio_r': custom_aud_path, # Custom audio uploaded to center / track R
        'track_r_source': 'custom',
        'track_l_source': 'background',
        'vid_codec': 'libx264',
        'vid_preset': 'ultrafast',
        'aud_method': 'inversion',
        'carrier_freq': 8000,
        'vol_factor': 1.0,
        'vol_factor_bg': 1.0,
        'vol_factor_center': 1.0,
    }

    prog = {}
    print("Running process_video_file encrypt...")
    process_video_file(bg_path, enc_out_path, enc_options, prog, "test_enc")

    # Check 1: Video duration must match 2.0s, NOT 10s!
    cap = cv2.VideoCapture(enc_out_path)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    vid_dur = fc / fps
    print(f"Encrypted Video duration: {vid_dur:.2f}s ({fc} frames @ {fps}fps)")
    assert abs(vid_dur - 2.0) < 0.2, f"Bug 1 FAILED: Video duration is {vid_dur:.2f}s, expected ~2.0s"
    print("[PASS] Bug 1 Verified: Video was NOT stretched to custom audio duration!")

    # Check 2: Audio tracks in dual track mode: Left is encrypted, Right is untouched custom audio
    aud_wav = os.path.join(temp_dir, "enc_extracted.wav")
    subprocess.run([ffmpeg_exe, '-y', '-i', enc_out_path, '-vn', '-ar', str(sr), '-ac', '2', aud_wav],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d, _ = sf.read(aud_wav)
    left_ch = d[:, 0]
    right_ch = d[:, 1]

    # Audio duration check
    aud_dur = len(d) / sr
    print(f"Encrypted Audio duration: {aud_dur:.2f}s")
    assert abs(aud_dur - 2.0) < 0.2, f"Audio duration {aud_dur}s not truncated to video length!"

    # FFT peak check on Right channel: should be 500Hz (clean custom audio, NOT scrambled to carrier!)
    def get_peak(a):
        x = a.astype(float) - a.mean()
        spec = np.abs(np.fft.rfft(x))
        spec[0] = 0
        return float(np.argmax(spec)) * sr / len(x)

    peak_l = get_peak(left_ch)
    peak_r = get_peak(right_ch)
    print(f"Encrypted Left peak: {peak_l:.1f}Hz, Right peak: {peak_r:.1f}Hz")
    assert abs(peak_r - 500) < 30, f"Bug 2 FAILED: Right channel in dual track was encrypted! (Peak={peak_r:.1f}Hz, expected 500Hz)"
    print("[PASS] Bug 2 Verified: Right channel remains completely clean / untouched in Dual Track mode!")

    # Clean up
    for f in [bg_path, ct_path, custom_aud_path, enc_out_path, aud_wav]:
        if os.path.exists(f): os.remove(f)

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_reproduction_test()
