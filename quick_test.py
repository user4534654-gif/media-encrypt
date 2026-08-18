                      
import os
import sys
import time
import tempfile
import numpy as np
import cv2
import soundfile as sf
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from core.crypto import clean_key, hash_str, seeded_shuffle
from core.grid_utils import find_best_grid, get_blocks, get_outer_blocks
from core.svg_generator import export_grid_to_svg, export_scrambled_grid_to_svg
from core.image_processor import process_image_file
from core.audio import process_audio_file, mulberry32, get_permutation, get_inverse_permutation
from core.video_processor import process_video_file
from core.pipeline import process_media
from core.metadata_prober import probe_media_file
from core.tempdir import get_temp_dir
from core.logger import LiveDebugger
def parse_key_options(raw_key):
    clean = clean_key(raw_key)
    options = {
        'process_audio': False,
        'process_video': False,
        'reverse': True,
        'center': False,
        'center_size': '1/4',
        'aud_method': 'inversion',
        'aud_splits': 10,
        'vol_factor': 1.0,
        'dual_track': False,
        'video_encrypt_mode': 'external',
        'aud_track': 'both',
        'cols': 10,
        'rows': 10,
        'seed': 0,
        'aud_key': 0,
        'carrier_freq': 8000
    }
    if not clean:
        return options
    if clean.startswith("|a"):
        options['process_audio'] = True
        parts = clean.split('|')
        if len(parts) > 2:
            p2 = parts[2]
            if not (p2.startswith('am_') or p2.startswith('as_') or p2.startswith('cf_') or
                    p2.startswith('v_') or p2 in ['abs', 'acb', 'ainv', 'inversion', 'band_scramble', 'combined'] or
                    p2.startswith('at_')):
                options['seed'] = hash_str(p2)
                options['aud_key'] = hash_str(p2)
        for part in parts[2:]:
            if part.startswith('am_'):
                options['aud_method'] = part[3:]
            elif part == 'abs':
                options['aud_method'] = 'band_scramble'
            elif part == 'acb':
                options['aud_method'] = 'combined'
            elif part == 'ainv':
                options['aud_method'] = 'inversion'
            elif part.startswith('as_'):
                options['aud_splits'] = int(part[3:])
            elif part.startswith('cf_'):
                options['carrier_freq'] = int(part[3:])
            elif part.startswith('v_'):
                options['vol_factor'] = float(part[2:])
            elif part == 'at_l':
                options['aud_track'] = 'left'
            elif part == 'at_r':
                options['aud_track'] = 'right'
    else:
        parts = clean.split('|')
        if len(parts) >= 2:
            dim = parts[0]
            seed_str = parts[1]
            options['process_video'] = True
            if 'x' in dim:
                c_parts = dim.split('x')
                if len(c_parts) == 2 and c_parts[0].isdigit() and c_parts[1].isdigit():
                    options['cols'], options['rows'] = int(c_parts[0]), int(c_parts[1])
            options['seed'] = hash_str(seed_str)
            options['aud_key'] = hash_str(seed_str)
            for part in parts[2:]:
                if part == 'a':
                    options['process_audio'] = True
                elif part == 'c':
                    options['center'] = True
                    options['center_size'] = '1/4'
                elif part.startswith('c_'):
                    options['center'] = True
                    options['center_size'] = part[2:]
                elif part == 'dm':
                    options['dual_track'] = True
                elif part == 'em_ext':
                    options['video_encrypt_mode'] = 'external'
                elif part == 'em_cnt':
                    options['video_encrypt_mode'] = 'center'
                elif part == 'em_both':
                    options['video_encrypt_mode'] = 'both'
                elif part == 'at_l':
                    options['aud_track'] = 'left'
                elif part == 'at_r':
                    options['aud_track'] = 'right'
                elif part.startswith('am_'):
                    options['process_audio'] = True
                    options['aud_method'] = part[3:]
                elif part == 'abs':
                    options['process_audio'] = True
                    options['aud_method'] = 'band_scramble'
                elif part == 'acb':
                    options['process_audio'] = True
                    options['aud_method'] = 'combined'
                elif part == 'ainv':
                    options['process_audio'] = True
                    options['aud_method'] = 'inversion'
                elif part.startswith('as_') and part[3:].isdigit():
                    options['aud_splits'] = int(part[3:])
                elif part.startswith('cf_') and part[3:].isdigit():
                    options['carrier_freq'] = int(part[3:])
                elif part.startswith('v_'):
                    try:
                        options['vol_factor'] = float(part[2:])
                    except ValueError:
                        pass
    return options
def run_quick_tests():
    start_time = time.time()
    test_results = {}
    LiveDebugger.log("TEST_START", "Starting Media-Encrypt Studio Diagnostic Suite", level="INFO", module="TEST")
    with tempfile.TemporaryDirectory(prefix="media_encrypt_diag_") as temp_dir:
        LiveDebugger.log("TEMP_DIR", f"Isolated test directory created: {temp_dir}", level="DEBUG", module="TEST")
        t1_start = time.time()
        try:
            LiveDebugger.log("TEST_1", "Testing Crypto, PRNG Determinism & Key Parsing...", level="INFO", module="TEST")
            assert clean_key("KEY: 10x10|seed123 ") == "10x10|seed123", "clean_key whitespace/prefix failure"
            assert clean_key(None) == "", "clean_key None check failure"
            h_apple = hash_str("apple123")
            assert isinstance(h_apple, int) and h_apple == hash_str("apple123"), "hash_str non-deterministic"
            assert hash_str("test_key") == 4243324813, f"hash_str mismatch on golden vector: {hash_str('test_key')}"
            base_list = list(range(16))
            shuffled_1 = seeded_shuffle(list(base_list), 12345)
            shuffled_2 = seeded_shuffle(list(base_list), 12345)
            assert shuffled_1 == shuffled_2, "seeded_shuffle non-deterministic"
            assert sorted(shuffled_1) == base_list, "seeded_shuffle dropped or duplicated elements"
            assert shuffled_1 != base_list, "seeded_shuffle failed to randomize elements"
            prng = mulberry32(9999)
            val1, val2 = prng(), prng()
            assert 0.0 <= val1 < 1.0 and 0.0 <= val2 < 1.0 and val1 != val2, "mulberry32 PRNG invalid output range"
            perm = get_permutation(20, 54321)
            inv_perm = get_inverse_permutation(20, 54321)
            restored = [perm[inv_perm[i]] for i in range(20)]
            assert restored == list(range(20)), "Permutation / inverse permutation inversion mismatch"
            complex_key = "8x6|my_secret_seed|c_2/4|em_both|a|acb|as_15|cf_10000|dm|v_0.8|at_l"
            opts = parse_key_options(complex_key)
            assert opts['cols'] == 8 and opts['rows'] == 6, f"Key parsing cols/rows mismatch: {opts}"
            assert opts['center'] is True and opts['center_size'] == '2/4', "Center mode key parse failure"
            assert opts['video_encrypt_mode'] == 'both', "Video encrypt mode key parse failure"
            assert opts['process_audio'] is True and opts['aud_method'] == 'combined', "Audio method parse failure"
            assert opts['aud_splits'] == 15 and opts['carrier_freq'] == 10000, "Audio splits/carrier parse failure"
            assert opts['dual_track'] is True, "Dual track parse failure"
            assert abs(opts['vol_factor'] - 0.8) < 1e-4, "Vol factor parse failure"
            assert opts['aud_track'] == 'left', "Audio track parse failure"
            for bad_key in ["", "invalid", "10x|seed", "axb|seed", "|a|"]:
                try:
                    parse_key_options(bad_key)
                except Exception as ex:
                    raise AssertionError(f"Key parser crashed on malformed input '{bad_key}': {ex}")
            t1_dur = time.time() - t1_start
            test_results["Crypto, PRNG & Key Parser"] = f"PASS ({t1_dur:.3f}s)"
            LiveDebugger.log("TEST_1_PASS", f"Crypto & Key Parser verified ({t1_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_crypto_prng_keys")
            test_results["Crypto, PRNG & Key Parser"] = f"FAIL: {e}"
        t2_start = time.time()
        try:
            LiveDebugger.log("TEST_2", "Testing Grid Math & Prime Dimension Partitioning...", level="INFO", module="TEST")
            c, r = find_best_grid(12, target_ratio=1.0)
            assert c * r == 12, "find_best_grid factor mismatch"
            assert (c, r) in [(3, 4), (4, 3)], f"Unexpected grid aspect ratio: {c}x{r}"
            W, H = 127, 131
            cols, rows = 5, 7
            blocks = get_blocks(W, H, cols, rows)
            assert len(blocks) == cols * rows, f"Expected {cols * rows} blocks, got {len(blocks)}"
            canvas_mask = np.zeros((H, W), dtype=np.uint8)
            total_area = 0
            for (x1, y1, x2, y2) in blocks:
                assert 0 <= x1 < x2 <= W, f"Block X bounds invalid: ({x1}, {x2})"
                assert 0 <= y1 < y2 <= H, f"Block Y bounds invalid: ({y1}, {y2})"
                bw, bh = x2 - x1, y2 - y1
                total_area += bw * bh
                canvas_mask[y1:y2, x1:x2] += 1
            assert total_area == W * H, f"Total block area {total_area} != canvas area {W * H}"
            assert np.all(canvas_mask == 1), "Grid blocks have overlapping or uncovered pixels!"
            outer_idx, inner_idx, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, W, H, center_size='1/4')
            assert len(outer_idx) + len(inner_idx) == cols * rows, "Outer/inner blocks count mismatch"
            assert set(outer_idx).isdisjoint(set(inner_idx)), "Outer and inner block sets overlap"
            assert 0 <= cx1 < cx2 <= W and 0 <= cy1 < cy2 <= H, "Center bounding box out of bounds"
            t2_dur = time.time() - t2_start
            test_results["Grid Math & Partitioning"] = f"PASS ({t2_dur:.3f}s)"
            LiveDebugger.log("TEST_2_PASS", f"Grid Math & Partitioning verified ({t2_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_grid_math")
            test_results["Grid Math & Partitioning"] = f"FAIL: {e}"
        t3_start = time.time()
        try:
            LiveDebugger.log("TEST_3", "Testing SVG Grid Exporters...", level="INFO", module="TEST")
            svg_normal = os.path.join(temp_dir, "grid_normal.svg")
            export_grid_to_svg(svg_normal, 200, 200, 4, 4, has_center=False)
            assert os.path.exists(svg_normal) and os.path.getsize(svg_normal) > 50, "Normal SVG empty"
            svg_center = os.path.join(temp_dir, "grid_center.svg")
            export_grid_to_svg(svg_center, 200, 200, 6, 6, has_center=True, center_size='2/4')
            assert os.path.exists(svg_center) and os.path.getsize(svg_center) > 50, "Center SVG empty"
            svg_scrambled = os.path.join(temp_dir, "grid_scrambled.svg")
            export_scrambled_grid_to_svg(svg_scrambled, 200, 200, 4, 4, seed=12345, has_center=False)
            assert os.path.exists(svg_scrambled) and os.path.getsize(svg_scrambled) > 50, "Scrambled SVG empty"
            t3_dur = time.time() - t3_start
            test_results["SVG Grid Generators"] = f"PASS ({t3_dur:.3f}s)"
            LiveDebugger.log("TEST_3_PASS", f"SVG Generators verified ({t3_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_svg_exporters")
            test_results["SVG Grid Generators"] = f"FAIL: {e}"
        t4_start = time.time()
        try:
            LiveDebugger.log("TEST_4", "Testing Image Lossless & Center-Overlay Roundtrips...", level="INFO", module="TEST")
            prog = {}
            W_img, H_img = 120, 120
            synth_bg = np.zeros((H_img, W_img, 3), dtype=np.uint8)
            for y in range(H_img):
                for x in range(W_img):
                    synth_bg[y, x] = [x * 2 % 256, y * 2 % 256, (x * 3 + y * 5) % 256]
            img_bg_in = os.path.join(temp_dir, "img_bg_orig.png")
            img_bg_enc = os.path.join(temp_dir, "img_bg_enc.png")
            img_bg_dec = os.path.join(temp_dir, "img_bg_dec.png")
            cv2.imwrite(img_bg_in, synth_bg)
            enc_opts = {'process_video': True, 'reverse': False, 'cols': 4, 'rows': 4, 'seed': 8888, 'export_svg': False}
            process_image_file(img_bg_in, img_bg_enc, enc_opts, prog, "task_img_enc")
            assert os.path.exists(img_bg_enc), "Encrypted image missing"
            dec_opts = {'process_video': True, 'reverse': True, 'cols': 4, 'rows': 4, 'seed': 8888, 'export_svg': False}
            process_image_file(img_bg_enc, img_bg_dec, dec_opts, prog, "task_img_dec")
            assert os.path.exists(img_bg_dec), "Decrypted image missing"
            restored_bg = cv2.imread(img_bg_dec)
            max_diff = int(np.max(np.abs(synth_bg.astype(int) - restored_bg.astype(int))))
            assert max_diff == 0, f"Lossless image roundtrip failed! Max pixel difference: {max_diff}"
            odd_img = np.zeros((131, 127, 3), dtype=np.uint8)
            odd_in = os.path.join(temp_dir, "odd_orig.png")
            odd_enc = os.path.join(temp_dir, "odd_enc.png")
            odd_dec = os.path.join(temp_dir, "odd_dec.png")
            cv2.imwrite(odd_in, odd_img)
            process_image_file(odd_in, odd_enc, {'process_video': True, 'reverse': False, 'cols': 5, 'rows': 7, 'seed': 1234, 'export_svg': False}, prog, "task_odd_enc")
            process_image_file(odd_enc, odd_dec, {'process_video': True, 'reverse': True, 'cols': 5, 'rows': 7, 'seed': 1234, 'export_svg': False}, prog, "task_odd_dec")
            assert os.path.exists(odd_dec), "Non-divisible image roundtrip file missing"
            bg_pip = np.full((120, 160, 3), 40, dtype=np.uint8)
            cnt_pip = np.full((60, 80, 3), 200, dtype=np.uint8)
            bg_pip_path = os.path.join(temp_dir, "bg_pip.png")
            cnt_pip_path = os.path.join(temp_dir, "cnt_pip.png")
            pip_enc_path = os.path.join(temp_dir, "pip_enc.png")
            pip_dec_path = os.path.join(temp_dir, "pip_dec.png")
            cv2.imwrite(bg_pip_path, bg_pip)
            cv2.imwrite(cnt_pip_path, cnt_pip)
            pip_enc_opts = {
                'process_video': True, 'reverse': False, 'cols': 4, 'rows': 4, 'seed': 1234,
                'center': True, 'center_size': '1/4', 'center_path': cnt_pip_path,
                'video_encrypt_mode': 'both', 'export_svg': False
            }
            process_image_file(bg_pip_path, pip_enc_path, pip_enc_opts, prog, "task_pip_enc")
            assert os.path.exists(pip_enc_path), "PiP encrypted image missing"
            pip_dec_opts = {
                'process_video': True, 'reverse': True, 'cols': 4, 'rows': 4, 'seed': 1234,
                'center': True, 'center_size': '1/4', 'video_encrypt_mode': 'both', 'export_svg': False
            }
            process_image_file(pip_enc_path, pip_dec_path, pip_dec_opts, prog, "task_pip_dec")
            assert os.path.exists(pip_dec_path), "PiP decrypted background missing"
            pip_cnt_dec = os.path.join(temp_dir, "pip_dec_center.png")
            assert os.path.exists(pip_cnt_dec), "PiP extracted center image missing"
            t4_dur = time.time() - t4_start
            test_results["Image & Center-PiP Roundtrip"] = f"PASS ({t4_dur:.3f}s)"
            LiveDebugger.log("TEST_4_PASS", f"Image roundtrips verified ({t4_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_image_roundtrip")
            test_results["Image & Center-PiP Roundtrip"] = f"FAIL: {e}"
        t5_start = time.time()
        try:
            LiveDebugger.log("TEST_5", "Testing Audio DSP Scrambling & Signal Fidelity...", level="INFO", module="TEST")
            sr = 48000
            t_sig = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
            sig = 0.4 * np.sin(2 * np.pi * 440 * t_sig) + 0.2 * np.sin(2 * np.pi * 1200 * t_sig)
            stereo_sig = np.vstack((sig, sig)).T
            aud_orig = os.path.join(temp_dir, "audio_orig.wav")
            aud_enc = os.path.join(temp_dir, "audio_enc.wav")
            aud_dec = os.path.join(temp_dir, "audio_dec.wav")
            sf.write(aud_orig, stereo_sig, sr, subtype='PCM_16')
            for method in ["inversion", "band_scramble", "combined"]:
                process_audio_file(aud_orig, aud_enc, is_decrypt=False, method=method, key=777, carrier_freq=8000)
                assert os.path.exists(aud_enc), f"Audio encryption failed for method: {method}"
                process_audio_file(aud_enc, aud_dec, is_decrypt=True, method=method, key=777, carrier_freq=8000)
                assert os.path.exists(aud_dec), f"Audio decryption failed for method: {method}"
                orig_data, _ = sf.read(aud_orig)
                enc_data, _ = sf.read(aud_enc)
                dec_data, _ = sf.read(aud_dec)
                corr_enc = np.corrcoef(orig_data[:, 0], enc_data[:, 0])[0, 1]
                assert abs(corr_enc) < 0.50, f"Method {method}: Encrypted audio not adequately scrambled (corr={corr_enc:.3f})"
                corr_dec = np.corrcoef(orig_data[:, 0], dec_data[:, 0])[0, 1]
                min_expected_corr = 0.70 if method == "band_scramble" else 0.85
                assert corr_dec >= min_expected_corr, (
                    f"Method {method}: Decrypted audio fidelity low! Correlation={corr_dec:.3f} < {min_expected_corr}"
                )
            aud_mono_in = os.path.join(temp_dir, "mono_orig.wav")
            aud_mono_out = os.path.join(temp_dir, "mono_dec.wav")
            sf.write(aud_mono_in, sig, sr, subtype='PCM_16')
            process_audio_file(aud_mono_in, aud_mono_out, is_decrypt=False, method="inversion")
            assert os.path.exists(aud_mono_out), "Mono audio processing failed"
            t5_dur = time.time() - t5_start
            test_results["Audio DSP & Signal Fidelity"] = f"PASS ({t5_dur:.3f}s)"
            LiveDebugger.log("TEST_5_PASS", f"Audio DSP verified ({t5_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_audio_dsp")
            test_results["Audio DSP & Signal Fidelity"] = f"FAIL: {e}"
        t6_start = time.time()
        try:
            LiveDebugger.log("TEST_6", "Testing Video Encrypt & Decrypt Roundtrip...", level="INFO", module="TEST")
            vid_orig = os.path.join(temp_dir, "vid_orig.mp4")
            vid_enc = os.path.join(temp_dir, "vid_enc.mp4")
            vid_dec = os.path.join(temp_dir, "vid_dec.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(vid_orig, fourcc, 10.0, (160, 120))
            for i in range(10):
                frame = np.full((120, 160, 3), (i * 25, 120, 240 - i * 20), dtype=np.uint8)
                cv2.rectangle(frame, (10 + i * 10, 10), (40 + i * 10, 40), (255, 255, 255), -1)
                writer.write(frame)
            writer.release()
            assert os.path.exists(vid_orig) and os.path.getsize(vid_orig) > 0, "Synthetic video generation failed"
            prog = {}
            vid_seed = hash_str("test_vid_roundtrip")
            enc_options = {
                'process_video': True,
                'process_audio': False,
                'reverse': False,
                'cols': 4,
                'rows': 4,
                'seed': vid_seed,
                'export_svg': False,
                'vid_format': '.mp4',
                'vid_codec': 'libx264',
                'vid_bitrate': '2000k',
                'vid_preset': 'ultrafast'
            }
            process_media(vid_orig, vid_enc, enc_options, prog, "task_v_enc")
            assert os.path.exists(vid_enc) and os.path.getsize(vid_enc) > 0, "Encrypted video file missing or empty"
            dec_options = {
                'process_video': True,
                'process_audio': False,
                'reverse': True,
                'cols': 4,
                'rows': 4,
                'seed': vid_seed,
                'export_svg': False,
                'vid_format': '.mp4',
                'vid_codec': 'libx264',
                'vid_bitrate': '2000k',
                'vid_preset': 'ultrafast'
            }
            process_media(vid_enc, vid_dec, dec_options, prog, "task_v_dec")
            assert os.path.exists(vid_dec) and os.path.getsize(vid_dec) > 0, "Decrypted video file missing or empty"
            cap_orig = cv2.VideoCapture(vid_orig)
            cap_dec = cv2.VideoCapture(vid_dec)
            orig_fc = int(cap_orig.get(cv2.CAP_PROP_FRAME_COUNT))
            dec_fc = int(cap_dec.get(cv2.CAP_PROP_FRAME_COUNT))
            assert dec_fc == orig_fc, f"Decrypted video frame count mismatch: {dec_fc} != {orig_fc}"
            dec_w = int(cap_dec.get(cv2.CAP_PROP_FRAME_WIDTH))
            dec_h = int(cap_dec.get(cv2.CAP_PROP_FRAME_HEIGHT))
            assert (dec_w, dec_h) == (160, 120), f"Decrypted video dimensions mismatch: {dec_w}x{dec_h}"
            ret_o, f_orig = cap_orig.read()
            ret_d, f_dec = cap_dec.read()
            cap_orig.release()
            cap_dec.release()
            assert ret_o and ret_d, "Failed to read decoded frames from video"
            mse = np.mean((f_orig.astype(float) - f_dec.astype(float)) ** 2)
            assert mse < 30.0, f"Decrypted video frame distortion too high: MSE={mse:.2f}"
            t6_dur = time.time() - t6_start
            test_results["Video Roundtrip & Frames"] = f"PASS ({t6_dur:.3f}s)"
            LiveDebugger.log("TEST_6_PASS", f"Video Roundtrip verified ({t6_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_video_pipeline")
            test_results["Video Roundtrip & Frames"] = f"FAIL: {e}"
        t7_start = time.time()
        try:
            LiveDebugger.log("TEST_7", "Testing Media Metadata Prober...", level="INFO", module="TEST")
            if os.path.exists(os.path.join(temp_dir, "vid_orig.mp4")):
                v_info = probe_media_file(os.path.join(temp_dir, "vid_orig.mp4"))
                v_fmt = v_info.get('format', '')
                assert 'mp4' in v_fmt or 'mov' in v_fmt, f"Video format mismatch: {v_fmt}"
                assert v_info.get('resolution') == '160x120', f"Resolution probe mismatch: {v_info.get('resolution')}"
                assert v_info.get('duration_sec') is not None and v_info.get('duration_sec') > 0, "Duration probe failed"
            if os.path.exists(os.path.join(temp_dir, "audio_orig.wav")):
                a_info = probe_media_file(os.path.join(temp_dir, "audio_orig.wav"))
                a_fmt = a_info.get('format', '')
                assert 'wav' in a_fmt, f"Audio format mismatch: {a_fmt}"
                assert a_info.get('audio_sr') is not None, "Audio sample rate probe missing"
            dummy_info = probe_media_file(os.path.join(temp_dir, "non_existent_file.xyz"))
            assert isinstance(dummy_info, dict) and dummy_info.get('video_codec') is None, "Faulty fallback on missing file"
            t7_dur = time.time() - t7_start
            test_results["Metadata Prober"] = f"PASS ({t7_dur:.3f}s)"
            LiveDebugger.log("TEST_7_PASS", f"Metadata Prober verified ({t7_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_metadata_prober")
            test_results["Metadata Prober"] = f"FAIL: {e}"
        t8_start = time.time()
        try:
            LiveDebugger.log("TEST_8", "Testing Temp Resource Cleanup & LiveDebugger Engine...", level="INFO", module="TEST")
            p_temp = get_temp_dir()
            assert os.path.isdir(p_temp), "Project temp directory missing"
            try:
                _ = 100 / 0
            except ZeroDivisionError as err:
                diag = LiveDebugger.analyze_exception(err, module_name="FAULT_TEST", func_name="simulated_fault")
                assert diag is not None, "Diagnostic report creation failed"
                assert "ZeroDivisionError" in diag["error_type"], "Diagnostic error type mismatch"
            t8_dur = time.time() - t8_start
            test_results["Temp Cleanup & Debugger"] = f"PASS ({t8_dur:.3f}s)"
            LiveDebugger.log("TEST_8_PASS", f"Temp Cleanup & Debugger verified ({t8_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_temp_debugger")
            test_results["Temp Cleanup & Debugger"] = f"FAIL: {e}"
    elapsed_time = time.time() - start_time
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(script_dir, "quick_test.log")
    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(LiveDebugger.logs))
    except Exception as e:
        print(f"Warning: Could not write quick_test.log: {e}")
    print("\n" + "=" * 74)
    print("        MEDIA-ENCRYPT STUDIO — DIAGNOSTIC TEST SUITE SUMMARY")
    print("=" * 74)
    all_passed = True
    for test_name, result in test_results.items():
        is_pass = result.startswith("PASS")
        status_tag = "[PASS]" if is_pass else "[FAIL]"
        print(f" {status_tag:<8} | {test_name:<32} | {result}")
        if not is_pass:
            all_passed = False
    print("-" * 74)
    print(f" Total Execution Time: {elapsed_time:.2f} seconds")
    print(f" Diagnostic Log Saved: {log_file_path}")
    print("=" * 74 + "\n")
    return all_passed
if __name__ == "__main__":
    success = run_quick_tests()
    sys.exit(0 if success else 1)
