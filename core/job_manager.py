import os
import time
import secrets
import threading
import traceback
from core.crypto import clean_key, hash_str
from core.pipeline import process_media
from core.metadata_prober import probe_media_file
from core.logger import LiveDebugger
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
                    'center_size': form_data.get('center_size', '1/4'),
                    'video_encrypt_mode': form_data.get('video_encrypt_mode', 'external'),
                    'aud_track': form_data.get('aud_track', 'both'),
                    'center_end_action': form_data.get('center_end_action', 'loop'),
                    'center_aud_action': form_data.get('center_aud_action', 'silence'),
                    'outer_end_action': form_data.get('outer_end_action', 'stop'),
                    'is_cancelled': lambda: self.cancel_event.is_set()
                }
                options = self.resolve_quality_fn(file_path, options)
                fn_lower = filename.lower()
                if fn_lower.endswith(('.jpg', '.png', '.jpeg', '.bmp', '.webp', '.avif')):
                    out_ext = form_data.get('img_format', '.png')
                    if out_ext == 'auto':
                        out_ext = os.path.splitext(filename)[1].lower()
                elif fn_lower.endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')):
                    out_ext = form_data.get('aud_format', '.wav')
                    if out_ext == 'auto':
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
                        'export_svg': form_data.get('export_svg') in [True, 'true', 'True', '1', None]
                    })
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
                    if options['process_video'] and options['process_audio']:
                        key = f"{options['cols']}x{options['rows']}|{sid}"
                        if options.get('center'):
                            if options.get('center_size', '1/4') != '1/4':
                                key += f"|c_{options['center_size']}"
                            else:
                                key += "|c"
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
                        key = f"|a|{sid}"
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
                        key = f"{options['cols']}x{options['rows']}|{sid}"
                        if options.get('center'):
                            if options.get('center_size', '1/4') != '1/4':
                                key += f"|c_{options['center_size']}"
                            else:
                                key += "|c"
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
                    key_path = self.save_key_fn(os.path.basename(out_path), key)
                    with self.lock:
                        self.keys.append({
                            "name": display_name,
                            "file": display_name,
                            "out_file": os.path.basename(out_path),
                            "key": key,
                            "path": out_path
                        })
                elif action == "unscramble":
                    raw_key = clean_key(form_data.get('key', ''))
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
                        'aud_track': 'both'
                    })
                    if raw_key.startswith("|a"):
                        options['process_audio'] = True
                        parts = raw_key.split('|')
                        if len(parts) > 2:
                            p2 = parts[2]
                            if not (p2.startswith('am_') or p2.startswith('as_') or p2.startswith('cf_') or p2.startswith('v_') or p2 in ['abs', 'acb', 'ainv', 'inversion', 'band_scramble', 'combined'] or p2.startswith('at_')):
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
