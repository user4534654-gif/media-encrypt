import cv2
import numpy as np
import os
import sys
import subprocess
import imageio_ffmpeg
creation_flags = 0
if sys.platform == "win32":
    creation_flags = subprocess.CREATE_NO_WINDOW
from core.crypto import seeded_shuffle
from core.audio import process_audio_file
from core.grid_utils import find_best_grid, get_outer_blocks, get_blocks
from core.svg_generator import export_grid_to_svg, export_scrambled_grid_to_svg
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
def process_video_file(input_path, output_path, options, progress_dict, task_id):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    proc_vid, proc_aud, reverse = options.get('process_video'), options.get('process_audio'), options.get('reverse')
    cols, rows, seed = options.get('cols', 1), options.get('rows', 1), options.get('seed', 0)
    target_w, target_h = options.get('target_w'), options.get('target_h')
    no_scale = options.get('no_scale', False)
    carrier_freq = options.get('carrier_freq', 8000)
    video_encrypt_mode = options.get('video_encrypt_mode', 'external')                               
    center_end_action = options.get('center_end_action', 'loop')                              
    center_aud_action = options.get('center_aud_action', 'silence')                    
    outer_end_action  = options.get('outer_end_action',  'stop')                                      
    temp_aud = input_path + "_aud.wav"
    temp_center_aud_out = input_path + "_center_aud_out.wav"
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
            print("Failed to read main audio sample rate:", e)
        if not reverse and options.get('center') and options.get('dual_track'):
            process_audio_file(
                temp_aud, temp_aud, is_decrypt=False,
                method=options.get('aud_method', 'inversion'),
                key=options.get('aud_key', 42),
                num_splits=options.get('aud_splits', 10),
                carrier_freq=carrier_freq,
                vol_factor=options.get('vol_factor', 1.0),
                aud_track=options.get('aud_track', 'both')
            )
            temp_center_aud = options['center_path'] + "_center_aud.wav"
            has_center_audio = subprocess.run([ffmpeg_exe, '-y', '-i', options['center_path'], '-vn', '-ar', str(main_sr), temp_center_aud], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags).returncode == 0
            main_data, main_sr = sf.read(temp_aud)
            if len(main_data.shape) > 1:
                main_data = main_data[:, 0]
            center_data = None
            if has_center_audio and os.path.exists(temp_center_aud):
                center_data, center_sr = sf.read(temp_center_aud)
                if len(center_data.shape) > 1:
                    center_data = center_data[:, 0]
                center_data = _adjust_audio_length(center_data, len(main_data), center_aud_action)
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
                aud_track='both'                                         
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
                aud_track=options.get('aud_track', 'both')
            )
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
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
    if not reverse and options.get('export_svg', True):
        try:
            base, _ = os.path.splitext(output_path)
            export_grid_to_svg(f"{base}_grid.svg", out_w, out_h, cols, rows, has_center=options.get('center', False), center_size=center_size)
            export_scrambled_grid_to_svg(f"{base}_grid_original.svg", out_w, out_h, cols, rows, seed, has_center=options.get('center', False), center_size=center_size, prefix_original=True)
            export_scrambled_grid_to_svg(f"{base}_grid_scrambled.svg", out_w, out_h, cols, rows, seed, has_center=options.get('center', False), center_size=center_size, prefix_original=False)
        except Exception as e:
            print("Failed to export SVG grids:", e)
    cap_center = None
    fps_c = 30.0
    total_frames_c = 0
    frame_step_c = 1.0
    if options.get('center') and not reverse and options.get('center_path'):
        cap_center = cv2.VideoCapture(options['center_path'])
        fps_c = cap_center.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames_c = int(cap_center.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_step_c = fps_c / fps
    if cap_center and total_frames_c > 0 and outer_end_action != 'stop':
        center_frames_adapted = int(total_frames_c / frame_step_c)
        output_total_frames = max(total_frames, center_frames_adapted)
    else:
        output_total_frames = total_frames                                
    cmd = [ffmpeg_exe, '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
           '-s', f'{out_w}x{out_h}', '-pix_fmt', 'bgr24', '-r', str(fps), '-i', '-']
    if has_audio:
        cmd.extend(['-i', temp_aud])
    cmd.extend(['-c:v', options.get('vid_codec'), '-b:v', options.get('vid_bitrate'), '-preset', options.get('vid_preset')])
    if options.get('vid_codec') != 'prores':
        cmd.extend(['-pix_fmt', 'yuv420p'])
    if has_audio:
        cmd.extend(['-c:a', options.get('aud_codec'), '-b:a', options.get('aud_bitrate'), '-ar', options.get('aud_sr')])
    else:
        cmd.extend(['-an'])
    cmd.append(output_path)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=creation_flags)
    proc_center = None
    if reverse and options.get('center'):
        base, ext = os.path.splitext(output_path)
        output_path_center = f"{base}_center{ext}"
        has_center_aud_out = os.path.exists(temp_center_aud_out)
        cmd_center = [ffmpeg_exe, '-y', '-f', 'rawvideo', '-vcodec', 'rawvideo',
                      '-s', f'{cw}x{ch}', '-pix_fmt', 'bgr24', '-r', str(fps), '-i', '-']
        if has_center_aud_out:
            cmd_center.extend(['-i', temp_center_aud_out])
        cmd_center.extend(['-c:v', options.get('vid_codec'), '-b:v', options.get('vid_bitrate'), '-preset', options.get('vid_preset')])
        if options.get('vid_codec') != 'prores':
            cmd_center.extend(['-pix_fmt', 'yuv420p'])
        if has_center_aud_out:
            cmd_center.extend(['-c:a', options.get('aud_codec'), '-b:a', options.get('aud_bitrate'), '-ar', options.get('aud_sr')])
        else:
            cmd_center.extend(['-an'])
        cmd_center.append(output_path_center)
        proc_center = subprocess.Popen(cmd_center, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=creation_flags)
    frame_count = 0
    last_outer_frame = None                                       
    last_center_frame = None                                       
    outer_exhausted = False
    center_exhausted = False
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
        if proc_vid:
            if options.get('center'):
                if reverse:
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
                    proc.stdin.write(restored_frame.tobytes())
                    if proc_center:
                        center_out = cv2.resize(center_frame_to_write, (cw, ch))
                        proc_center.stdin.write(center_out.tobytes())
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
                    proc.stdin.write(new_frame.tobytes())
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
                proc.stdin.write(new_frame.tobytes())
        else:
            proc.stdin.write(frame.tobytes())
        frame_count += 1
        if total_frames > 0 and frame_count % 5 == 0:
            progress_dict[task_id] = int((frame_count / max(output_total_frames, 1)) * 100)
    proc.stdin.close()
    proc.wait()
    if proc_center:
        proc_center.stdin.close()
        proc_center.wait()
    cap.release()
    if cap_center:
        cap_center.release()
    if has_audio and os.path.exists(temp_aud):
        os.remove(temp_aud)
    if os.path.exists(temp_center_aud_out):
        os.remove(temp_center_aud_out)
    progress_dict[task_id] = 100
