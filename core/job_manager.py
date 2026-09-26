import os
import time
import secrets
import threading
import traceback
from core.crypto import clean_key, hash_str, compress_key, decompress_key, generate_qr_code
from core.grid_utils import format_center_key
from core.pipeline import process_media
from core.metadata_prober import probe_media_file, is_image_filename, IMAGE_EXTENSIONS, writable_image_ext
from core.logger import LiveDebugger
def parse_wave_envelope(raw_env):
    if not raw_env:
        return None
    try:
        import json as _json
        _env = _json.loads(raw_env) if isinstance(raw_env, str) else raw_env
        _env = _env or {}
        def _clean_pts(v):
            pts = [int(round(float(x))) for x in (v or [])]
            pts = [max(100, min(25000, x)) for x in pts]
            return pts if 2 <= len(pts) <= 100 else None
        _pts = _clean_pts(_env.get('points'))
        if _pts is None:
            return None
        _parsed = {
            'points': _pts,
            'avg': max(100, int(round(sum(_pts) / len(_pts)))),
            'max': max(_pts),
        }
        _zp = _clean_pts(_env.get('zone_points'))
        if _zp is not None:
            if len(_zp) != len(_pts):
                _rs = []
                for _i in range(len(_pts)):
                    _t = _i * (len(_zp) - 1) / max(1, len(_pts) - 1)
                    _i0 = int(_t)
                    _i1 = min(len(_zp) - 1, _i0 + 1)
                    _f = _t - _i0
                    _rs.append(max(100, min(25000, int(round(_zp[_i0] * (1 - _f) + _zp[_i1] * _f)))))
                _zp = _rs
            _parsed['zone_points'] = _zp
            _parsed['zone_avg'] = max(100, int(round(sum(_zp) / len(_zp))))
        try:
            _dur = float(_env.get('duration')) if _env.get('duration') is not None else None
        except Exception:
            _dur = None
        if _dur and 0 < _dur < 86400:
            _parsed['duration'] = _dur
        for _k in ('zone_target', 'bg_target'):
            try:
                _v = int(round(float(_env.get(_k)))) if _env.get(_k) is not None else None
            except Exception:
                _v = None
            if _v:
                _parsed[_k] = max(100, min(25000, _v))
        return _parsed
    except Exception:
        return None
class JobManager:
    def __init__(self, input_folder, encrypted_folder, decrypted_folder, save_key_fn, resolve_quality_fn, sanitize_sr_fn):
        self.input_folder = input_folder
        self.encrypted_folder = encrypted_folder
        self.decrypted_folder = decrypted_folder
        self.save_key_fn = save_key_fn
        self.resolve_quality_fn = resolve_quality_fn
        self.sanitize_sr_fn = sanitize_sr_fn
        self.lock = threading.Lock()
        self.job_id = None
        self.status = "idle"                                                        
        self.action = None
        self.total_files = 0
        self.current_index = 0
        self.current_file = ""
        self.progress = 0
        self.start_time = None
        self.end_time = None
        self.keys = []
        self.errors = []
        self.cancel_event = threading.Event()
        self.worker_thread = None
        self.task_progress = {}
    def start_job(self, action, files_info, form_data):
        with self.lock:
            if self.status == "running" and self.worker_thread and self.worker_thread.is_alive():
                return False, "A processing job is already in progress.", self.job_id
            self.cancel_event.clear()
            self.job_id = f"job_{int(time.time() * 1000)}"
            self.status = "running"
            self.action = action
            self.total_files = len(files_info)
            self.current_index = 0
            self.current_file = ""
            self.progress = 0
            self.start_time = time.time()
            self.end_time = None
            self.keys = []
            self.errors = []
            self.task_progress = {}
            self.worker_thread = threading.Thread(
                target=self._run_job,
                args=(self.job_id, action, files_info, dict(form_data)),
                daemon=True
            )
            self.worker_thread.start()
            return True, "Job started", self.job_id
    def cancel_job(self):
        with self.lock:
            if self.status == "running":
                self.cancel_event.set()
                self.status = "cancelled"
                self.end_time = time.time()
                LiveDebugger.log("Job Manager", f"Job '{self.job_id}' cancellation requested by user", level="WARNING", module="JOB")
                return True, "Job cancelled"
            return False, f"Cannot cancel job in state: {self.status}"
    def get_status(self):
        with self.lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "action": self.action,
                "total_files": self.total_files,
                "current_index": self.current_index,
                "current_file": self.current_file,
                "progress": self.progress,
                "keys": list(self.keys),
                "errors": list(self.errors),
                "start_time": self.start_time,
                "end_time": self.end_time
            }
    def _run_job(self, job_id, action, files_info, form_data):
        LiveDebugger.log("Job Manager", f"Starting batch job '{job_id}' ({action}) with {len(files_info)} file(s)", level="INFO", module="JOB")
        for idx, file_item in enumerate(files_info):
            if self.cancel_event.is_set():
                LiveDebugger.log("Job Manager", f"Job '{job_id}' stopped due to cancellation before file #{idx+1}", level="WARNING", module="JOB")
                with self.lock:
                    self.status = "cancelled"
                    self.end_time = time.time()
                return
            filename = file_item['filename']
            file_path = file_item['path']
            display_name = file_item.get('display_name', filename)
            base_name, _ = os.path.splitext(filename)
            task_id = f"task_{job_id}_{idx}"
            with self.lock:
                self.current_index = idx + 1
                self.current_file = display_name
                self.progress = 0
                self.task_progress[task_id] = 0
            def make_progress_dict():
                class ProgressDict(dict):
                    def __init__(outer_self, job_mgr, tid):
                        super().__init__()
                        outer_self.job_mgr = job_mgr
                        outer_self.tid = tid
                    def __setitem__(outer_self, k, v):
                        super().__setitem__(k, v)
                        with outer_self.job_mgr.lock:
                            outer_self.job_mgr.progress = int(v)
                            outer_self.job_mgr.task_progress[outer_self.tid] = int(v)
                return ProgressDict(self, task_id)
            p_dict = make_progress_dict()
            try:
                info = probe_media_file(file_path)
                meta_str = f"Format: {info.get('format', 'unknown')} | Size: {info.get('file_size_mb', 'unknown')} MB"
                if info.get('resolution'): meta_str += f" | Res: {info.get('resolution')}"
                if info.get('duration'): meta_str += f" | Dur: {info.get('duration')}"
                if info.get('video_codec'): meta_str += f" | Video Codec: {info.get('video_codec')}"
                if info.get('audio_codec'): meta_str += f" | Audio Codec: {info.get('audio_codec')} ({info.get('audio_sr', 'unknown')} Hz)"
                LiveDebugger.log("Load File", f"Loaded user file '{display_name}' for action '{action}' | Location: {file_path} | Metadata: {meta_str}", level="INFO", module="HTTP")
                raw_aud_sr = form_data.get('aud_sr', '48000')
                raw_aud_codec = form_data.get('aud_codec', 'aac')
                options = {
                    'vid_format': form_data.get('vid_format', '.mp4'),
                    'vid_codec': form_data.get('vid_codec', 'libx264'),
                    'vid_bitrate': form_data.get('vid_bitrate', '3000k'),
                    'vid_preset': form_data.get('vid_preset', 'medium'),
                    'aud_sr': self.sanitize_sr_fn(raw_aud_sr, raw_aud_codec),
                    'aud_codec': raw_aud_codec,
                    'aud_bitrate': form_data.get('aud_bitrate', '192k'),
                    'carrier_freq': int(form_data.get('carrier_freq', 8000)) if form_data.get('carrier_freq') and str(form_data.get('carrier_freq')).isdigit() else 8000,
                    'no_scale': form_data.get('no_scale') in [True, 'true', 'True', '1'],
                    'aud_method': form_data.get('aud_method', 'inversion'),
                    'aud_splits': int(form_data.get('aud_splits', 10)) if form_data.get('aud_splits') and str(form_data.get('aud_splits')).isdigit() else 10,
                    'vol_factor': float(form_data.get('vol_factor_bg', form_data.get('vol_factor', 1.0))),
                    'vol_factor_bg': float(form_data.get('vol_factor_bg', form_data.get('vol_factor', 1.0))),
                    'vol_factor_center': float(form_data.get('vol_factor_center', 1.0)),
                    'dual_track': form_data.get('dual_track') in [True, 'true', 'True', '1'],
                    'center': False,
                    'center_size': form_data.get('center_size', '1/4'),
                    'video_encrypt_mode': form_data.get('video_encrypt_mode', 'external'),
                    'aud_track': form_data.get('aud_track', 'both'),
                    'center_end_action': form_data.get('center_end_action', 'loop'),
                    'center_aud_action': form_data.get('center_aud_action', 'silence'),
                    'outer_end_action': form_data.get('outer_end_action', 'stop'),
                    'use_gpu': form_data.get('use_gpu') in [True, 'true', 'True', '1'],
                    'is_cancelled': lambda: self.cancel_event.is_set()
                }
                _sm = str(form_data.get('spatial_compression_mode', 'off') or 'off').lower()
                if _sm == 'zone':
                    _sm = 'priority'
                elif _sm != 'priority':
                    _sm = 'off'
                options['spatial_compression_mode'] = _sm
                try:
                    options['zone_priority_strength'] = max(
                        0, min(100, int(form_data.get('zone_priority_strength', 40))))
                except Exception:
                    options['zone_priority_strength'] = 40
                _center_pre = file_item.get('center_path') or form_data.get('center_path')
                if form_data.get('center_mode') in [True, 'true', 'True', '1'] and _center_pre and os.path.exists(_center_pre):
                    options['center'] = True
                    options['center_path'] = _center_pre
                _parsed_env = parse_wave_envelope(form_data.get('vid_bitrate_envelope'))
                if _parsed_env:
                    options['vid_bitrate_envelope'] = _parsed_env
                options = self.resolve_quality_fn(file_path, options)
                fn_lower = filename.lower()
                is_image = is_image_filename(fn_lower) or (info.get('format') == 'image') or (file_item.get('type') == 'image')
                if is_image:
                    out_ext = form_data.get('img_format', '.png')
                    if out_ext == 'auto' or not out_ext or out_ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
                        _, f_ext = os.path.splitext(filename)
                        out_ext = f_ext.lower() if f_ext.lower() in IMAGE_EXTENSIONS else '.png'
                        out_ext = writable_image_ext(out_ext)
                elif fn_lower.endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')) or (info.get('format') == 'audio'):
                    out_ext = form_data.get('aud_format', '.wav')
                    if out_ext == 'auto' or not out_ext:
                        out_ext = os.path.splitext(filename)[1].lower()
                else:
                    out_ext = options['vid_format']
                req_w, req_h = form_data.get('resize_w'), form_data.get('resize_h')
                if req_w and str(req_w).isdigit(): options['target_w'] = int(req_w)
                if req_h and str(req_h).isdigit(): options['target_h'] = int(req_h)
                if action == "scramble":
                    options.update({
                        'process_video': form_data.get('enc_video') in [True, 'true', 'True', '1'],
                        'process_audio': form_data.get('enc_audio') in [True, 'true', 'True', '1'],
                        'reverse': False,
                        'cols': int(form_data.get('cols', 10)) if form_data.get('cols') and str(form_data.get('cols')).isdigit() else 10,
                        'rows': int(form_data.get('rows', 10)) if form_data.get('rows') and str(form_data.get('rows')).isdigit() else 10,
                        'export_svg': form_data.get('export_svg') in [True, 'true', 'True', '1', None],
                        'export_timeline': form_data.get('export_timeline') in [True, 'true', 'True', '1', None]
                    })
                    raw_patch = form_data.get('patch_intervals')
                    parsed_patch = []
                    if raw_patch:
                        if isinstance(raw_patch, str):
                            try:
                                import json
                                parsed_patch = json.loads(raw_patch)
                            except Exception:
                                for seg in raw_patch.split(','):
                                    seg = seg.strip()
                                    if '-' in seg:
                                        p_s, p_e = seg.split('-', 1)
                                        try:
                                            parsed_patch.append([float(p_s.strip()), float(p_e.strip())])
                                        except ValueError:
                                            pass
                        elif isinstance(raw_patch, (list, tuple)):
                            parsed_patch = list(raw_patch)
                    if parsed_patch:
                        valid_intervals = []
                        for item in parsed_patch:
                            try:
                                s_val, e_val = float(item[0]), float(item[1])
                                if e_val > s_val:
                                    valid_intervals.append((s_val, e_val))
                            except Exception:
                                pass
                        if valid_intervals:
                            options['patch_intervals'] = valid_intervals
                    raw_roi = form_data.get('patch_roi')
                    if raw_roi:
                        if isinstance(raw_roi, str):
                            try:
                                import json
                                options['patch_roi'] = json.loads(raw_roi)
                            except Exception:
                                parts = [float(p.strip()) for p in raw_roi.split(',') if p.strip()]
                                if len(parts) >= 4:
                                    options['patch_roi'] = parts[:4]
                        elif isinstance(raw_roi, (list, tuple)) and len(raw_roi) >= 4:
                            options['patch_roi'] = list(raw_roi)[:4]
                    options['roi_invert'] = form_data.get('roi_invert') in [True, 'true', 'True', '1']
                    options['optical_markers'] = (form_data.get('optical_markers') in [True, 'true', 'True', '1'] or
                                                  form_data.get('patch_optical_markers') in [True, 'true', 'True', '1'])
                    options['marker_placement'] = form_data.get('marker_placement') or form_data.get('patch_marker_placement') or 'outside'
                    raw_segments = form_data.get('patch_segments')
                    if raw_segments:
                        if isinstance(raw_segments, str):
                            try:
                                import json
                                options['patch_segments'] = json.loads(raw_segments)
                            except Exception:
                                pass
                        elif isinstance(raw_segments, list):
                            options['patch_segments'] = raw_segments
                    if form_data.get('custom_audio_l'):
                        options['custom_audio_l'] = form_data.get('custom_audio_l')
                    if form_data.get('custom_audio_r'):
                        options['custom_audio_r'] = form_data.get('custom_audio_r')
                    for _ch in ('l', 'r'):
                        _enc_val = form_data.get(f'track_{_ch}_enc',
                                     form_data.get(f'custom_audio_{_ch}_enc',
                                     form_data.get(f'enc_custom_{_ch}', True)))
                        options[f'track_{_ch}_enc'] = _enc_val not in [False, 'false', 'False', '0', 'off', 'no']
                        options[f'custom_audio_{_ch}_enc'] = options[f'track_{_ch}_enc']
                        _src_val = form_data.get(f'track_{_ch}_source')
                        if _src_val in ('background', 'center', 'custom'):
                            options[f'track_{_ch}_source'] = _src_val
                    sid = str(form_data.get('sid', '')).strip() or secrets.token_hex(4)
                    options['seed'] = hash_str(sid)
                    options['aud_key'] = hash_str(sid)
                    center_path = file_item.get('center_path') or form_data.get('center_path')
                    if form_data.get('center_mode') in [True, 'true', 'True', '1'] and center_path and os.path.exists(center_path):
                        options['center'] = True
                        options['center_path'] = center_path
                    method_tag = 'ainv'
                    if options['aud_method'] == 'band_scramble':
                        method_tag = 'abs'
                    elif options['aud_method'] == 'combined':
                        method_tag = 'acb'
                    patch_tag = ""
                    if options.get('patch_intervals') and not options.get('patch_segments'):
                        if not options.get('optical_markers') or options.get('process_audio'):
                            patch_str = ",".join(f"{s:.3f}-{e:.3f}" for s, e in options['patch_intervals'])
                            patch_tag = f"|patch:{patch_str}"
                    spatial_tag = ""
                    if (options.get('optical_markers')
                            and options.get('marker_placement') == 'inside'
                            and (options.get('patch_segments') or options.get('patch_roi'))):
                        options['marker_inside_full'] = True
                    if options.get('patch_segments'):
                        if not options.get('optical_markers'):
                            psegs_encoded = []
                            for s in options['patch_segments']:
                                s_start = float(s.get('start', 0.0))
                                s_end = float(s.get('end', 0.0))
                                s_roi = s.get('roi')
                                s_inv = 1 if s.get('invert') else 0
                                if s_roi and len(s_roi) >= 4:
                                    psegs_encoded.append(f"{s_start:.2f}-{s_end:.2f}:{s_roi[0]:.3f}_{s_roi[1]:.3f}_{s_roi[2]:.3f}_{s_roi[3]:.3f}_{s_inv}")
                                else:
                                    psegs_encoded.append(f"{s_start:.2f}-{s_end:.2f}")
                            spatial_tag += f"|psegs:{','.join(psegs_encoded)}"
                    elif options.get('patch_roi'):
                        rx1, ry1, rx2, ry2 = options['patch_roi']
                        inv_bit = 1 if options.get('roi_invert') else 0
                        if not options.get('optical_markers'):
                            spatial_tag += f"|roi:{rx1:.3f}_{ry1:.3f}_{rx2:.3f}_{ry2:.3f}_{inv_bit}"
                    if options.get('optical_markers'):
                        plc = options.get('marker_placement', 'outside')[:3]
                        inv_sfx = "_inv" if options.get('roi_invert') else ""
                        spatial_tag += f"|opt_{plc}{inv_sfx}"
                        if options.get('marker_inside_full'):
                            spatial_tag += "|mif"
                    if options.get('custom_audio_l') or options.get('custom_audio_r'):
                        spatial_tag += "|ca"
                        if not options.get('track_l_enc', True):
                            spatial_tag += "|cal0"
                        if not options.get('track_r_enc', True):
                            spatial_tag += "|car0"
                    elif (options.get('track_l_source') in ('background', 'center', 'custom')
                            or options.get('track_r_source') in ('background', 'center', 'custom')):
                        _eff_l = options.get('track_l_source', 'background')
                        _eff_r = options.get('track_r_source', 'background')
                        if _eff_l != 'background' or _eff_r != 'center':
                            spatial_tag += "|ca"
                            if not options.get('track_l_enc', True):
                                spatial_tag += "|cal0"
                            if not options.get('track_r_enc', True):
                                spatial_tag += "|car0"
                    if options['process_video'] and options['process_audio']:
                        key = f"{options['cols']}x{options['rows']}|{sid}{patch_tag}{spatial_tag}"
                        if options.get('center'):
                            key += format_center_key(options.get('center_size', '1/4'))
                        if options['video_encrypt_mode'] == 'center':
                            key += "|em_cnt"
                        elif options['video_encrypt_mode'] == 'both':
                            key += "|em_both"
                        key += "|a"
                        key += f"|{method_tag}"
                        key += f"|as_{options['aud_splits']}"
                        key += f"|cf_{options['carrier_freq']}"
                        if options.get('dual_track'):
                            key += "|dm"
                        if options.get('vol_factor', 1.0) != 1.0:
                            key += f"|v_{options['vol_factor']}"
                        if options['aud_track'] == 'left':
                            key += "|at_l"
                        elif options['aud_track'] == 'right':
                            key += "|at_r"
                    elif options['process_audio']:
                        key = f"|a|{sid}{patch_tag}{spatial_tag}"
                        key += f"|{method_tag}"
                        key += f"|as_{options['aud_splits']}"
                        key += f"|cf_{options['carrier_freq']}"
                        if options.get('vol_factor', 1.0) != 1.0:
                            key += f"|v_{options['vol_factor']}"
                        if options['aud_track'] == 'left':
                            key += "|at_l"
                        elif options['aud_track'] == 'right':
                            key += "|at_r"
                    else:
                        key = f"{options['cols']}x{options['rows']}|{sid}{patch_tag}{spatial_tag}"
                        if options.get('center'):
                            key += format_center_key(options.get('center_size', '1/4'))
                        if options['video_encrypt_mode'] == 'center':
                            key += "|em_cnt"
                        elif options['video_encrypt_mode'] == 'both':
                            key += "|em_both"
                    out_path = os.path.join(self.encrypted_folder, f"locked_{base_name}{out_ext}")
                    LiveDebugger.log("Start Process", f"Encrypting '{display_name}' -> '{out_path}' | Key: '{key}'", level="INFO", module="JOB")
                    process_media(file_path, out_path, options, p_dict, task_id)
                    if self.cancel_event.is_set():
                        if os.path.exists(out_path):
                            try: os.remove(out_path)
                            except Exception: pass
                        with self.lock:
                            self.status = "cancelled"
                            self.end_time = time.time()
                        return
                    active_key = key
                    generate_qr_enabled = form_data.get('generate_qr') in [True, 'true', 'True', '1']
                    qr_filename = None
                    qr_path = None
                    if generate_qr_enabled:
                        qr_filename = f"{os.path.splitext(os.path.basename(out_path))[0]}_qr.png"
                        qr_path = os.path.join(self.encrypted_folder, qr_filename)
                        try:
                            generate_qr_code(active_key, qr_path)
                        except Exception as e:
                            print(f"Warning: QR generation skipped or failed: {e}")
                    save_key_enabled = form_data.get('save_key_file') in [True, 'true', 'True', '1', None]
                    key_path = None
                    if save_key_enabled:
                        key_path = self.save_key_fn(os.path.basename(out_path), active_key)
                    with self.lock:
                        self.keys.append({
                            "name": display_name,
                            "file": display_name,
                            "out_file": os.path.basename(out_path),
                            "key": active_key,
                            "canonical_key": key,
                            "qr_file": qr_filename if (qr_path and os.path.exists(qr_path)) else None,
                            "path": out_path
                        })
                elif action == "unscramble":
                    raw_input_key = form_data.get('key', '')
                    raw_key, opt_payload = decompress_key(raw_input_key)
                    options.update({
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
                        'optical_payload': opt_payload,
                        'has_custom_audio': False,
                        'track_l_enc': True,
                        'track_r_enc': True
                    })
                    def _parse_patch_tag(part_str):
                        content = part_str.split(':', 1)[1] if ':' in part_str else ""
                        parsed = []
                        for item in content.split(','):
                            item = item.strip()
                            if '-' in item:
                                s_part, e_part = item.split('-', 1)
                                try:
                                    s_f, e_f = float(s_part.strip()), float(e_part.strip())
                                    if e_f > s_f:
                                        parsed.append((s_f, e_f))
                                except ValueError:
                                    pass
                        return parsed
                    if raw_key.startswith("|a"):
                        options['process_audio'] = True
                        parts = raw_key.split('|')
                        if len(parts) > 2:
                            p2 = parts[2]
                            if not (p2.startswith('am_') or p2.startswith('as_') or p2.startswith('cf_') or p2.startswith('v_') or p2.startswith('patch:') or p2.startswith('p:') or p2 in ['abs', 'acb', 'ainv', 'inversion', 'band_scramble', 'combined'] or p2.startswith('at_')):
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
                            elif part.startswith('patch:') or part.startswith('p:'):
                                p_intervals = _parse_patch_tag(part)
                                if p_intervals:
                                    options['patch_intervals'] = p_intervals
                    else:
                        parts = raw_key.split('|')
                        dim = parts[0]
                        seed_str = parts[1] if len(parts) > 1 else "0"
                        options['process_video'] = True
                        options['cols'], options['rows'] = map(int, dim.split('x'))
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
                            elif part.startswith('patch:') or part.startswith('p:'):
                                p_intervals = _parse_patch_tag(part)
                                if p_intervals:
                                    options['patch_intervals'] = p_intervals
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
                            elif part.startswith('as_'):
                                options['aud_splits'] = int(part[3:])
                            elif part.startswith('cf_'):
                                options['carrier_freq'] = int(part[3:])
                            elif part.startswith('v_'):
                                options['vol_factor'] = float(part[2:])
                            elif part.startswith('psegs:'):
                                p_content = part.split(':', 1)[1]
                                psegs = []
                                p_intervals = []
                                for item in p_content.split(','):
                                    item = item.strip()
                                    if ':' in item:
                                        t_part, r_part = item.split(':', 1)
                                        s_s, s_e = map(float, t_part.split('-'))
                                        r_coords = r_part.split('_')
                                        r_box = [float(r_coords[0]), float(r_coords[1]), float(r_coords[2]), float(r_coords[3])]
                                        r_inv = (r_coords[4] == '1') if len(r_coords) > 4 else False
                                        psegs.append({"start": s_s, "end": s_e, "roi": r_box, "invert": r_inv})
                                        p_intervals.append((s_s, s_e))
                                    elif '-' in item:
                                        s_s, s_e = map(float, item.split('-'))
                                        p_intervals.append((s_s, s_e))
                                        psegs.append({"start": s_s, "end": s_e})
                                if psegs:
                                    options['patch_segments'] = psegs
                                if p_intervals:
                                    options['patch_intervals'] = p_intervals
                            elif part.startswith('roi:'):
                                r_part = part.split(':', 1)[1]
                                sep = '_' if '_' in r_part else ','
                                r_coords = [c.strip() for c in r_part.split(sep) if c.strip()]
                                if len(r_coords) >= 4:
                                    options['patch_roi'] = [float(r_coords[0]), float(r_coords[1]), float(r_coords[2]), float(r_coords[3])]
                                    if len(r_coords) > 4:
                                        options['roi_invert'] = (r_coords[4] == '1')
                            elif part.startswith('opt_'):
                                options['optical_markers'] = True
                                options['marker_placement'] = 'inside' if 'ins' in part else 'outside'
                                if 'inv' in part:
                                    options['roi_invert'] = True
                            elif part == 'mif':
                                options['marker_inside_full'] = True
                            elif part == 'ca':
                                options['has_custom_audio'] = True
                                options['custom_audio_l_enc'] = True
                                options['custom_audio_r_enc'] = True
                                options['track_l_enc'] = True
                                options['track_r_enc'] = True
                            elif part == 'cal0':
                                options['has_custom_audio'] = True
                                options['custom_audio_l_enc'] = False
                                options['track_l_enc'] = False
                            elif part == 'car0':
                                options['has_custom_audio'] = True
                                options['custom_audio_r_enc'] = False
                                options['track_r_enc'] = False
                    out_path = os.path.join(self.decrypted_folder, f"restored_{base_name}{out_ext}")
                    LiveDebugger.log("Start Process", f"Decrypting '{display_name}' -> '{out_path}' | Key: '{raw_key}'", level="INFO", module="JOB")
                    process_media(file_path, out_path, options, p_dict, task_id)
                    if self.cancel_event.is_set():
                        if os.path.exists(out_path):
                            try: os.remove(out_path)
                            except Exception: pass
                        with self.lock:
                            self.status = "cancelled"
                            self.end_time = time.time()
                        return
                    with self.lock:
                        self.keys.append({
                            "name": display_name,
                            "file": display_name,
                            "out_file": os.path.basename(out_path),
                            "key": raw_key,
                            "path": out_path
                        })
                        base_d, ext_d = os.path.splitext(out_path)
                        c_path = f"{base_d}_center{ext_d}"
                        if os.path.exists(c_path):
                            c_out_file = os.path.basename(c_path)
                            self.keys.append({
                                "name": f"{display_name} (Center)",
                                "file": f"{display_name} (Center)",
                                "out_file": c_out_file,
                                "key": raw_key,
                                "path": c_path
                            })
                with self.lock:
                    self.progress = 100
            except Exception as e:
                if self.cancel_event.is_set():
                    LiveDebugger.log("Job Manager", f"Task #{idx+1} '{display_name}' cancelled by user", level="WARNING", module="JOB")
                    with self.lock:
                        self.status = "cancelled"
                        self.end_time = time.time()
                    return
                tb = traceback.format_exc()
                diag = LiveDebugger.analyze_exception(e, module_name="JOB", func_name="_run_job")
                LiveDebugger.log("Process Error", f"Error on '{display_name}': {str(e)}", level="ERROR", module="JOB")
                with self.lock:
                    self.errors.append({
                        "file": display_name,
                        "error": str(e),
                        "traceback": tb,
                        "diagnostic": diag
                    })
        with self.lock:
            if self.cancel_event.is_set():
                self.status = "cancelled"
            elif self.errors and len(self.errors) == self.total_files:
                self.status = "error"
            else:
                self.status = "completed"
            self.end_time = time.time()
            self.progress = 100
        LiveDebugger.log("Job Manager", f"Job '{job_id}' finished with status '{self.status}'", level="INFO", module="JOB")
