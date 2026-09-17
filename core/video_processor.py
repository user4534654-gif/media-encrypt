import cv2
import numpy as np
import os
import sys
import math
import subprocess
import imageio_ffmpeg
creation_flags = 0
if sys.platform == "win32":
    creation_flags = subprocess.CREATE_NO_WINDOW
from core.crypto import seeded_shuffle, stamp_optical_markers, restore_optical_markers, detect_optical_markers, detect_all_optical_markers, inpaint_optical_markers, check_marker_presence, _calculate_marker_boxes
from core.audio import process_audio_file
from core.grid_utils import find_best_grid, get_outer_blocks, get_blocks, get_roi_blocks
from core.svg_generator import export_grid_to_svg, export_scrambled_grid_to_svg
from core.tempdir import get_temp_file_path
from core.logger import LiveDebugger
_AVAILABLE_HW_ENCODERS = None
def get_available_hw_encoders():
    global _AVAILABLE_HW_ENCODERS
    if _AVAILABLE_HW_ENCODERS is not None:
        return _AVAILABLE_HW_ENCODERS
    encoders = set()
    try:
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        res = subprocess.run(
            [ffmpeg_exe, '-encoders'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creation_flags
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].startswith('V'):
                    encoders.add(parts[1].lower())
    except Exception as e:
        LiveDebugger.log("GPU_PROBE_WARN", f"Failed to probe FFmpeg encoders: {e}", level="WARNING", module="VIDEO")
    _AVAILABLE_HW_ENCODERS = encoders
    return _AVAILABLE_HW_ENCODERS
def resolve_video_encoder(requested_codec, use_gpu=False):
    if not use_gpu:
        return requested_codec, 'software', {}
    hw_encoders = get_available_hw_encoders()
    req = (requested_codec or '').lower()
    is_h264 = req in ['libx264', 'h264', 'auto', '']
    is_h265 = req in ['libx265', 'hevc', 'h265']
    candidate_chain = []
    if is_h264:
        candidate_chain = [
            ('h264_nvenc', 'NVIDIA NVENC'),
            ('h264_videotoolbox', 'Apple VideoToolbox'),
            ('h264_qsv', 'Intel QuickSync'),
            ('h264_amf', 'AMD AMF')
        ]
    elif is_h265:
        candidate_chain = [
            ('hevc_nvenc', 'NVIDIA NVENC'),
            ('hevc_videotoolbox', 'Apple VideoToolbox'),
            ('hevc_qsv', 'Intel QuickSync'),
            ('hevc_amf', 'AMD AMF')
        ]
    for enc_name, hw_type in candidate_chain:
        if enc_name in hw_encoders:
            extra_args = {}
            if 'nvenc' in enc_name:
                extra_args['preset'] = 'p4'
            return enc_name, hw_type, extra_args
    return requested_codec, 'software', {}
def _adjust_audio_length(y, target_len, action='silence'):
    if len(y) >= target_len:
        return y[:target_len]
    shortage = target_len - len(y)
    if action == 'loop' and len(y) > 0:
        repeats = (target_len // len(y)) + 1
        if y.ndim == 1:
            y_tiled = np.tile(y, repeats)
        else:
            y_tiled = np.tile(y, (repeats, 1))
        return y_tiled[:target_len]
    else:
        if y.ndim == 1:
            return np.pad(y, (0, shortage))
        else:
            return np.pad(y, ((0, shortage), (0, 0)))
def _load_or_extract_audio_channel(file_path, target_sr, ffmpeg_exe, creation_flags):
    if not file_path or not os.path.exists(file_path):
        return None
    import soundfile as sf
    temp_wav = get_temp_file_path("extract_track.wav")
    try:
        cmd = [ffmpeg_exe, '-y', '-i', file_path, '-vn', '-ar', str(target_sr), temp_wav]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        if res.returncode == 0 and os.path.exists(temp_wav):
            data, sr = sf.read(temp_wav)
            if len(data.shape) > 1:
                data = data[:, 0]
            return data
    except Exception as e:
        LiveDebugger.log("AUD_EXTRACT_ERR", f"Failed to extract audio from {file_path}: {e}", level="WARNING", module="AUDIO")
    finally:
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass
    return None
def _close_ffmpeg_proc(p, name="FFmpeg"):
    if p is None:
        return
    if p.stdin and not p.stdin.closed:
        try:
            p.stdin.close()
        except Exception:
            pass
    p.stdin = None
    _, stderr_bytes = p.communicate()
    if p.returncode != 0 and stderr_bytes:
        err_text = stderr_bytes.decode('utf-8', errors='ignore')
        LiveDebugger.log("FFMPEG_ERROR", f"{name} encoding failed with returncode {p.returncode}: {err_text.strip()}", level="ERROR", module="VIDEO")
def build_video_encoder_args(chosen_codec, vid_bitrate, vid_preset, spatial_mode='off', rows=1, cols=1, extra_hw_args=None):
    if extra_hw_args is None:
        extra_hw_args = {}
    args = ['-c:v', chosen_codec]
    b_val = vid_bitrate or '3000k'
    buf_val = '6000k'
    try:
        raw_num = int(''.join(filter(str.isdigit, str(b_val))))
        unit = ''.join(filter(str.isalpha, str(b_val))) or 'k'
        buf_val = f"{raw_num * 2}{unit}"
    except Exception:
        buf_val = '6000k'
    codec_lower = (chosen_codec or '').lower()
    is_h264 = any(x in codec_lower for x in ['x264', 'h264'])
    is_h265 = any(x in codec_lower for x in ['x265', 'hevc', 'h265'])
    is_vp9 = any(x in codec_lower for x in ['vp9', 'libvpx'])
    is_nvenc = 'nvenc' in codec_lower
    is_qsv = 'qsv' in codec_lower
    is_vt = 'videotoolbox' in codec_lower
    is_amf = 'amf' in codec_lower
    is_prores = 'prores' in codec_lower
    if spatial_mode == 'zone':
        if is_nvenc:
            args.extend(['-rc', 'vbr', '-cq', '19', '-b:v', b_val, '-maxrate', b_val, '-bufsize', buf_val])
            args.extend(['-preset', extra_hw_args.get('preset', 'p4'), '-pix_fmt', 'yuv420p'])
        elif is_h264:
            args.extend(['-crf', '19', '-maxrate', b_val, '-bufsize', buf_val, '-aq-mode', '2'])
            args.extend(['-preset', vid_preset, '-pix_fmt', 'yuv420p'])
        elif is_h265:
            args.extend(['-crf', '21', '-maxrate', b_val, '-bufsize', buf_val, '-aq-mode', '2'])
            args.extend(['-preset', vid_preset, '-pix_fmt', 'yuv420p'])
        elif is_vp9:
            args.extend(['-crf', '22', '-b:v', b_val, '-deadline', 'good', '-cpu-used', '2', '-pix_fmt', 'yuv420p'])
        elif is_qsv:
            args.extend(['-b:v', b_val, '-maxrate', b_val, '-bufsize', buf_val, '-preset', 'medium', '-pix_fmt', 'nv12'])
        elif is_vt or is_amf:
            args.extend(['-b:v', b_val, '-maxrate', b_val, '-bufsize', buf_val, '-pix_fmt', 'yuv420p'])
        elif is_prores:
            args.extend(['-profile:v', '3'])
        else:
            args.extend(['-b:v', b_val, '-maxrate', b_val, '-bufsize', buf_val, '-preset', vid_preset, '-pix_fmt', 'yuv420p'])
    elif spatial_mode == 'tiles':
        n_slices = max(2, min(int(rows), 16))
        if is_nvenc:
            args.extend(['-slices', str(n_slices), '-rc', 'vbr', '-cq', '20', '-maxrate', b_val, '-bufsize', buf_val])
            args.extend(['-preset', extra_hw_args.get('preset', 'p4'), '-pix_fmt', 'yuv420p'])
        elif is_h264:
            args.extend([
                '-slices', str(n_slices),
                '-flags', '-loop',
                '-x264opts', 'no-deblock=1',
                '-crf', '20',
                '-maxrate', b_val,
                '-bufsize', buf_val,
                '-preset', vid_preset,
                '-pix_fmt', 'yuv420p'
            ])
        elif is_h265:
            args.extend([
                '-x265-params', f'no-deblock=1:slices={n_slices}',
                '-crf', '21',
                '-maxrate', b_val,
                '-bufsize', buf_val,
                '-preset', vid_preset,
                '-pix_fmt', 'yuv420p'
            ])
        elif is_qsv:
            args.extend(['-slices', str(n_slices), '-b:v', b_val, '-preset', 'medium', '-pix_fmt', 'nv12'])
        elif is_prores:
            args.extend(['-profile:v', '3'])
        else:
            args.extend(['-slices', str(n_slices), '-flags', '-loop', '-b:v', b_val, '-preset', vid_preset, '-pix_fmt', 'yuv420p'])
    else:
        args.extend(['-b:v', b_val])
        if is_vp9:
            args.extend(['-deadline', 'good', '-cpu-used', '2'])
        elif is_nvenc:
            args.extend(['-preset', extra_hw_args.get('preset', 'p4'), '-pix_fmt', 'yuv420p'])
        elif is_vt:
            args.extend(['-pix_fmt', 'yuv420p'])
        elif is_qsv:
            args.extend(['-preset', 'medium', '-pix_fmt', 'nv12'])
        elif is_amf:
            args.extend(['-pix_fmt', 'yuv420p'])
        elif not is_prores:
            args.extend(['-preset', vid_preset])
        if not is_prores and not is_qsv:
            args.extend(['-pix_fmt', 'yuv420p'])
    return args
def _scramble_frame_ordinary(frame, cols, rows, seed, reverse=False):
    h, w = frame.shape[:2]
    blocks = get_blocks(w, h, cols, rows)
    n = len(blocks)
    dest_to_src = {}
    if reverse:
        fwd = seeded_shuffle(list(range(n)), seed)
        for i, v in enumerate(fwd):
            dest_to_src[v] = i
    else:
        shf = seeded_shuffle(list(range(n)), seed)
        for i, v in enumerate(shf):
            dest_to_src[i] = v
    out = np.zeros_like(frame)
    for i in range(n):
        t_idx = dest_to_src[i]
        sx1, sy1, sx2, sy2 = blocks[t_idx]
        dx1, dy1, dx2, dy2 = blocks[i]
        tile = frame[sy1:sy2, sx1:sx2]
        dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
        if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
            tile = cv2.resize(tile, (dw_blk, dh_blk))
        out[dy1:dy2, dx1:dx2] = tile
    return out
def _resolve_zone_pixels(s_roi, out_w, out_h):
    rx1, ry1, rx2, ry2 = s_roi
    if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
        px1, py1 = int(round(rx1 * out_w)), int(round(ry1 * out_h))
        px2, py2 = int(round(rx2 * out_w)), int(round(ry2 * out_h))
    else:
        px1, py1, px2, py2 = int(rx1), int(ry1), int(rx2), int(ry2)
    px1 = max(0, min(out_w, px1))
    py1 = max(0, min(out_h, py1))
    px2 = max(0, min(out_w, px2))
    py2 = max(0, min(out_h, py2))
    return px1, py1, px2, py2
def _zone_nested_geometry(zw, zh, cols, rows, center_size, seed):
    outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(
        cols, rows, zw, zh, center_size=center_size)
    n_outer = len(outer_indices)
    c1, r1 = find_best_grid(n_outer, target_ratio=(cols / rows) if rows else 1.0)
    all_blocks_zone = get_blocks(zw, zh, cols, rows)
    src_blocks_outer_zone = get_blocks(zw, zh, c1, r1)
    shuffled_outer = seeded_shuffle(list(outer_indices), seed)
    if center_size == '2/4':
        s = 0.7071
    elif center_size == '3/4':
        s = 0.866
    else:
        s = 0.5
    cols_inner = max(1, min(cols - 1, int(cols * s)))
    rows_inner = max(1, min(rows - 1, int(rows * s)))
    cw, ch = max(2, cx2 - cx1), max(2, cy2 - cy1)
    center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
    shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)
    dest_to_src_enc = {i: v for i, v in enumerate(shuffled_center)}
    dest_to_src_dec = {v: i for i, v in enumerate(shuffled_center)}
    return {
        "outer_indices": outer_indices,
        "inner_indices": inner_indices,
        "cx1": cx1, "cy1": cy1, "cx2": cx2, "cy2": cy2,
        "cw": cw, "ch": ch,
        "cols_inner": cols_inner, "rows_inner": rows_inner,
        "c1": c1, "r1": r1, "n_outer": n_outer,
        "all_blocks_zone": all_blocks_zone,
        "src_blocks_outer_zone": src_blocks_outer_zone,
        "shuffled_outer": shuffled_outer,
        "center_blocks": center_blocks,
        "dest_to_src_enc": dest_to_src_enc,
        "dest_to_src_dec": dest_to_src_dec,
    }
def _encrypt_zone_nested(zone_bg, center_frame, cols, rows, center_size, seed, video_encrypt_mode):
    zh, zw = zone_bg.shape[:2]
    g = _zone_nested_geometry(zw, zh, cols, rows, center_size, seed)
    new_zone = np.zeros((zh, zw, 3), dtype=np.uint8)
    if video_encrypt_mode in ['external', 'both']:
        for j in range(g["n_outer"]):
            x1, y1, x2, y2 = g["src_blocks_outer_zone"][j]
            tile = zone_bg[y1:y2, x1:x2]
            idx = g["shuffled_outer"][j]
            dx1, dy1, dx2, dy2 = g["all_blocks_zone"][idx]
            tile_resized = cv2.resize(tile, (dx2 - dx1, dy2 - dy1))
            new_zone[dy1:dy2, dx1:dx2] = tile_resized
    else:
        for idx in g["outer_indices"]:
            dx1, dy1, dx2, dy2 = g["all_blocks_zone"][idx]
            new_zone[dy1:dy2, dx1:dx2] = zone_bg[dy1:dy2, dx1:dx2]
    cx1, cy1, cx2, cy2, cw, ch = g["cx1"], g["cy1"], g["cx2"], g["cy2"], g["cw"], g["ch"]
    if center_frame is not None:
        frame_c = cv2.resize(center_frame, (cw, ch))
        if video_encrypt_mode in ['center', 'both']:
            scrambled = np.zeros((ch, cw, 3), dtype=np.uint8)
            cb = g["center_blocks"]
            m = g["dest_to_src_enc"]
            for i in range(g["cols_inner"] * g["rows_inner"]):
                t_idx = m[i]
                sx1, sy1, sx2, sy2 = cb[t_idx]
                dx1, dy1, dx2, dy2 = cb[i]
                tile = frame_c[sy1:sy2, sx1:sx2]
                dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                    tile = cv2.resize(tile, (dw_blk, dh_blk))
                scrambled[dy1:dy2, dx1:dx2] = tile
            frame_c = scrambled
        new_zone[cy1:cy2, cx1:cx2] = frame_c
    else:
        new_zone[cy1:cy2, cx1:cx2] = zone_bg[cy1:cy2, cx1:cx2]
    return new_zone
def _decrypt_zone_nested(zone_enc, cols, rows, center_size, seed, video_encrypt_mode):
    zh, zw = zone_enc.shape[:2]
    g = _zone_nested_geometry(zw, zh, cols, rows, center_size, seed)
    cx1, cy1, cx2, cy2, cw, ch = g["cx1"], g["cy1"], g["cx2"], g["cy2"], g["cw"], g["ch"]
    center_enc = zone_enc[cy1:cy2, cx1:cx2]
    if center_enc.shape[1] != cw or center_enc.shape[0] != ch:
        center_enc = cv2.resize(center_enc, (cw, ch))
    if video_encrypt_mode in ['center', 'both']:
        clean_center = np.zeros((ch, cw, 3), dtype=np.uint8)
        cb = g["center_blocks"]
        m = g["dest_to_src_dec"]
        for i in range(g["cols_inner"] * g["rows_inner"]):
            t_idx = m[i]
            sx1, sy1, sx2, sy2 = cb[t_idx]
            dx1, dy1, dx2, dy2 = cb[i]
            tile = center_enc[sy1:sy2, sx1:sx2]
            dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
            if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                tile = cv2.resize(tile, (dw_blk, dh_blk))
            clean_center[dy1:dy2, dx1:dx2] = tile
    else:
        clean_center = center_enc
    if video_encrypt_mode in ['external', 'both']:
        restored = np.zeros((zh, zw, 3), dtype=np.uint8)
        for j in range(g["n_outer"]):
            idx = g["shuffled_outer"][j]
            dx1, dy1, dx2, dy2 = g["all_blocks_zone"][idx]
            tile = zone_enc[dy1:dy2, dx1:dx2]
            x1, y1, x2, y2 = g["src_blocks_outer_zone"][j]
            tile_resized = cv2.resize(tile, (x2 - x1, y2 - y1))
            restored[y1:y2, x1:x2] = tile_resized
    else:
        restored = zone_enc.copy()
        restored[cy1:cy2, cx1:cx2] = clean_center
    return restored, clean_center
@LiveDebugger.trace(module_name="VIDEO")
def process_video_file(input_path, output_path, options, progress_dict, task_id):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    proc_vid, proc_aud = options.get('process_video'), options.get('process_audio')
    reverse = options.get('reverse') or (options.get('action') == 'unscramble')
    cols, rows, seed = options.get('cols', 1), options.get('rows', 1), options.get('seed', 0)
    target_w, target_h = options.get('target_w'), options.get('target_h')
    no_scale = options.get('no_scale', False)
    carrier_freq = options.get('carrier_freq', 8000)
    video_encrypt_mode = options.get('video_encrypt_mode', 'external')                               
    patch_intervals = options.get('patch_intervals')                                      
    LiveDebugger.log("START_VIDEO", f"Processing video '{os.path.basename(input_path)}' | grid={cols}x{rows}, seed={seed}, mode={video_encrypt_mode}, patch_intervals={patch_intervals}, reverse={reverse}", level="INFO", module="VIDEO")
    center_end_action = options.get('center_end_action', 'loop')                              
    center_aud_action = options.get('center_aud_action', 'silence')                    
    outer_end_action  = options.get('outer_end_action',  'stop')                                      
    temp_aud = get_temp_file_path(os.path.basename(input_path) + "_aud.wav")
    temp_center_aud_out = get_temp_file_path(os.path.basename(input_path) + "_center_aud_out.wav")
    has_audio = subprocess.run([ffmpeg_exe, '-y', '-i', input_path, '-vn', temp_aud], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags).returncode == 0
    if has_audio and not os.path.exists(temp_aud):
        has_audio = False
    if has_audio and proc_aud:
        import soundfile as sf
        main_sr = 48000
        try:
            info_main = sf.info(temp_aud)
            main_sr = info_main.samplerate
        except Exception as e:
            LiveDebugger.log("AUDIO_SR_WARN", f"Failed to read main audio sample rate: {e}", level="WARNING", module="VIDEO")
        has_custom_audio = bool(options.get('custom_audio_l') or options.get('custom_audio_r'))
        if not reverse and has_custom_audio:
            main_data = None
            if os.path.exists(temp_aud):
                try:
                    main_data, _ = sf.read(temp_aud)
                except Exception:
                    main_data = None
            dur_sec = max(1.0, float(output_total_frames if 'output_total_frames' in locals() else total_frames) / max(1.0, float(fps)))
            target_samples = int(round(dur_sec * main_sr))
            data_l = None
            if options.get('custom_audio_l'):
                data_l = _load_or_extract_audio_channel(options['custom_audio_l'], main_sr, ffmpeg_exe, creation_flags)
            if data_l is None:
                if main_data is not None:
                    data_l = main_data[:, 0] if len(main_data.shape) > 1 else main_data
                else:
                    data_l = np.zeros(target_samples, dtype=np.float32)
            data_l = _adjust_audio_length(data_l, target_samples, action=options.get('track_l_action', 'loop'))
            data_r = None
            if options.get('custom_audio_r'):
                data_r = _load_or_extract_audio_channel(options['custom_audio_r'], main_sr, ffmpeg_exe, creation_flags)
            if data_r is None:
                if main_data is not None:
                    data_r = main_data[:, 1] if (len(main_data.shape) > 1 and main_data.shape[1] > 1) else (main_data[:, 0] if len(main_data.shape) > 1 else main_data)
                else:
                    data_r = data_l.copy()
            data_r = _adjust_audio_length(data_r, target_samples, action=options.get('track_r_action', 'loop'))
            enc_l = options.get('custom_audio_l_enc', True)
            enc_r = options.get('custom_audio_r_enc', True)
            if enc_l:
                tmp_l = get_temp_file_path("track_l_proc.wav")
                sf.write(tmp_l, data_l, main_sr)
                process_audio_file(tmp_l, tmp_l, is_decrypt=False, method=options.get('aud_method', 'inversion'),
                                   key=options.get('aud_key', 42), num_splits=options.get('aud_splits', 10),
                                   carrier_freq=carrier_freq, vol_factor=options.get('vol_factor', 1.0),
                                   aud_track='both', patch_intervals=patch_intervals)
                data_l, _ = sf.read(tmp_l)
                if len(data_l.shape) > 1: data_l = data_l[:, 0]
                if os.path.exists(tmp_l):
                    try: os.remove(tmp_l)
                    except Exception: pass
            if enc_r:
                tmp_r = get_temp_file_path("track_r_proc.wav")
                sf.write(tmp_r, data_r, main_sr)
                process_audio_file(tmp_r, tmp_r, is_decrypt=False, method=options.get('aud_method', 'inversion'),
                                   key=options.get('aud_key', 42), num_splits=options.get('aud_splits', 10),
                                   carrier_freq=carrier_freq, vol_factor=options.get('vol_factor', 1.0),
                                   aud_track='both', patch_intervals=patch_intervals)
                data_r, _ = sf.read(tmp_r)
                if len(data_r.shape) > 1: data_r = data_r[:, 0]
                if os.path.exists(tmp_r):
                    try: os.remove(tmp_r)
                    except Exception: pass
            stereo_data = np.vstack((data_l, data_r)).T
            sf.write(temp_aud, stereo_data, main_sr)
        elif not reverse and options.get('center') and options.get('dual_track'):
            vol_bg = options.get('vol_factor_bg', options.get('vol_factor', 1.0))
            vol_center = options.get('vol_factor_center', 1.0)
            process_audio_file(
                temp_aud, temp_aud, is_decrypt=False,
                method=options.get('aud_method', 'inversion'),
                key=options.get('aud_key', 42),
                num_splits=options.get('aud_splits', 10),
                carrier_freq=carrier_freq,
                vol_factor=vol_bg,
                aud_track=options.get('aud_track', 'both'),
                patch_intervals=patch_intervals
            )
            temp_center_aud = get_temp_file_path(os.path.basename(options['center_path']) + "_center_aud.wav")
            has_center_audio = subprocess.run([ffmpeg_exe, '-y', '-i', options['center_path'], '-vn', '-ar', str(main_sr), temp_center_aud], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags).returncode == 0
            main_data, main_sr = sf.read(temp_aud)
            if len(main_data.shape) > 1:
                main_data = main_data[:, 0]
            center_data = None
            if has_center_audio and os.path.exists(temp_center_aud):
                center_data, center_sr = sf.read(temp_center_aud)
                if len(center_data.shape) > 1:
                    center_data = center_data[:, 0]
                center_data = _adjust_audio_length(center_data, len(main_data), center_aud_action) * vol_center
                os.remove(temp_center_aud)
            else:
                center_data = np.zeros_like(main_data)
            stereo_data = np.vstack((main_data, center_data)).T
            sf.write(temp_aud, stereo_data, main_sr)
        elif reverse and options.get('dual_track'):
            stereo_data, sr = sf.read(temp_aud)
            if len(stereo_data.shape) > 1 and stereo_data.shape[1] > 1:
                left_data  = stereo_data[:, 0]
                right_data = stereo_data[:, 1]
                sf.write(temp_center_aud_out, right_data, sr)
            else:
                left_data = stereo_data
            sf.write(temp_aud, left_data, sr)
            process_audio_file(
                temp_aud, temp_aud, is_decrypt=True,
                method=options.get('aud_method', 'inversion'),
                key=options.get('aud_key', 42),
                num_splits=options.get('aud_splits', 10),
                carrier_freq=carrier_freq,
                vol_factor=options.get('vol_factor', 1.0),
                aud_track='both',                                         
                patch_intervals=patch_intervals
            )
            dec_data, dec_sr = sf.read(temp_aud)
            if len(dec_data.shape) == 1:
                dec_stereo = np.vstack((dec_data, dec_data)).T
                sf.write(temp_aud, dec_stereo, dec_sr)
        else:
            process_audio_file(
                temp_aud, temp_aud, is_decrypt=reverse,
                method=options.get('aud_method', 'inversion'),
                key=options.get('aud_key', 42),
                num_splits=options.get('aud_splits', 10),
                carrier_freq=carrier_freq,
                vol_factor=options.get('vol_factor', 1.0),
                aud_track=options.get('aud_track', 'both'),
                patch_intervals=patch_intervals
            )
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        from core.metadata_prober import probe_media_file
        info = probe_media_file(input_path)
        dur_sec = info.get('duration_sec')
        if dur_sec and dur_sec > 0:
            total_frames = int(dur_sec * fps)
        else:
            total_frames = 999999
    out_w = target_w if target_w else int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    out_h = target_h if target_h else int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    all_blocks = get_blocks(out_w, out_h, cols, rows)                             
    n_blocks = len(all_blocks)                                          
    dest_to_src = {idx: idx for idx in range(n_blocks)}
    center_size = options.get('center_size', '1/4')
    outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, out_w, out_h, center_size=center_size)
    N_outer = len(outer_indices)
    C1, R1 = find_best_grid(N_outer, target_ratio=cols/rows)
    src_blocks_outer = get_blocks(out_w, out_h, C1, R1)
    shuffled_outer = seeded_shuffle(list(outer_indices), seed)
    cw = cx2 - cx1
    ch = cy2 - cy1
    if center_size == '2/4':
        s = 0.7071
    elif center_size == '3/4':
        s = 0.866
    else:
        s = 0.5
    cols_inner = max(1, min(cols - 1, int(cols * s)))
    rows_inner = max(1, min(rows - 1, int(rows * s)))
    center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
    dest_to_src_center = {idx: idx for idx in range(cols_inner * rows_inner)}
    shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)
    if reverse:
        for i, v in enumerate(shuffled_center):
            dest_to_src_center[v] = i
    else:
        for i, v in enumerate(shuffled_center):
            dest_to_src_center[i] = v
    if proc_vid and not options.get('center'):
        if reverse:
            fwd = seeded_shuffle(list(range(n_blocks)), seed)
            for i, v in enumerate(fwd):
                dest_to_src[v] = i
        else:
            shuffled = seeded_shuffle(list(range(n_blocks)), seed)
            for i, v in enumerate(shuffled):
                dest_to_src[i] = v
    patch_segments_cfg = options.get('patch_segments')
    global_roi = options.get('patch_roi')
    global_invert = options.get('roi_invert', False)
    placement = options.get('marker_placement', 'outside')
    _may_combine = bool(options.get('center_path') or options.get('center')) and (
        bool(patch_segments_cfg) or bool(global_roi) or bool(options.get('optical_markers')))
    if _may_combine and options.get('optical_markers') and placement == 'inside':
        LiveDebugger.log("MARKER_PLACEMENT", "Zone+Center mode: 'inside' corner markers would be overwritten by the pasted center content. Coercing marker_placement to 'outside' (markers are stamped on the background after compositing).", level="WARNING", module="VIDEO")
        placement = 'outside'
        options['marker_placement'] = 'outside'
    discovered_zones = []
    def _get_effective_roi_blocks(r_roi, inv):
        if not r_roi:
            return None
        rx1, ry1, rx2, ry2 = r_roi
        if options.get('optical_markers') and placement == 'inside':
            if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
                px1, py1 = int(math.floor(rx1 * out_w)), int(math.floor(ry1 * out_h))
                px2, py2 = int(math.ceil(rx2 * out_w)), int(math.ceil(ry2 * out_h))
            else:
                px1, py1 = int(math.floor(rx1)), int(math.floor(ry1))
                px2, py2 = int(math.ceil(rx2)), int(math.ceil(ry2))
            m_size = 18
            inner_px1 = min(px2, px1 + m_size)
            inner_py1 = min(py2, py1 + m_size)
            inner_px2 = max(inner_px1, px2 - m_size)
            inner_py2 = max(inner_py1, py2 - m_size)
            if (inner_px2 - inner_px1) >= 20 and (inner_py2 - inner_py1) >= 20:
                inner_roi = [inner_px1 / out_w, inner_py1 / out_h, inner_px2 / out_w, inner_py2 / out_h]
                return get_roi_blocks(out_w, out_h, inner_roi, cols, rows, invert=inv)
        return get_roi_blocks(out_w, out_h, r_roi, cols, rows, invert=inv)
    def _create_zone_dict(roi_norm):
        rx1, ry1, rx2, ry2 = roi_norm
        px1, py1 = int(math.floor(rx1 * out_w)), int(math.floor(ry1 * out_h))
        px2, py2 = int(math.ceil(rx2 * out_w)), int(math.ceil(ry2 * out_h))
        m_boxes = _calculate_marker_boxes(out_w, out_h, px1, py1, px2, py2, placement=placement, size=18)
        z_blocks = _get_effective_roi_blocks(roi_norm, global_invert)
        n_b = len(z_blocks)
        z_map = {}
        if reverse:
            fwd = seeded_shuffle(list(range(n_b)), seed)
            for i, v in enumerate(fwd): z_map[v] = i
        else:
            shf = seeded_shuffle(list(range(n_b)), seed)
            for i, v in enumerate(shf): z_map[i] = v
        return {
            "roi": [rx1, ry1, rx2, ry2],
            "pixel_roi": [px1, py1, px2, py2],
            "marker_coords": m_boxes,
            "blocks": z_blocks,
            "mapping": z_map,
            "invert": global_invert
        }
    if reverse and options.get('optical_markers') and not global_roi and not patch_segments_cfg:
        LiveDebugger.log("MARKER_DETECT", f"Optical marker tag found in key (|opt_{placement[:3]}). Auto-scanning video for markers across timeline...", level="INFO", module="VIDEO")
        probe_cap = cv2.VideoCapture(input_path)
        if probe_cap.isOpened():
            tot_p = int(probe_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            sample_count = min(30, tot_p) if tot_p > 0 else 10
            step = max(1, tot_p // sample_count) if tot_p > 0 else 1
            cur_idx = 0
            while cur_idx < tot_p:
                probe_cap.set(cv2.CAP_PROP_POS_FRAMES, cur_idx)
                ret_p, frame_p = probe_cap.read()
                if not ret_p or frame_p is None:
                    break
                found_rois = detect_all_optical_markers(frame_p, placement=placement)
                for f_roi in found_rois:
                    if not any(
                        abs(f_roi[0] - z["roi"][0]) < 0.02 and
                        abs(f_roi[1] - z["roi"][1]) < 0.02 and
                        abs(f_roi[2] - z["roi"][2]) < 0.02 and
                        abs(f_roi[3] - z["roi"][3]) < 0.02
                        for z in discovered_zones
                    ):
                        discovered_zones.append(_create_zone_dict(f_roi))
                cur_idx += step
            probe_cap.release()
        if discovered_zones:
            global_roi = list(discovered_zones[0]["roi"])
            options['patch_roi'] = global_roi
            LiveDebugger.log("MARKER_DETECT", f"Auto-detected {len(discovered_zones)} optical marker zone(s)! ROIs: {[z['roi'] for z in discovered_zones]}", level="SUCCESS", module="VIDEO")
        else:
            LiveDebugger.log("MARKER_DETECT", "Warning: Optical marker tag present in key, but markers could not be detected in probed video frames.", level="WARNING", module="VIDEO")
    elif options.get('optical_markers') and global_roi:
        norm_g_roi = list(global_roi)
        if norm_g_roi[0] > 1.0 or norm_g_roi[1] > 1.0 or norm_g_roi[2] > 1.0 or norm_g_roi[3] > 1.0:
            norm_g_roi = [norm_g_roi[0] / out_w, norm_g_roi[1] / out_h, norm_g_roi[2] / out_w, norm_g_roi[3] / out_h]
        discovered_zones.append(_create_zone_dict(norm_g_roi))
    marker_coords = discovered_zones[0]["marker_coords"] if discovered_zones else None
    segment_lookup = []
    if patch_segments_cfg and isinstance(patch_segments_cfg, list):
        for seg in patch_segments_cfg:
            s_start = float(seg.get('start', 0.0))
            s_end = float(seg.get('end', 999999.0))
            s_roi = seg.get('roi', global_roi)
            s_inv = seg.get('invert', global_invert)
            blocks = None
            mapping = None
            if s_roi:
                blocks = _get_effective_roi_blocks(s_roi, s_inv)
                n_b = len(blocks)
                mapping = {}
                if reverse:
                    fwd = seeded_shuffle(list(range(n_b)), seed)
                    for i, v in enumerate(fwd): mapping[v] = i
                else:
                    shf = seeded_shuffle(list(range(n_b)), seed)
                    for i, v in enumerate(shf): mapping[i] = v
            segment_lookup.append({
                "start": s_start, "end": s_end, "roi": s_roi, "invert": s_inv,
                "blocks": blocks, "mapping": mapping
            })
    elif global_roi:
        g_blocks = _get_effective_roi_blocks(global_roi, global_invert)
        n_b = len(g_blocks)
        g_mapping = {}
        if reverse:
            fwd = seeded_shuffle(list(range(n_b)), seed)
            for i, v in enumerate(fwd): g_mapping[v] = i
        else:
            shf = seeded_shuffle(list(range(n_b)), seed)
            for i, v in enumerate(shf): g_mapping[i] = v
        segment_lookup.append({
            "start": 0.0, "end": 999999.0, "roi": global_roi, "invert": global_invert,
            "blocks": g_blocks, "mapping": g_mapping
        })
    if not reverse and options.get('export_svg', True):
        try:
            base, _ = os.path.splitext(output_path)
            export_grid_to_svg(f"{base}_grid.svg", out_w, out_h, cols, rows, has_center=options.get('center', False), center_size=center_size)
            export_scrambled_grid_to_svg(f"{base}_grid_original.svg", out_w, out_h, cols, rows, seed, has_center=options.get('center', False), center_size=center_size, prefix_original=True)
            export_scrambled_grid_to_svg(f"{base}_grid_scrambled.svg", out_w, out_h, cols, rows, seed, has_center=options.get('center', False), center_size=center_size, prefix_original=False)
        except Exception as e:
            LiveDebugger.log("SVG_EXPORT_WARN", f"Failed to export SVG grids: {e}", level="WARNING", module="VIDEO")
    cap_center = None
    fps_c = 30.0
    total_frames_c = 0
    frame_step_c = 1.0
    wants_center = bool(options.get('center')) or bool(segment_lookup)
    if wants_center and not reverse and options.get('center_path'):
        cap_center = cv2.VideoCapture(options['center_path'])
        fps_c = cap_center.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames_c = int(cap_center.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames_c <= 0:
            from core.metadata_prober import probe_media_file
            info_c = probe_media_file(options['center_path'])
            dur_sec_c = info_c.get('duration_sec')
            if dur_sec_c and dur_sec_c > 0:
                total_frames_c = int(dur_sec_c * fps_c)
        frame_step_c = fps_c / fps
    if cap_center and total_frames_c > 0 and outer_end_action != 'stop':
        center_frames_adapted = int(total_frames_c / frame_step_c)
        output_total_frames = max(total_frames, center_frames_adapted)
    else:
        output_total_frames = total_frames                                
    vid_codec = options.get('vid_codec', 'libx264')
    vid_preset = options.get('vid_preset', 'medium')
    use_gpu = options.get('use_gpu', False)
    spatial_mode = options.get('spatial_compression_mode', 'off')
    chosen_codec, hw_type, extra_hw_args = resolve_video_encoder(vid_codec, use_gpu=use_gpu)
    if hw_type != 'software':
        LiveDebugger.log("GPU_ACCEL", f"Hardware acceleration enabled: using {chosen_codec} ({hw_type})", level="INFO", module="VIDEO")
    if spatial_mode != 'off':
        LiveDebugger.log("SPATIAL_COMP", f"Spatial compression mode active: '{spatial_mode}' (rows={rows}, cols={cols})", level="INFO", module="VIDEO")
    cmd = [ffmpeg_exe, '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
           '-s', f'{out_w}x{out_h}', '-pix_fmt', 'bgr24', '-r', str(fps), '-i', '-']
    if has_audio:
        cmd.extend(['-i', temp_aud])
    enc_args = build_video_encoder_args(
        chosen_codec,
        options.get('vid_bitrate', '3000k'),
        vid_preset,
        spatial_mode=spatial_mode,
        rows=rows,
        cols=cols,
        extra_hw_args=extra_hw_args
    )
    cmd.extend(enc_args)
    if has_audio:
        aud_c = options.get('aud_codec', 'aac')
        aud_sr = str(options.get('aud_sr', '48000'))
        from core.metadata_prober import sanitize_audio_bitrate
        aud_b = sanitize_audio_bitrate(options.get('aud_bitrate', '320k'), aud_c)
        if aud_b and aud_c not in ['pcm_s16le', 'flac']:
            cmd.extend(['-c:a', aud_c, '-b:a', aud_b, '-ar', aud_sr])
        else:
            cmd.extend(['-c:a', aud_c, '-ar', aud_sr])
    else:
        cmd.extend(['-an'])
    cmd.append(output_path)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
    proc_center = None
    center_w, center_h = cw, ch
    if reverse and options.get('center'):
        base, ext = os.path.splitext(output_path)
        output_path_center = f"{base}_center{ext}"
        has_center_aud_out = os.path.exists(temp_center_aud_out)
        if options.get('center_in_zone', True) and (segment_lookup or global_roi or discovered_zones):
            target_roi = None
            if segment_lookup and segment_lookup[0].get('roi'):
                target_roi = segment_lookup[0].get('roi')
            elif global_roi:
                target_roi = global_roi
            elif discovered_zones:
                target_roi = discovered_zones[0].get('roi')
            if target_roi:
                zx1, zy1, zx2, zy2 = _resolve_zone_pixels(target_roi, out_w, out_h)
                zw_v = max(2, zx2 - zx1)
                zh_v = max(2, zy2 - zy1)
                try:
                    _zg = _zone_nested_geometry(zw_v, zh_v, cols, rows, center_size, seed)
                    _cw_v, _ch_v = max(2, _zg["cw"]), max(2, _zg["ch"])
                except Exception:
                    _cw_v, _ch_v = zw_v, zh_v
                if _cw_v % 2 != 0: _cw_v += 1
                if _ch_v % 2 != 0: _ch_v += 1
                center_w, center_h = _cw_v, _ch_v
        cmd_center = [ffmpeg_exe, '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
                      '-s', f'{center_w}x{center_h}', '-pix_fmt', 'bgr24', '-r', str(fps), '-i', '-']
        if has_center_aud_out:
            cmd_center.extend(['-i', temp_center_aud_out])
        enc_args_center = build_video_encoder_args(
            chosen_codec,
            options.get('vid_bitrate', '3000k'),
            vid_preset,
            spatial_mode=spatial_mode,
            rows=rows_inner if options.get('center') else rows,
            cols=cols_inner if options.get('center') else cols,
            extra_hw_args=extra_hw_args
        )
        cmd_center.extend(enc_args_center)
        if has_center_aud_out:
            aud_c = options.get('aud_codec', 'aac')
            aud_sr = str(options.get('aud_sr', '48000'))
            aud_b = sanitize_audio_bitrate(options.get('aud_bitrate', '320k'), aud_c)
            if aud_b and aud_c not in ['pcm_s16le', 'flac']:
                cmd_center.extend(['-c:a', aud_c, '-b:a', aud_b, '-ar', aud_sr])
            else:
                cmd_center.extend(['-c:a', aud_c, '-ar', aud_sr])
        else:
            cmd_center.extend(['-an'])
        cmd_center.append(output_path_center)
        proc_center = subprocess.Popen(cmd_center, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
    def write_pipe_frame(p, data):
        try:
            p.stdin.write(data)
        except (BrokenPipeError, OSError) as err:
            stderr_msg = ""
            try:
                if p.stdin and not p.stdin.closed:
                    p.stdin.close()
                p.stdin = None
                _, err_bytes = p.communicate(timeout=2)
                if err_bytes:
                    stderr_msg = err_bytes.decode('utf-8', errors='ignore')
            except Exception:
                pass
            raise RuntimeError(f"FFmpeg process ended unexpectedly: {stderr_msg.strip() or str(err)}") from err
    try:
        frame_count = 0
        last_outer_frame = None                                       
        last_center_frame = None                                       
        outer_exhausted = False
        center_exhausted = False
        zone_miss_counts = {}
        accumulated_c = 0.0                                        
        center_read_cursor = 0                                                               
        while frame_count < output_total_frames:
            ret, frame = cap.read()
            if not ret:
                outer_exhausted = True
                if outer_end_action == 'loop':
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break                     
                elif outer_end_action == 'freeze' and last_outer_frame is not None:
                    frame = last_outer_frame.copy()
                elif outer_end_action == 'black' and last_outer_frame is not None:
                    frame = np.zeros_like(last_outer_frame)
                else:
                    break                            
            if frame is not None:
                last_outer_frame = frame
            if frame is not None and (out_w != frame.shape[1] or out_h != frame.shape[0]):
                if no_scale:
                    canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
                    orig_h, orig_w = frame.shape[:2]
                    copy_w, copy_h = min(out_w, orig_w), min(out_h, orig_h)
                    cxo, cyo = (out_w - copy_w) // 2, (out_h - copy_h) // 2
                    fxo, fyo = (orig_w - copy_w) // 2, (orig_h - copy_h) // 2
                    canvas[cyo:cyo+copy_h, cxo:cxo+copy_w] = frame[fyo:fyo+copy_h, fxo:fxo+copy_w]
                    frame = canvas
                else:
                    frame = cv2.resize(frame, (out_w, out_h))
            current_sec = frame_count / fps
            is_in_patch = True
            if patch_intervals is not None:
                is_in_patch = any(start_s <= current_sec <= end_s for start_s, end_s in patch_intervals)
            if reverse and options.get('optical_markers'):
                is_in_patch = True
            if proc_vid and is_in_patch:
                if options.get('center'):
                    _zc_dec = bool(reverse and options.get('center_in_zone', True)
                                   and (segment_lookup or discovered_zones or options.get('optical_markers')))
                    _zc_enc = bool(not reverse and options.get('center_in_zone', True)
                                   and segment_lookup and cap_center)
                    if _zc_dec:
                        zc_rects = []
                        if options.get('optical_markers'):
                            for z in discovered_zones:
                                z_id = id(z)
                                if check_marker_presence(frame, z["marker_coords"], marker_size=18):
                                    zone_miss_counts[z_id] = 0
                                    zc_rects.append(z["pixel_roi"])
                                elif zone_miss_counts.get(z_id, 99) < 2:
                                    zone_miss_counts[z_id] += 1
                                    zc_rects.append(z["pixel_roi"])
                            scan_interval = 5 if not zc_rects else 30
                            if (frame_count % scan_interval == 0) or (frame_count < 10 and not discovered_zones):
                                found_rois = detect_all_optical_markers(frame, placement=placement)
                                for f_roi in found_rois:
                                    if not any(
                                        abs(f_roi[0] - z["roi"][0]) < 0.02 and
                                        abs(f_roi[1] - z["roi"][1]) < 0.02 and
                                        abs(f_roi[2] - z["roi"][2]) < 0.02 and
                                        abs(f_roi[3] - z["roi"][3]) < 0.02
                                        for z in discovered_zones
                                    ):
                                        new_z = _create_zone_dict(f_roi)
                                        discovered_zones.append(new_z)
                                        if check_marker_presence(frame, new_z["marker_coords"], marker_size=18):
                                            zc_rects.append(new_z["pixel_roi"])
                        elif segment_lookup:
                            for s_info in segment_lookup:
                                if s_info["start"] <= current_sec <= s_info["end"] and s_info.get("roi"):
                                    qx1, qy1, qx2, qy2 = _resolve_zone_pixels(s_info["roi"], out_w, out_h)
                                    if qx2 > qx1 and qy2 > qy1:
                                        zc_rects.append([qx1, qy1, qx2, qy2])
                        if zc_rects:
                            new_frame = frame.copy()
                            for z_i, (px1, py1, px2, py2) in enumerate(zc_rects):
                                zw, zh = max(2, px2 - px1), max(2, py2 - py1)
                                patch = frame[py1:py2, px1:px2]
                                if patch.size == 0:
                                    continue
                                if patch.shape[1] != zw or patch.shape[0] != zh:
                                    patch = cv2.resize(patch, (zw, zh))
                                restored_zone, clean_center = _decrypt_zone_nested(
                                    patch, cols, rows, center_size, seed, video_encrypt_mode)
                                new_frame[py1:py2, px1:px2] = restored_zone
                                if options.get('optical_markers'):
                                    new_frame = inpaint_optical_markers(new_frame, px1, py1, px2, py2, placement=placement)
                                if proc_center and z_i == 0:
                                    center_out = cv2.resize(clean_center, (center_w, center_h))
                                    write_pipe_frame(proc_center, center_out.tobytes())
                            write_pipe_frame(proc, new_frame.tobytes())
                        else:
                            write_pipe_frame(proc, frame.tobytes())
                            if proc_center:
                                write_pipe_frame(proc_center, np.zeros((center_h, center_w, 3), dtype=np.uint8).tobytes())
                    elif _zc_enc:
                        active_segs = [s for s in segment_lookup if s["start"] <= current_sec <= s["end"]]
                        if active_segs:
                            target_c_idx = int(accumulated_c)
                            while center_read_cursor <= target_c_idx:
                                rc, fc = cap_center.read()
                                if not rc:
                                    center_exhausted = True
                                    break
                                last_center_frame = fc
                                center_read_cursor += 1
                            if center_exhausted and center_end_action == 'loop':
                                cap_center.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                center_read_cursor = 0
                                accumulated_c = 0.0
                                center_exhausted = False
                                rc, fc = cap_center.read()
                                if rc:
                                    last_center_frame = fc
                                    center_read_cursor = 1
                            elif center_exhausted and center_end_action == 'black':
                                last_center_frame = np.zeros((2, 2, 3), dtype=np.uint8)
                            center_patch = last_center_frame
                            accumulated_c += frame_step_c
                            new_frame = frame.copy()
                            for seg in active_segs:
                                s_roi = seg.get("roi")
                                if not s_roi:
                                    continue
                                px1, py1, px2, py2 = _resolve_zone_pixels(s_roi, out_w, out_h)
                                if px2 <= px1 or py2 <= py1:
                                    continue
                                zw, zh = max(2, px2 - px1), max(2, py2 - py1)
                                zone_bg = frame[py1:py2, px1:px2]
                                if zone_bg.shape[1] != zw or zone_bg.shape[0] != zh:
                                    zone_bg = cv2.resize(zone_bg, (zw, zh))
                                if center_patch is not None:
                                    new_zone = _encrypt_zone_nested(
                                        zone_bg, center_patch, cols, rows,
                                        center_size, seed, video_encrypt_mode)
                                    new_frame[py1:py2, px1:px2] = new_zone
                                else:
                                    s_blocks = seg.get("blocks")
                                    s_mapping = seg.get("mapping")
                                    if s_blocks and s_mapping:
                                        for i in range(len(s_blocks)):
                                            t_idx = s_mapping[i]
                                            sx1, sy1, sx2, sy2 = s_blocks[t_idx]
                                            dx1, dy1, dx2, dy2 = s_blocks[i]
                                            tile = frame[sy1:sy2, sx1:sx2]
                                            dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                            if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                                tile = cv2.resize(tile, (dw_blk, dh_blk))
                                            new_frame[dy1:dy2, dx1:dx2] = tile
                                if options.get('optical_markers'):
                                    new_frame, _ = stamp_optical_markers(new_frame, px1, py1, px2, py2, placement=placement)
                            write_pipe_frame(proc, new_frame.tobytes())
                        else:
                            write_pipe_frame(proc, frame.tobytes())
                    elif reverse:
                        restored_frame = np.zeros((out_h, out_w, 3), dtype=np.uint8)
                        if video_encrypt_mode in ['external', 'both']:
                            for j in range(N_outer):
                                idx = shuffled_outer[j]
                                dx1, dy1, dx2, dy2 = all_blocks[idx]
                                tile = frame[dy1:dy2, dx1:dx2]
                                x1, y1, x2, y2 = src_blocks_outer[j]
                                tile_resized = cv2.resize(tile, (x2 - x1, y2 - y1))
                                restored_frame[y1:y2, x1:x2] = tile_resized
                        else:
                            restored_frame = frame.copy()
                        center_frame = frame[cy1:cy2, cx1:cx2]
                        if video_encrypt_mode in ['center', 'both']:
                            unscrambled_c = np.zeros((ch, cw, 3), dtype=np.uint8)
                            for i in range(cols_inner * rows_inner):
                                t_idx = dest_to_src_center[i]
                                sx1, sy1, sx2, sy2 = center_blocks[t_idx]
                                dx1, dy1, dx2, dy2 = center_blocks[i]
                                tile = center_frame[sy1:sy2, sx1:sx2]
                                dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                    tile = cv2.resize(tile, (dw_blk, dh_blk))
                                unscrambled_c[dy1:dy2, dx1:dx2] = tile
                            center_frame_to_write = unscrambled_c
                        else:
                            center_frame_to_write = center_frame
                        write_pipe_frame(proc, restored_frame.tobytes())
                        if proc_center:
                            center_out = cv2.resize(center_frame_to_write, (cw, ch))
                            write_pipe_frame(proc_center, center_out.tobytes())
                    else:
                        new_frame = np.zeros((out_h, out_w, 3), dtype=np.uint8)
                        if video_encrypt_mode in ['external', 'both']:
                            for j in range(N_outer):
                                x1, y1, x2, y2 = src_blocks_outer[j]
                                tile = frame[y1:y2, x1:x2]
                                idx = shuffled_outer[j]
                                dx1, dy1, dx2, dy2 = all_blocks[idx]
                                tile_resized = cv2.resize(tile, (dx2 - dx1, dy2 - dy1))
                                new_frame[dy1:dy2, dx1:dx2] = tile_resized
                        else:
                            for idx in outer_indices:
                                dx1, dy1, dx2, dy2 = all_blocks[idx]
                                new_frame[dy1:dy2, dx1:dx2] = frame[dy1:dy2, dx1:dx2]
                        if cap_center:
                            target_c_idx = int(accumulated_c)
                            while center_read_cursor <= target_c_idx:
                                rc, fc = cap_center.read()
                                if not rc:
                                    center_exhausted = True
                                    break
                                last_center_frame = fc
                                center_read_cursor += 1
                            if center_exhausted:
                                if center_end_action == 'loop':
                                    cap_center.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                    center_read_cursor = 0
                                    accumulated_c = 0.0
                                    center_exhausted = False
                                    rc, fc = cap_center.read()
                                    if rc:
                                        last_center_frame = fc
                                        center_read_cursor = 1
                                elif center_end_action == 'black':
                                    last_center_frame = np.zeros((ch, cw, 3), dtype=np.uint8)
                            frame_c = last_center_frame
                            accumulated_c += frame_step_c
                            if frame_c is not None:
                                frame_c_resized = cv2.resize(frame_c, (cw, ch))
                                if video_encrypt_mode in ['center', 'both']:
                                    scrambled_c = np.zeros((ch, cw, 3), dtype=np.uint8)
                                    for i in range(cols_inner * rows_inner):
                                        t_idx = dest_to_src_center[i]
                                        sx1, sy1, sx2, sy2 = center_blocks[t_idx]
                                        dx1, dy1, dx2, dy2 = center_blocks[i]
                                        tile = frame_c_resized[sy1:sy2, sx1:sx2]
                                        dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                        if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                            tile = cv2.resize(tile, (dw_blk, dh_blk))
                                        scrambled_c[dy1:dy2, dx1:dx2] = tile
                                    frame_c_resized = scrambled_c
                                new_frame[cy1:cy2, cx1:cx2] = frame_c_resized
                        write_pipe_frame(proc, new_frame.tobytes())
                else:
                    matched_seg = None
                    if reverse and options.get('optical_markers'):
                        active_marker_zones = []
                        for z in discovered_zones:
                            z_id = id(z)
                            if check_marker_presence(frame, z["marker_coords"], marker_size=18):
                                zone_miss_counts[z_id] = 0
                                active_marker_zones.append(z)
                            elif zone_miss_counts.get(z_id, 99) < 2:
                                zone_miss_counts[z_id] += 1
                                active_marker_zones.append(z)
                        scan_interval = 5 if not active_marker_zones else 30
                        if (frame_count % scan_interval == 0) or (frame_count < 10 and not discovered_zones):
                            found_rois = detect_all_optical_markers(frame, placement=placement)
                            for f_roi in found_rois:
                                if not any(
                                    abs(f_roi[0] - z["roi"][0]) < 0.02 and
                                    abs(f_roi[1] - z["roi"][1]) < 0.02 and
                                    abs(f_roi[2] - z["roi"][2]) < 0.02 and
                                    abs(f_roi[3] - z["roi"][3]) < 0.02
                                    for z in discovered_zones
                                ):
                                    new_z = _create_zone_dict(f_roi)
                                    discovered_zones.append(new_z)
                                    if check_marker_presence(frame, new_z["marker_coords"], marker_size=18):
                                        if new_z not in active_marker_zones:
                                            active_marker_zones.append(new_z)
                        if active_marker_zones:
                            new_frame = frame.copy()
                            for z in active_marker_zones:
                                s_blocks = z["blocks"]
                                s_mapping = z["mapping"]
                                n_s_blocks = len(s_blocks)
                                for i in range(n_s_blocks):
                                    t_idx = s_mapping[i]
                                    sx1, sy1, sx2, sy2 = s_blocks[t_idx]
                                    dx1, dy1, dx2, dy2 = s_blocks[i]
                                    tile = frame[sy1:sy2, sx1:sx2]
                                    dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                    if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                        tile = cv2.resize(tile, (dw_blk, dh_blk))
                                    new_frame[dy1:dy2, dx1:dx2] = tile
                                px1, py1, px2, py2 = z["pixel_roi"]
                                new_frame = inpaint_optical_markers(new_frame, px1, py1, px2, py2, placement=placement)
                            write_pipe_frame(proc, new_frame.tobytes())
                        else:
                            write_pipe_frame(proc, frame.tobytes())
                    elif not reverse and segment_lookup:
                        active_segs = [s for s in segment_lookup if s["start"] <= current_sec <= s["end"]]
                        if active_segs:
                            use_zone_center = bool(cap_center and options.get('center_in_zone', True))
                            center_patch = None
                            if use_zone_center:
                                target_c_idx = int(accumulated_c)
                                while center_read_cursor <= target_c_idx:
                                    rc, fc = cap_center.read()
                                    if not rc:
                                        center_exhausted = True
                                        break
                                    last_center_frame = fc
                                    center_read_cursor += 1
                                if center_exhausted and center_end_action == 'loop':
                                    cap_center.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                    center_read_cursor = 0
                                    accumulated_c = 0.0
                                    center_exhausted = False
                                    rc, fc = cap_center.read()
                                    if rc:
                                        last_center_frame = fc
                                        center_read_cursor = 1
                                elif center_exhausted and center_end_action == 'black':
                                    last_center_frame = np.zeros((2, 2, 3), dtype=np.uint8)
                                center_patch = last_center_frame
                                accumulated_c += frame_step_c
                            new_frame = frame.copy()
                            for seg in active_segs:
                                s_roi = seg["roi"]
                                if not s_roi:
                                    continue
                                px1, py1, px2, py2 = _resolve_zone_pixels(s_roi, out_w, out_h)
                                if px2 <= px1 or py2 <= py1:
                                    continue
                                zw, zh = max(2, px2 - px1), max(2, py2 - py1)
                                if use_zone_center and center_patch is not None:
                                    zone_bg = frame[py1:py2, px1:px2]
                                    if zone_bg.shape[1] != zw or zone_bg.shape[0] != zh:
                                        zone_bg = cv2.resize(zone_bg, (zw, zh))
                                    new_zone = _encrypt_zone_nested(
                                        zone_bg, center_patch, cols, rows,
                                        center_size, seed, video_encrypt_mode)
                                    new_frame[py1:py2, px1:px2] = new_zone
                                else:
                                    s_blocks = seg["blocks"]
                                    s_mapping = seg["mapping"]
                                    for i in range(len(s_blocks)):
                                        t_idx = s_mapping[i]
                                        sx1, sy1, sx2, sy2 = s_blocks[t_idx]
                                        dx1, dy1, dx2, dy2 = s_blocks[i]
                                        tile = frame[sy1:sy2, sx1:sx2]
                                        dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                        if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                            tile = cv2.resize(tile, (dw_blk, dh_blk))
                                        new_frame[dy1:dy2, dx1:dx2] = tile
                                if options.get('optical_markers'):
                                    new_frame, _ = stamp_optical_markers(new_frame, px1, py1, px2, py2, placement=placement)
                            write_pipe_frame(proc, new_frame.tobytes())
                        else:
                            write_pipe_frame(proc, frame.tobytes())
                    elif reverse and segment_lookup:
                        matched_seg = None
                        for s_info in segment_lookup:
                            if s_info["start"] <= current_sec <= s_info["end"]:
                                matched_seg = s_info
                                break
                        if matched_seg and matched_seg["blocks"]:
                            s_blocks = matched_seg["blocks"]
                            s_mapping = matched_seg["mapping"]
                            n_s_blocks = len(s_blocks)
                            new_frame = frame.copy()
                            for i in range(n_s_blocks):
                                t_idx = s_mapping[i]
                                sx1, sy1, sx2, sy2 = s_blocks[t_idx]
                                dx1, dy1, dx2, dy2 = s_blocks[i]
                                tile = frame[sy1:sy2, sx1:sx2]
                                dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                    tile = cv2.resize(tile, (dw_blk, dh_blk))
                                new_frame[dy1:dy2, dx1:dx2] = tile
                            write_pipe_frame(proc, new_frame.tobytes())
                        else:
                            write_pipe_frame(proc, frame.tobytes())
                    elif matched_seg and matched_seg["blocks"]:
                        s_blocks = matched_seg["blocks"]
                        s_mapping = matched_seg["mapping"]
                        n_s_blocks = len(s_blocks)
                        new_frame = frame.copy()
                        for i in range(n_s_blocks):
                            t_idx = s_mapping[i]
                            sx1, sy1, sx2, sy2 = s_blocks[t_idx]
                            dx1, dy1, dx2, dy2 = s_blocks[i]
                            tile = frame[sy1:sy2, sx1:sx2]
                            dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                            if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                tile = cv2.resize(tile, (dw_blk, dh_blk))
                            new_frame[dy1:dy2, dx1:dx2] = tile
                        if not reverse and options.get('optical_markers'):
                            s_roi = matched_seg["roi"]
                            rx1, ry1, rx2, ry2 = s_roi
                            if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
                                rx1, ry1, rx2, ry2 = int(rx1 * out_w), int(ry1 * out_h), int(rx2 * out_w), int(ry2 * out_h)
                            placement = options.get('marker_placement', 'outside')
                            new_frame, opt_payload = stamp_optical_markers(new_frame, rx1, ry1, rx2, ry2, placement=placement)
                            if 'optical_payload' not in options:
                                options['optical_payload'] = opt_payload
                        elif reverse and options.get('optical_markers'):
                            if options.get('optical_payload'):
                                new_frame = restore_optical_markers(new_frame, options['optical_payload'])
                            else:
                                s_roi = matched_seg.get("roi") or global_roi
                                if s_roi:
                                    rx1, ry1, rx2, ry2 = s_roi
                                    if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
                                        rx1, ry1, rx2, ry2 = int(rx1 * out_w), int(ry1 * out_h), int(rx2 * out_w), int(ry2 * out_h)
                                    placement = options.get('marker_placement', 'outside')
                                    new_frame = inpaint_optical_markers(new_frame, rx1, ry1, rx2, ry2, placement=placement)
                        write_pipe_frame(proc, new_frame.tobytes())
                    else:
                        new_frame = frame.copy()
                        for i in range(n_blocks):
                            t_idx = dest_to_src[i]
                            sx1, sy1, sx2, sy2 = all_blocks[t_idx]
                            dx1, dy1, dx2, dy2 = all_blocks[i]
                            tile = frame[sy1:sy2, sx1:sx2]
                            dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                            if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                tile = cv2.resize(tile, (dw_blk, dh_blk))
                            new_frame[dy1:dy2, dx1:dx2] = tile
                        write_pipe_frame(proc, new_frame.tobytes())
            else:
                write_pipe_frame(proc, frame.tobytes())
                if reverse and proc_center:
                    center_blank = np.zeros((center_h, center_w, 3), dtype=np.uint8)
                    write_pipe_frame(proc_center, center_blank.tobytes())
            frame_count += 1
            if frame_count % 3 == 0:
                is_cancelled_cb = options.get('is_cancelled')
                if is_cancelled_cb and is_cancelled_cb():
                    LiveDebugger.log("CANCEL", f"Video processing cancelled by user at frame {frame_count}/{max(output_total_frames, 1)}", level="WARNING", module="VIDEO")
                    raise RuntimeError("Processing cancelled by user")
            if total_frames > 0 and frame_count % 5 == 0:
                progress_dict[task_id] = int((frame_count / max(output_total_frames, 1)) * 100)
    finally:
        _close_ffmpeg_proc(proc, name="FFmpeg Main")
        if proc_center:
            _close_ffmpeg_proc(proc_center, name="FFmpeg Center")
        cap.release()
        if cap_center:
            cap_center.release()
        if os.path.exists(temp_aud):
            try:
                os.remove(temp_aud)
            except Exception:
                pass
        if os.path.exists(temp_center_aud_out):
            try:
                os.remove(temp_center_aud_out)
            except Exception:
                pass
        is_cancelled_cb = options.get('is_cancelled')
        if is_cancelled_cb and is_cancelled_cb():
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception:
                    pass
            if proc_center and 'output_path_center' in locals() and os.path.exists(output_path_center):
                try:
                    os.remove(output_path_center)
                except Exception:
                    pass
    progress_dict[task_id] = 100
