                      
import os
import sys
import time
import tempfile
import numpy as np
import cv2
import soundfile as sf
from core.crypto import clean_key, hash_str, seeded_shuffle
from core.grid_utils import find_best_grid, get_blocks
from core.svg_generator import export_grid_to_svg, export_scrambled_grid_to_svg
from core.image_processor import process_image_file
from core.audio import process_audio_file
from core.pipeline import process_media
from core.logger import LiveDebugger
def run_quick_tests():
    start_time = time.time()
    test_results = {}
    LiveDebugger.log("TEST_START", "Starting Media-Encrypt Studio Quick Diagnostic Suite", level="INFO", module="TEST")
    with tempfile.TemporaryDirectory(prefix="media_encrypt_test_") as temp_dir:
        LiveDebugger.log("TEMP_DIR", f"Isolated test directory created: {temp_dir}", level="DEBUG", module="TEST")
        try:
            LiveDebugger.log("TEST_1", "Testing Crypto & Grid Utility functions...", level="INFO", module="TEST")
            cleaned = clean_key("KEY: 10x10|seed123 ")
            assert cleaned == "10x10|seed123", f"Key cleaning failed: '{cleaned}'"
            h1 = hash_str("apple123")
            h2 = hash_str("apple123")
            assert h1 == h2 and isinstance(h1, int), "Hash string function mismatch"
            arr1 = seeded_shuffle([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], h1)
            arr2 = seeded_shuffle([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], h1)
            assert arr1 == arr2, "Seeded shuffle non-deterministic"
            c, r = find_best_grid(12, target_ratio=1.0)
            assert c * r == 12, "Grid calculation factor mismatch"
            blocks = get_blocks(100, 100, 2, 2)
            assert len(blocks) == 4, f"Expected 4 blocks, got {len(blocks)}"
            test_results["Crypto & Grid Utils"] = "PASS"
            LiveDebugger.log("TEST_1_PASS", "Crypto & Grid Utilities verified", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_crypto_grid")
            test_results["Crypto & Grid Utils"] = f"FAIL: {e}"
        try:
            LiveDebugger.log("TEST_2", "Testing SVG Grid Generator...", level="INFO", module="TEST")
            svg_path = os.path.join(temp_dir, "grid_test.svg")
            export_grid_to_svg(svg_path, 200, 200, 4, 4)
            assert os.path.exists(svg_path) and os.path.getsize(svg_path) > 0, "SVG grid file empty"
            svg_scrambled = os.path.join(temp_dir, "grid_scrambled_test.svg")
            export_scrambled_grid_to_svg(svg_scrambled, 200, 200, 4, 4, seed=12345)
            assert os.path.exists(svg_scrambled) and os.path.getsize(svg_scrambled) > 0, "Scrambled SVG file empty"
            test_results["SVG Grid Generator"] = "PASS"
            LiveDebugger.log("TEST_2_PASS", "SVG Grid Generator verified", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_svg_gen")
            test_results["SVG Grid Generator"] = f"FAIL: {e}"
        try:
            LiveDebugger.log("TEST_3", "Testing Image Encrypt/Decrypt Roundtrip...", level="INFO", module="TEST")
            orig_img = np.zeros((120, 120, 3), dtype=np.uint8)
            for y_idx in range(120):
                for x_idx in range(120):
                    orig_img[y_idx, x_idx] = [x_idx * 2, y_idx * 2, (x_idx + y_idx) % 256]
            img_in = os.path.join(temp_dir, "test_orig.png")
            img_enc = os.path.join(temp_dir, "test_enc.png")
            img_dec = os.path.join(temp_dir, "test_dec.png")
            cv2.imwrite(img_in, orig_img)
            enc_options = {'process_video': True, 'reverse': False, 'cols': 4, 'rows': 4, 'seed': 9999, 'export_svg': False}
            prog = {}
            process_image_file(img_in, img_enc, enc_options, prog, "task_img_enc")
            assert os.path.exists(img_enc), "Encrypted image file was not written"
            dec_options = {'process_video': True, 'reverse': True, 'cols': 4, 'rows': 4, 'seed': 9999, 'export_svg': False}
            process_image_file(img_enc, img_dec, dec_options, prog, "task_img_dec")
            assert os.path.exists(img_dec), "Decrypted image file was not written"
            restored_img = cv2.imread(img_dec)
            pixel_diff = np.max(np.abs(orig_img.astype(int) - restored_img.astype(int)))
            assert pixel_diff == 0, f"Image restoration loss detected! Max pixel diff: {pixel_diff}"
            test_results["Image Encrypt/Decrypt"] = "PASS"
            LiveDebugger.log("TEST_3_PASS", "Image Roundtrip verified (0 pixel loss)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_image_roundtrip")
            test_results["Image Encrypt/Decrypt"] = f"FAIL: {e}"
        try:
            LiveDebugger.log("TEST_4", "Testing Audio DSP Methods (inversion, band_scramble, combined)...", level="INFO", module="TEST")
            sr = 48000
            t_sig = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
            sine_wave = 0.5 * np.sin(2 * np.pi * 440 * t_sig)
            stereo_sig = np.vstack((sine_wave, sine_wave)).T
            aud_in = os.path.join(temp_dir, "aud_orig.wav")
            aud_enc = os.path.join(temp_dir, "aud_enc.wav")
            aud_dec = os.path.join(temp_dir, "aud_dec.wav")
            sf.write(aud_in, stereo_sig, sr, subtype='PCM_16')
            for method in ["inversion", "band_scramble", "combined"]:
                process_audio_file(aud_in, aud_enc, is_decrypt=False, method=method, key=555, carrier_freq=8000)
                assert os.path.exists(aud_enc), f"Audio encryption failed for {method}"
                process_audio_file(aud_enc, aud_dec, is_decrypt=True, method=method, key=555, carrier_freq=8000)
                assert os.path.exists(aud_dec), f"Audio decryption failed for {method}"
            test_results["Audio DSP Methods"] = "PASS"
            LiveDebugger.log("TEST_4_PASS", "Audio DSP methods completed roundtrip", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_audio_dsp")
            test_results["Audio DSP Methods"] = f"FAIL: {e}"
        try:
            LiveDebugger.log("TEST_5", "Testing Video Processing Pipeline...", level="INFO", module="TEST")
            vid_in = os.path.join(temp_dir, "vid_orig.mp4")
            vid_enc = os.path.join(temp_dir, "vid_enc.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(vid_in, fourcc, 10.0, (160, 120))
            for i in range(10):
                frame = np.full((120, 160, 3), (i * 20, 100, 200 - i * 15), dtype=np.uint8)
                writer.write(frame)
            writer.release()
            assert os.path.exists(vid_in) and os.path.getsize(vid_in) > 0, "Synthetic video generation failed"
            vid_options = {
                'process_video': True,
                'process_audio': False,
                'reverse': False,
                'cols': 2,
                'rows': 2,
                'seed': hash_str("test_vid_seed"),
                'export_svg': False,
                'vid_format': '.mp4',
                'vid_codec': 'libx264',
                'vid_bitrate': '500k',
                'vid_preset': 'ultrafast'
            }
            prog = {}
            process_media(vid_in, vid_enc, vid_options, prog, "task_vid_enc")
            assert os.path.exists(vid_enc) and os.path.getsize(vid_enc) > 0, "Encrypted video file missing or empty"
            test_results["Video Pipeline"] = "PASS"
            LiveDebugger.log("TEST_5_PASS", "Video Pipeline verified", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_video_pipeline")
            test_results["Video Pipeline"] = f"FAIL: {e}"
        try:
            LiveDebugger.log("TEST_6", "Verifying LiveDebugger on deliberate exception...", level="INFO", module="TEST")
            try:
                faulty_val = 100 / 0
            except ZeroDivisionError as err:
                diag = LiveDebugger.analyze_exception(err, module_name="FAULT_TEST", func_name="simulated_fault")
                assert diag is not None, "Diagnostic report creation failed"
                assert "ZeroDivisionError" in diag["error_type"], "Diagnostic error type mismatch"
            test_results["LiveDebugger Engine"] = "PASS"
            LiveDebugger.log("TEST_6_PASS", "LiveDebugger Engine verified", level="INFO", module="TEST")
        except Exception as e:
            test_results["LiveDebugger Engine"] = f"FAIL: {e}"
    elapsed_time = time.time() - start_time
    log_file_path = os.path.abspath("quick_test.log")
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(LiveDebugger.logs))
    saved_dl_path = LiveDebugger.save_to_file()
    print("\n" + "=" * 70)
    print("      MEDIA-ENCRYPT STUDIO — QUICK TEST SUITE SUMMARY")
    print("=" * 70)
    all_passed = True
    for test_name, result in test_results.items():
        status_symbol = "✅ PASS" if result == "PASS" else "❌ FAIL"
        print(f" {status_symbol:<8} | {test_name:<30} | {result}")
        if result != "PASS":
            all_passed = False
    print("-" * 70)
    print(f" Total Execution Time: {elapsed_time:.2f} seconds")
    print(f" Log Report Saved To:  {log_file_path}")
    if saved_dl_path:
        print(f" Debugger Log Saved:   {saved_dl_path}")
    print("=" * 70 + "\n")
    return all_passed
if __name__ == "__main__":
    success = run_quick_tests()
    sys.exit(0 if success else 1)
