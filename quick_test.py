                      
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
from core.grid_utils import find_best_grid, get_blocks, get_outer_blocks, center_size_to_scale, normalize_center_value, format_center_key, center_inner_grid
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
        'carrier_freq': 8000,
        'has_custom_audio': False,
        'track_l_enc': True,
        'track_r_enc': True
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
                elif part == 'ca':
                    options['has_custom_audio'] = True
                elif part == 'cal0':
                    options['has_custom_audio'] = True
                    options['track_l_enc'] = False
                elif part == 'car0':
                    options['has_custom_audio'] = True
                    options['track_r_enc'] = False
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
            assert center_size_to_scale('1/4') == 0.5, "Legacy 1/4 scale changed!"
            assert center_size_to_scale('2/4') == 0.7071, "Legacy 2/4 scale changed!"
            assert center_size_to_scale('3/4') == 0.866, "Legacy 3/4 scale changed!"
            assert center_size_to_scale(2) == 0.7071 and center_size_to_scale('2') == 0.7071
            assert abs(center_size_to_scale('1.44') - 0.6) < 1e-9, "Slider 1.44 must map to 0.6"
            assert abs(center_size_to_scale('2.73') - (2.73 / 4.0) ** 0.5) < 1e-9
            assert abs(center_size_to_scale('1.44/4') - 0.6) < 1e-9
            assert normalize_center_value('2/4') == 2.0 and normalize_center_value('x') == 1.0
            assert normalize_center_value(99.0) <= 3.99 and normalize_center_value(-5) >= 0.25
            assert format_center_key('1/4') == '|c' and format_center_key(1.0) == '|c'
            assert format_center_key('2/4') == '|c_2/4' and format_center_key('3/4') == '|c_3/4'
            assert format_center_key('1.44') == '|c_1.44' and format_center_key(2.7) == '|c_2.7'
            assert center_inner_grid(10, 10, '1/4') == (5, 5)
            assert center_inner_grid(10, 10, '2/4') == (7, 7)
            assert center_inner_grid(10, 10, '1.44') == (6, 6)
            for _n, _leg in [(1.0, '1/4'), (2.0, '2/4'), (3.0, '3/4')]:
                _a = get_outer_blocks(9, 7, 321, 197, center_size=_n)
                _b = get_outer_blocks(9, 7, 321, 197, center_size=_leg)
                assert _a == _b, f"Geometry drift for size {_n} vs {_leg}"
            _fopts = parse_key_options("6x6|s3|c_1.44|em_cnt|a|ainv|as_10|cf_8000|ca|car0")
            assert _fopts['center'] is True and _fopts['center_size'] == '1.44', "Float center key parse failure"
            assert abs(center_size_to_scale(_fopts['center_size']) - 0.6) < 1e-9
            assert _fopts['has_custom_audio'] is True, "|ca tag parse failure"
            assert _fopts['track_l_enc'] is True and _fopts['track_r_enc'] is False, "|car0 tag parse failure"
            _copts = parse_key_options("6x6|s4|c|a|ainv|as_10|cf_8000|ca|cal0")
            assert _copts['track_l_enc'] is False and _copts['track_r_enc'] is True, "|cal0 tag parse failure"
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
        t9_start = time.time()
        try:
            LiveDebugger.log("TEST_9", "Testing Zone+Center nested encrypt/decrypt roundtrips...", level="INFO", module="TEST")
            def _make_clip9(path, w, h, n, base, rect):
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                wr = cv2.VideoWriter(path, fourcc, 10.0, (w, h))
                yy9, xx9 = np.mgrid[0:h, 0:w]
                inv_base = (255 - base[0], 255 - base[1], 255 - base[2])
                for i in range(n):
                    f = np.zeros((h, w, 3), dtype=np.uint8)
                    ph = (i * 4) % 32
                    on = (((xx9 + ph) // 16) + ((yy9 + ph) // 16)) % 2 == 0
                    f[on] = base
                    f[~on] = inv_base
                    cv2.rectangle(f, (4 + i * 4, 4), (24 + i * 4, 24), rect, -1)
                    wr.write(f)
                wr.release()
            def _first_frame9(path):
                cap = cv2.VideoCapture(path)
                ret, frm = cap.read()
                cap.release()
                assert ret and frm is not None, f"Could not read first frame of {path}"
                return frm
            def _frame_at9(path, idx):
                cap = cv2.VideoCapture(path)
                frames = []
                while True:
                    ret, frm = cap.read()
                    if not ret:
                        break
                    frames.append(frm)
                cap.release()
                assert len(frames) > idx, f"Video {path} has only {len(frames)} frames"
                return frames[idx]
            def _meanabs9(a, b):
                return float(np.mean(np.abs(a.astype(int) - b.astype(int))))
            ZW9, ZH9 = 128, 96
            bg9 = os.path.join(temp_dir, "zc_bg.mp4")
            ct9 = os.path.join(temp_dir, "zc_ct.mp4")
            _make_clip9(bg9, ZW9, ZH9, 6, (40, 40, 40), (255, 255, 255))
            _make_clip9(ct9, 64, 48, 6, (200, 10, 10), (0, 255, 0))
            seed9 = hash_str("zone_center_regression")
            roi9 = [0.2, 0.2, 0.8, 0.8]
            px1, py1 = int(round(roi9[0] * ZW9)), int(round(roi9[1] * ZH9))
            px2, py2 = int(round(roi9[2] * ZW9)), int(round(roi9[3] * ZH9))
            zw9, zh9 = px2 - px1, py2 - py1
            _o9, _i9, (_ncx1, _ncy1, _ncx2, _ncy2) = get_outer_blocks(4, 4, zw9, zh9, center_size='1/4')
            icx1, icy1 = px1 + _ncx1, py1 + _ncy1
            cw9, ch9 = _ncx2 - _ncx1, _ncy2 - _ncy1
            fbg9 = _first_frame9(bg9)
            fct9 = _first_frame9(ct9)
            cres9 = cv2.resize(fct9, (cw9, ch9))
            for zc_mode in ['external', 'center', 'both']:
                enc9 = os.path.join(temp_dir, f"zc_enc_{zc_mode}.mp4")
                dec9 = os.path.join(temp_dir, f"zc_dec_{zc_mode}.mp4")
                enc_opts9 = {
                    'process_video': True, 'process_audio': False, 'reverse': False,
                    'cols': 4, 'rows': 4, 'seed': seed9,
                    'center': True, 'center_path': ct9, 'center_size': '1/4',
                    'video_encrypt_mode': zc_mode, 'patch_roi': list(roi9),
                    'export_svg': False, 'vid_codec': 'libx264',
                    'vid_bitrate': '2000k', 'vid_preset': 'ultrafast',
                }
                process_video_file(bg9, enc9, enc_opts9, prog, f"task_zc_enc_{zc_mode}")
                assert os.path.exists(enc9) and os.path.getsize(enc9) > 0, f"Zone+Center encrypted file missing ({zc_mode})"
                fenc9 = _first_frame9(enc9)
                enc_outer = fenc9[py1 + 6:py1 + 10, px1:px2]
                bg_outer = fbg9[py1 + 6:py1 + 10, px1:px2]
                d_outer = _meanabs9(enc_outer, bg_outer)
                enc_inner = fenc9[icy1 + 2:icy1 + 6, icx1 + 4:icx1 + 12]
                plain_inner = cres9[2:6, 4:12]
                d_inner_plain = _meanabs9(enc_inner, plain_inner)
                if zc_mode in ['external', 'both']:
                    assert d_outer > 15.0, (
                        f"[{zc_mode}] zone outer ring NOT encrypted (diff={d_outer:.1f}); "
                        f"background would leak inside the zone")
                else:
                    assert d_outer < 20.0, (
                        f"[{zc_mode}] zone outer ring should stay untouched (diff={d_outer:.1f})")
                if zc_mode in ['center', 'both']:
                    assert d_inner_plain > 15.0, (
                        f"[{zc_mode}] nested center NOT scrambled (diff vs plain={d_inner_plain:.1f}); "
                        f"zone is a plain paste of the second video")
                else:
                    assert d_inner_plain < 30.0, (
                        f"[{zc_mode}] nested center should stay plain (diff vs plain={d_inner_plain:.1f})")
                dec_opts9 = {
                    'process_video': True, 'process_audio': False, 'reverse': True,
                    'cols': 4, 'rows': 4, 'seed': seed9,
                    'center': True, 'center_size': '1/4',
                    'video_encrypt_mode': zc_mode, 'patch_roi': list(roi9),
                    'export_svg': False, 'vid_codec': 'libx264',
                    'vid_bitrate': '2000k', 'vid_preset': 'ultrafast',
                }
                process_video_file(enc9, dec9, dec_opts9, prog, f"task_zc_dec_{zc_mode}")
                assert os.path.exists(dec9) and os.path.getsize(dec9) > 0, f"Zone+Center decrypted file missing ({zc_mode})"
                fdec9 = _first_frame9(dec9)
                base9, ext9 = os.path.splitext(dec9)
                cpath9 = f"{base9}_center{ext9}"
                assert os.path.exists(cpath9), f"Zone+Center center file missing ({zc_mode})"
                fcc9 = _first_frame9(cpath9)
                assert fcc9.shape[1] == cw9 and fcc9.shape[0] == ch9, (
                    f"[{zc_mode}] center file is {fcc9.shape[1]}x{fcc9.shape[0]}, "
                    f"expected nested inner {cw9}x{ch9}")
                if zc_mode in ['external', 'both']:
                    d_main = _meanabs9(fdec9[py1:py2, px1:px2], fbg9[py1:py2, px1:px2])
                    assert d_main < 30.0, (
                        f"[{zc_mode}] decrypt did not restore zone background "
                        f"(diff={d_main:.1f}); center was not deleted / outer not descrambled")
                d_center = _meanabs9(fcc9, cres9)
                assert d_center < 40.0, (
                    f"[{zc_mode}] extracted center is garbled (diff vs original={d_center:.1f})")
                if zc_mode in ['center', 'both']:
                    assert d_center < d_inner_plain, (
                        f"[{zc_mode}] decrypt did not descramble the center "
                        f"(extracted diff={d_center:.1f} vs encrypted diff={d_inner_plain:.1f})")
            bgT = os.path.join(temp_dir, "zc_bgT.mp4")
            _make_clip9(bgT, ZW9, ZH9, 10, (40, 40, 40), (255, 255, 255))
            encT = os.path.join(temp_dir, "zc_encT.mp4")
            decT = os.path.join(temp_dir, "zc_decT.mp4")
            segsT = [{"start": 0.0, "end": 0.4, "roi": list(roi9), "invert": False}]
            enc_optsT = {
                'process_video': True, 'process_audio': False, 'reverse': False,
                'cols': 4, 'rows': 4, 'seed': seed9,
                'center': True, 'center_path': ct9, 'center_size': '1/4',
                'video_encrypt_mode': 'both', 'patch_segments': segsT,
                'patch_intervals': [(0.0, 0.4)],
                'export_svg': False, 'vid_codec': 'libx264',
                'vid_bitrate': '2000k', 'vid_preset': 'ultrafast',
            }
            process_video_file(bgT, encT, enc_optsT, prog, "task_zc_encT")
            fbgT_out = _frame_at9(encT, 8)                             
            fbgT_ref = _frame_at9(bgT, 8)
            d_outside = _meanabs9(fbgT_out, fbgT_ref)
            assert d_outside < 15.0, (
                f"Outside-patch frame was modified (diff={d_outside:.1f}); "
                f"timeline gating is broken")
            fencT_in = _frame_at9(encT, 0)                            
            d_inside = _meanabs9(fencT_in[py1:py2, px1:px2], fbgT_ref[py1:py2, px1:px2])
            assert d_inside > 15.0, (
                f"Inside-patch frame was NOT encrypted (diff={d_inside:.1f})")
            dec_optsT = dict(enc_optsT)
            dec_optsT.update({'reverse': True})
            dec_optsT.pop('center_path', None)
            process_video_file(encT, decT, dec_optsT, prog, "task_zc_decT")
            fdecT_out = _frame_at9(decT, 8)
            d_dec_out = _meanabs9(fdecT_out, fbgT_ref)
            assert d_dec_out < 20.0, (
                f"Decrypt touched outside-patch frames (diff={d_dec_out:.1f})")
            encF = os.path.join(temp_dir, "zc_encF.mp4")
            decF = os.path.join(temp_dir, "zc_decF.mp4")
            enc_optsF = {
                'process_video': True, 'process_audio': False, 'reverse': False,
                'cols': 4, 'rows': 4, 'seed': seed9,
                'center': True, 'center_path': ct9, 'center_size': '2.5',
                'video_encrypt_mode': 'both', 'patch_roi': list(roi9),
                'export_svg': False, 'vid_codec': 'libx264',
                'vid_bitrate': '2000k', 'vid_preset': 'ultrafast',
            }
            process_video_file(bg9, encF, enc_optsF, prog, "task_zc_encF")
            dec_optsF = dict(enc_optsF)
            dec_optsF.update({'reverse': True})
            dec_optsF.pop('center_path', None)
            process_video_file(encF, decF, dec_optsF, prog, "task_zc_decF")
            _oF, _iF, (_fx1, _fy1, _fx2, _fy2) = get_outer_blocks(4, 4, zw9, zh9, center_size='2.5')
            _cwF0, _chF0 = _fx2 - _fx1, _fy2 - _fy1
            _cwF, _chF = _cwF0, _chF0
            if _cwF % 2 != 0:
                _cwF += 1
            if _chF % 2 != 0:
                _chF += 1
            assert (_cwF, _chF) != (cw9, ch9), "Fractional size must change pixel geometry"
            fdecF = _first_frame9(decF)
            d_mainF = _meanabs9(fdecF[py1:py2, px1:px2], _first_frame9(bg9)[py1:py2, px1:px2])
            assert d_mainF < 30.0, f"[2.5] decrypt did not restore zone (diff={d_mainF:.1f})"
            baseF, extF = os.path.splitext(decF)
            fccF = _first_frame9(f"{baseF}_center{extF}")
            assert (fccF.shape[1], fccF.shape[0]) == (_cwF, _chF), (
                f"[2.5] center file is {fccF.shape[1]}x{fccF.shape[0]}, expected {_cwF}x{_chF}")
            d_cF = _meanabs9(fccF, cv2.resize(fct9, (_cwF, _chF)))
            assert d_cF < 40.0 and d_cF < _meanabs9(
                _frame_at9(encF, 0)[py1 + _fy1:py1 + _fy1 + _chF0, px1 + _fx1:px1 + _fx1 + _cwF0],
                cv2.resize(fct9, (_cwF0, _chF0))), f"[2.5] center not descrambled (diff={d_cF:.1f})"
            img_bgF = os.path.join(temp_dir, "zimg_bg.png")
            img_ctF = os.path.join(temp_dir, "zimg_ct.png")
            img_encF = os.path.join(temp_dir, "zimg_enc.png")
            img_decF = os.path.join(temp_dir, "zimg_dec.png")
            _gimg = np.zeros((96, 128, 3), dtype=np.uint8)
            for _yy in range(96):
                for _xx in range(128):
                    _gimg[_yy, _xx] = [_xx * 2 % 256, _yy * 2 % 256, (_xx + _yy) % 256]
            cv2.imwrite(img_bgF, _gimg)
            cv2.imwrite(img_ctF, 255 - cv2.resize(_gimg, (64, 48)))
            process_image_file(img_bgF, img_encF, {
                'process_video': True, 'reverse': False, 'cols': 4, 'rows': 4, 'seed': seed9,
                'center': True, 'center_path': img_ctF, 'center_size': '2.25',
                'video_encrypt_mode': 'both', 'patch_roi': list(roi9), 'export_svg': False,
            }, prog, "task_zimg_encF")
            process_image_file(img_encF, img_decF, {
                'process_video': True, 'reverse': True, 'cols': 4, 'rows': 4, 'seed': seed9,
                'center': True, 'center_size': '2.25',
                'video_encrypt_mode': 'both', 'patch_roi': list(roi9), 'export_svg': False,
            }, prog, "task_zimg_decF")
            _ipx1, _ipy1 = int(round(roi9[0] * 128)), int(round(roi9[1] * 96))
            _ipx2, _ipy2 = int(round(roi9[2] * 128)), int(round(roi9[3] * 96))
            _dImg = _meanabs9(cv2.imread(img_decF)[_ipy1:_ipy2, _ipx1:_ipx2],
                              cv2.imread(img_bgF)[_ipy1:_ipy2, _ipx1:_ipx2])
            assert _dImg < 12.0, f"[img 2.25] zone background not restored (diff={_dImg:.1f})"
            _oI, _iI, (_icx1, _icy1, _icx2, _icy2) = get_outer_blocks(4, 4, _ipx2 - _ipx1, _ipy2 - _ipy1, center_size='2.25')
            _baseI, _extI = os.path.splitext(img_decF)
            _cpathI = f"{_baseI}_center{_extI}"
            assert os.path.exists(_cpathI), "[img 2.25] center file missing"
            _fccI = cv2.imread(_cpathI)
            assert (_fccI.shape[1], _fccI.shape[0]) == (_icx2 - _icx1, _icy2 - _icy1), (
                f"[img 2.25] center file shape {(_fccI.shape[1], _fccI.shape[0])} != inner {(_icx2 - _icx1, _icy2 - _icy1)}")
            t9_dur = time.time() - t9_start
            test_results["Zone+Center Nested Roundtrip"] = f"PASS ({t9_dur:.3f}s)"
            LiveDebugger.log("TEST_9_PASS", f"Zone+Center nested roundtrips verified ({t9_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_zone_center_nested")
            test_results["Zone+Center Nested Roundtrip"] = f"FAIL: {e}"
        t10_start = time.time()
        try:
            import subprocess as _sp
            import imageio_ffmpeg as _iff
            _ffexe = _iff.get_ffmpeg_exe()
            _cflags = _sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            SR10 = 22050
            def _tone10(freq, dur=1.0):
                _t = np.linspace(0, dur, int(SR10 * dur), endpoint=False)
                return (0.5 * np.sin(2 * np.pi * freq * _t)).astype(np.float32)
            def _write_tone10(path, freq):
                sf.write(path, _tone10(freq), SR10, subtype='PCM_16')
            def _make_clip10(path, tone_freq=None):
                _vraw = os.path.join(temp_dir, "t10_" + os.path.basename(path).replace('.mp4', '_v.mp4'))
                _fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                _wr = cv2.VideoWriter(_vraw, _fourcc, 10.0, (128, 96))
                for _i in range(10):
                    _f = np.full((96, 128, 3), (30 + _i * 5, 60, 90), dtype=np.uint8)
                    cv2.rectangle(_f, (8, 8), (40, 40), (255, 255, 255), -1)
                    _wr.write(_f)
                _wr.release()
                if tone_freq is None:
                    os.replace(_vraw, path)
                else:
                    _wv = os.path.join(temp_dir, f"t10_{tone_freq}hz.wav")
                    _write_tone10(_wv, tone_freq)
                    _r = _sp.run([_ffexe, '-y', '-i', _vraw, '-i', _wv,
                                  '-c:v', 'copy', '-c:a', 'aac', '-b:a', '96k',
                                  '-shortest', path],
                                 stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, creationflags=_cflags)
                    assert _r.returncode == 0 and os.path.exists(path), "tone mux failed"
                    os.remove(_vraw)
            def _extract_stereo10(path):
                _wv = os.path.join(temp_dir, "t10_ex.wav")
                _r = _sp.run([_ffexe, '-y', '-i', path, '-vn', '-ar', str(SR10),
                              '-ac', '2', _wv],
                             stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, creationflags=_cflags)
                assert _r.returncode == 0 and os.path.exists(_wv), f"no audio decodable in {os.path.basename(path)}"
                _d, _ = sf.read(_wv)
                os.remove(_wv)
                if len(_d.shape) == 1:
                    _d = np.vstack((_d, _d)).T
                return _d[:, 0], _d[:, 1]
            def _peak10(a):
                _x = a.astype(float)
                _x = _x - _x.mean()
                _n = max(8, len(_x))
                _spec = np.abs(np.fft.rfft(_x))
                _spec[0] = 0.0
                return float(np.argmax(_spec)) * SR10 / _n
            def _near10(f, target, tol=40.0):
                return abs(f - target) <= tol
            def _rms10(a):
                return float(np.sqrt(np.mean(a.astype(float) ** 2)))
            _bgA = os.path.join(temp_dir, "t10_bgA.mp4")
            _ctA = os.path.join(temp_dir, "t10_ctA.mp4")
            _bgS = os.path.join(temp_dir, "t10_bgS.mp4")
            _cusW = os.path.join(temp_dir, "t10_cus660.wav")
            _make_clip10(_bgA, 440)
            _make_clip10(_ctA, 880)
            _make_clip10(_bgS, None)
            _write_tone10(_cusW, 660)
            _seedA = hash_str("audio_routing_regression")
            def _base_opts10(reverse=False):
                return {
                    'process_video': True, 'process_audio': True, 'reverse': reverse,
                    'cols': 4, 'rows': 4, 'seed': _seedA, 'aud_key': _seedA,
                    'center': True, 'center_size': '1/4', 'video_encrypt_mode': 'both',
                    'aud_method': 'inversion', 'aud_splits': 10, 'carrier_freq': 8000,
                    'vol_factor': 1.0, 'vol_factor_bg': 1.0, 'vol_factor_center': 1.0,
                    'aud_track': 'both', 'export_svg': False,
                    'vid_codec': 'libx264', 'vid_bitrate': '800k', 'vid_preset': 'ultrafast',
                }
            _encA = os.path.join(temp_dir, "t10_encA.mp4")
            _oA = _base_opts10()
            _oA.update({'center_path': _ctA, 'dual_track': True})
            process_video_file(_bgA, _encA, _oA, prog, "task_t10_encA")
            _lA, _rA = _extract_stereo10(_encA)
            assert not _near10(_peak10(_lA), 440) and _peak10(_lA) > 3000,
                f"dual L is not modulated background (peak={_peak10(_lA):.0f}Hz)"
            assert _near10(_peak10(_rA), 880), f"dual R is not center audio (peak={_peak10(_rA):.0f}Hz)"
            _decA = os.path.join(temp_dir, "t10_decA.mp4")
            _dA = _base_opts10(reverse=True)
            _dA.update({'dual_track': True})
            process_video_file(_encA, _decA, _dA, prog, "task_t10_decA")
            _ldA, _ = _extract_stereo10(_decA)
            assert _near10(_peak10(_ldA), 440), "dual decrypt did not restore background to main"
            _baseA, _extA = os.path.splitext(_decA)
            _ccA = f"{_baseA}_center{_extA}"
            assert os.path.exists(_ccA), "dual decrypt center file missing"
            _lcA, _ = _extract_stereo10(_ccA)
            assert _near10(_peak10(_lcA), 880), "dual decrypt did not recover center audio"
            _encB = os.path.join(temp_dir, "t10_encB.mp4")
            _oB = _base_opts10()
            _oB.update({'center_path': _ctA, 'dual_track': True})
            process_video_file(_bgS, _encB, _oB, prog, "task_t10_encB")
            _lB, _rB = _extract_stereo10(_encB)
            assert _rms10(_rB) > 0.02, "silent background muted the center track (R is silent)"
            assert _near10(_peak10(_rB), 880), f"center audio lost with silent bg (peak={_peak10(_rB):.0f}Hz)"
            _decB = os.path.join(temp_dir, "t10_decB.mp4")
            _dB = _base_opts10(reverse=True)
            _dB.update({'dual_track': True})
            process_video_file(_encB, _decB, _dB, prog, "task_t10_decB")
            _baseB, _extB = os.path.splitext(_decB)
            _ccB = f"{_baseB}_center{_extB}"
            _lcB, _ = _extract_stereo10(_ccB)
            assert _near10(_peak10(_lcB), 880), "silent-bg decrypt did not recover center audio"
            _encC = os.path.join(temp_dir, "t10_encC.mp4")
            _oC = _base_opts10()
            _oC.update({'center_path': _ctA, 'dual_track': True,
                        'custom_audio_l': _cusW,
                        'track_l_source': 'custom', 'track_r_source': 'center',
                        'track_l_enc': True, 'track_r_enc': True,
                        'custom_audio_l_enc': True, 'custom_audio_r_enc': True})
            process_video_file(_bgA, _encC, _oC, prog, "task_t10_encC")
            _lC, _rC = _extract_stereo10(_encC)
            assert not _near10(_peak10(_lC), 660) and _peak10(_lC) > 3000,
                f"custom L was not modulated into place (peak={_peak10(_lC):.0f}Hz)"
            _prC = _peak10(_rC)
            assert (not _near10(_prC, 880)
                    and (_near10(_prC, 7120) or _near10(_prC, 8880))),
                f"center R missing/wrong with custom L (peak={_prC:.0f}Hz)"
            _decC = os.path.join(temp_dir, "t10_decC.mp4")
            _dC = _base_opts10(reverse=True)
            _dC.update({'has_custom_audio': True, 'track_l_enc': True, 'track_r_enc': True})
            process_video_file(_encC, _decC, _dC, prog, "task_t10_decC")
            _ldC, _ = _extract_stereo10(_decC)
            assert _near10(_peak10(_ldC), 660), "custom decrypt did not restore L to main"
            _baseC, _extC = os.path.splitext(_decC)
            _lcC, _ = _extract_stereo10(f"{_baseC}_center{_extC}")
            assert _near10(_peak10(_lcC), 880), "custom decrypt did not recover center R"
            t10_dur = time.time() - t10_start
            test_results["Center Audio Routing"] = f"PASS ({t10_dur:.3f}s)"
            LiveDebugger.log("TEST_10_PASS", f"Center audio routing verified ({t10_dur:.3f}s)", level="INFO", module="TEST")
        except Exception as e:
            LiveDebugger.analyze_exception(e, module_name="TEST", func_name="test_center_audio_routing")
            test_results["Center Audio Routing"] = f"FAIL: {e}"
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
