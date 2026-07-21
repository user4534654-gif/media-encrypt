import os
import sys
import secrets
import time
import webbrowser
import mimetypes
import re
import platform
import traceback
import argparse
import logging
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, send_file
from core.crypto import clean_key, hash_str
from core.pipeline import process_media
from core.metadata_prober import probe_media_file
from core.logger import LiveDebugger
from static.icons.icons import ICON_MAPPINGS

# Silence Werkzeug/Flask default GET/POST polling logs
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)

if getattr(sys, 'frozen', False):
    # Running inside PyInstaller EXE bundle
    base_dir = sys._MEIPASS
    vault_base_dir = os.path.dirname(sys.executable)
else:
    # Running from raw Python source
    base_dir = os.path.abspath(os.path.dirname(__file__))
    vault_base_dir = base_dir

app = Flask(__name__, template_folder=os.path.join(base_dir, 'templates'), static_folder=os.path.join(base_dir, 'static'))
PORT = 5050

VAULT_FOLDER = os.path.join(vault_base_dir, 'media_encrypt_vault')
INPUT_FOLDER = os.path.join(VAULT_FOLDER, 'input')
ENCRYPTED_FOLDER = os.path.join(VAULT_FOLDER, 'encrypted')
DECRYPTED_FOLDER = os.path.join(VAULT_FOLDER, 'decrypted')

for folder in [INPUT_FOLDER, ENCRYPTED_FOLDER, DECRYPTED_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

task_progress = {}

# ── pywebview JS-Python Fullscreen Bridge ──────────────────────────────────────
class WebviewApi:
    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def toggle_fullscreen(self):
        if self._window:
            self._window.toggle_fullscreen()
            return self._window.fullscreen
        return False

# ── Simultaneous Connection Limits (Max 2 tabs/sessions) ───────────────────────
active_sessions = {}  # session_id -> last_active_time
MAX_SESSIONS = 2      # Allows maximum of 2 concurrent client sessions/tabs
SESSION_TIMEOUT = 12  # seconds (cleanup after 2 missed pings)

@app.before_request
def limit_connections():
    # Always allow static resources to load
    if request.path.startswith('/static/'):
        return

    # Clean up expired sessions
    now = time.time()
    expired = [sid for sid, last_active in active_sessions.items() if now - last_active > SESSION_TIMEOUT]
    for sid in expired:
        active_sessions.pop(sid, None)

    # Special handling for heartbeat endpoint to avoid creating session loops
    if request.path == '/api/heartbeat':
        session_id = request.cookies.get('session_id')
        if session_id and session_id in active_sessions:
            active_sessions[session_id] = now
            return jsonify({"status": "ok"})
        return jsonify({"status": "unauthorized"}), 401

    # Retrieve session ID cookie
    session_id = request.cookies.get('session_id')

    # If it is an active valid session, update activity time and allow
    if session_id and session_id in active_sessions:
        active_sessions[session_id] = now
        return

    # For new/unregistered sessions, check if the limit is reached
    if len(active_sessions) >= MAX_SESSIONS:
        # Serve a clean 403 Page limit message
        return Response(
            "<html><head><title>403 Forbidden</title><style>body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 60px 20px; background: #f4f6f8; color: #333; } h1 { color: #ff3b30; font-size: 32px; margin-bottom: 10px; } p { font-size: 16px; color: #555; line-height: 1.5; max-width: 500px; margin: 0 auto; }</style></head><body><h1>403 Forbidden</h1><p>Connection limit reached. This application is configured to allow a maximum of 2 simultaneous browser tabs or client sessions.</p></body></html>",
            status=403
        )

    # Allocate new session (will set cookie in after_request)
    from flask import g
    g.new_session_id = secrets.token_hex(16)
    active_sessions[g.new_session_id] = now

@app.after_request
def set_session_cookie(response):
    from flask import g
    new_sid = getattr(g, 'new_session_id', None)
    if new_sid:
        response.set_cookie('session_id', new_sid, max_age=3600, httponly=True, samesite='Lax')
    return response

@app.route('/api/heartbeat')
def heartbeat_endpoint():
    return jsonify({"status": "ok"})

@app.route('/api/icons')
def get_icons():
    return jsonify(ICON_MAPPINGS)

def is_colab():
    try:
        import google.colab
        from IPython import get_ipython
        return get_ipython() is not None
    except (ImportError, NameError):
        return False

def resolve_auto_quality(file_path, options):
    is_auto = any(val == 'auto' for val in options.values())
    if not is_auto:
        return options
        
    info = probe_media_file(file_path)
    
    # 1. Video Format Auto Resolution
    if options.get('vid_format') == 'auto':
        options['vid_format'] = info.get('format', '.mp4')
        if options['vid_format'] not in ['.mp4', '.mkv', '.avi', '.webm', '.mov']:
            options['vid_format'] = '.mp4'
            
    # 2. Video Codec Auto Resolution
    if options.get('vid_codec') == 'auto':
        fmt = options.get('vid_format', '.mp4')
        if fmt == '.webm':
            options['vid_codec'] = 'libvpx-vp9'
        else:
            in_codec = info.get('video_codec')
            if in_codec == 'h264':
                options['vid_codec'] = 'libx264'
            elif in_codec in ['hevc', 'h265']:
                options['vid_codec'] = 'libx265'
            elif in_codec == 'vp9':
                options['vid_codec'] = 'libvpx-vp9'
            elif in_codec == 'av1':
                options['vid_codec'] = 'libaom-av1'
            elif in_codec == 'mpeg4':
                options['vid_codec'] = 'mpeg4'
            elif in_codec == 'prores':
                options['vid_codec'] = 'prores'
            else:
                options['vid_codec'] = 'libx264'
                
    # 3. Video Bitrate Auto Resolution
    if options.get('vid_bitrate') == 'auto':
        options['vid_bitrate'] = info.get('video_bitrate') or '3000k'
        
    # 4. Preset
    if options.get('vid_preset') == 'auto':
        options['vid_preset'] = 'medium'
        
    # 5. Audio Hz
    if options.get('aud_sr') == 'auto':
        options['aud_sr'] = info.get('audio_sr') or '48000'
        
    # 6. Audio Codec
    if options.get('aud_codec') == 'auto':
        fmt = options.get('vid_format', '.mp4')
        if fmt == '.webm':
            options['aud_codec'] = 'libopus'
        else:
            in_aud = info.get('audio_codec')
            if in_aud == 'aac':
                options['aud_codec'] = 'aac'
            elif in_aud == 'mp3':
                options['aud_codec'] = 'libmp3lame'
            elif in_aud == 'opus':
                options['aud_codec'] = 'libopus'
            elif in_aud == 'flac':
                options['aud_codec'] = 'flac'
            else:
                options['aud_codec'] = 'aac'
                
    # 7. Audio Bitrate
    if options.get('aud_bitrate') == 'auto':
        options['aud_bitrate'] = info.get('audio_bitrate') or '192k'
        
    # 8. Audio Method, Splits, and Volume Factor
    if options.get('aud_method') == 'auto':
        options['aud_method'] = 'inversion'
    if options.get('aud_splits') == 'auto':
        options['aud_splits'] = 10
    if options.get('vol_factor') == 'auto':
        options['vol_factor'] = 1.0
        
    return options

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/progress')
def get_progress():
    return jsonify({"progress": task_progress.get(request.args.get('task_id'), 0)})

@app.route('/api/process', methods=['POST'])
def process_api():
    try:
        file = request.files['file']
        action = request.form['action']
        task_id = request.form['task_id']
        task_progress[task_id] = 0
        
        filename = file.filename
        base_name, _ = os.path.splitext(filename)
        path = os.path.join(INPUT_FOLDER, filename)
        file.save(path)

        # Probe file metadata and log load event
        info = probe_media_file(path)
        meta_str = f"Format: {info.get('format', 'unknown')} | Size: {info.get('file_size_mb', 'unknown')} MB"
        if info.get('resolution'): meta_str += f" | Res: {info.get('resolution')}"
        if info.get('duration'): meta_str += f" | Dur: {info.get('duration')}"
        if info.get('video_codec'): meta_str += f" | Video Codec: {info.get('video_codec')}"
        if info.get('audio_codec'): meta_str += f" | Audio Codec: {info.get('audio_codec')} ({info.get('audio_sr', 'unknown')} Hz)"
        
        LiveDebugger.log("Load File", f"Loaded user file '{filename}' for action '{action}' | Location: {path} | Metadata: {meta_str}", ["Flask", "os", "subprocess", "imageio-ffmpeg"])

        options = {
            'vid_format': request.form.get('vid_format', '.mp4'),
            'vid_codec': request.form.get('vid_codec', 'libx264'),
            'vid_bitrate': request.form.get('vid_bitrate', '3000k'),
            'vid_preset': request.form.get('vid_preset', 'medium'),
            'aud_sr': request.form.get('aud_sr', '48000'),
            'aud_codec': request.form.get('aud_codec', 'aac'),
            'aud_bitrate': request.form.get('aud_bitrate', '192k'),
            'carrier_freq': int(request.form.get('carrier_freq', 8000)) if request.form.get('carrier_freq') and request.form.get('carrier_freq').isdigit() else 8000,
            'no_scale': request.form.get('no_scale') == 'true',
            'aud_method': request.form.get('aud_method', 'inversion'),
            'aud_splits': int(request.form.get('aud_splits', 10)) if request.form.get('aud_splits') and request.form.get('aud_splits').isdigit() else 10,
            'vol_factor': float(request.form.get('vol_factor', 1.0)) if request.form.get('vol_factor') else 1.0,
            'dual_track': request.form.get('dual_track') == 'true',
            'center_size': request.form.get('center_size', '1/4'),
            'video_encrypt_mode': request.form.get('video_encrypt_mode', 'external'),
            'aud_track': request.form.get('aud_track', 'both'),
            'center_end_action': request.form.get('center_end_action', 'loop'),
            'center_aud_action': request.form.get('center_aud_action', 'silence'),
            'outer_end_action': request.form.get('outer_end_action', 'stop'),
        }
        
        # Resolve auto quality values
        options = resolve_auto_quality(path, options)
        
        # Output extension logic based on file type
        fn_lower = filename.lower()
        if fn_lower.endswith(('.jpg', '.png', '.jpeg', '.bmp', '.webp', '.avif')):
            out_ext = request.form.get('img_format', '.png')
            if out_ext == 'auto':
                out_ext = os.path.splitext(filename)[1].lower()
        elif fn_lower.endswith(('.mp3', '.wav', '.ogg', '.flac', '.m4a')):
            out_ext = request.form.get('aud_format', '.wav')
            if out_ext == 'auto':
                out_ext = os.path.splitext(filename)[1].lower()
        else:
            out_ext = options['vid_format']
        
        # Capture Resolution Details
        req_w, req_h = request.form.get('resize_w'), request.form.get('resize_h')
        if req_w and req_w.isdigit(): options['target_w'] = int(req_w)
        if req_h and req_h.isdigit(): options['target_h'] = int(req_h)

        if action == "scramble":
            options.update({
                'process_video': request.form.get('enc_video') == 'true',
                'process_audio': request.form.get('enc_audio') == 'true',
                'reverse': False,
                'cols': int(request.form.get('cols', 10)) if request.form.get('cols') and request.form.get('cols').isdigit() else 10,
                'rows': int(request.form.get('rows', 10)) if request.form.get('rows') and request.form.get('rows').isdigit() else 10,
                'export_svg': request.form.get('export_svg', 'true') == 'true'
            })
            
            sid = request.form.get('sid', '').strip() or secrets.token_hex(4)
            options['seed'] = hash_str(sid)
            options['aud_key'] = hash_str(sid)

            # Central video/image processing
            center_path = None
            is_center = request.form.get('center_mode') == 'true'
            if is_center and 'center_file' in request.files:
                center_file = request.files['center_file']
                if center_file.filename:
                    center_path = os.path.join(INPUT_FOLDER, f"center_{center_file.filename}")
                    center_file.save(center_path)
                    options['center'] = True
                    options['center_path'] = center_path

            # Construct key string with all audio options embedded
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
                        
                # Append video encryption mode tag
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
                    
                # Append audio track selection tag
                if options['aud_track'] == 'left':
                    key += "|at_l"
                elif options['aud_track'] == 'right':
                    key += "|at_r"
            elif options['process_audio']:
                # For audio-only, encode the seed so it affects the audio permutation and is visible in the key
                key = f"|a|{sid}"
                key += f"|{method_tag}"
                key += f"|as_{options['aud_splits']}"
                key += f"|cf_{options['carrier_freq']}"
                if options.get('vol_factor', 1.0) != 1.0:
                    key += f"|v_{options['vol_factor']}"
                    
                # Append audio track selection tag
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
                        
                # Append video encryption mode tag
                if options['video_encrypt_mode'] == 'center':
                    key += "|em_cnt"
                elif options['video_encrypt_mode'] == 'both':
                    key += "|em_both"

            out_path = os.path.join(ENCRYPTED_FOLDER, f"locked_{base_name}{out_ext}")
            LiveDebugger.log("Start Process", f"Encrypting '{filename}' -> '{out_path}' | Key: '{key}'", ["Flask", "core.pipeline"])
            process_media(path, out_path, options, task_progress, task_id)
            LiveDebugger.log("Process Complete", f"Successfully encrypted and saved output file: '{out_path}'", ["Flask", "core.pipeline", "os"])
            return jsonify({"status": "ok", "key": key, "file": out_path})

        elif action == "unscramble":
            raw_key = clean_key(request.form.get('key'))
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
                # The part after |a is the seed, if it is not a tag
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
                seed_str = parts[1]
                
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

            out_path = os.path.join(DECRYPTED_FOLDER, f"restored_{base_name}{out_ext}")
            LiveDebugger.log("Start Process", f"Decrypting '{filename}' -> '{out_path}' | Key: '{raw_key}'", ["Flask", "core.pipeline"])
            process_media(path, out_path, options, task_progress, task_id)
            LiveDebugger.log("Process Complete", f"Successfully decrypted and saved output file: '{out_path}'", ["Flask", "core.pipeline", "os"])
            return jsonify({"status": "ok", "file": out_path})

    except Exception as e:
        tb = traceback.format_exc()
        LiveDebugger.log("Process Error", f"Exception during processing: {e}\n{tb}", ["Flask", "traceback"])
        return jsonify({"status": "error", "message": str(e), "traceback": tb})

@app.route('/api/save_debug_log', methods=['POST'])
def save_debug_log():
    try:
        filepath = LiveDebugger.save_to_file()
        if filepath:
            LiveDebugger.log("Save Debug Log", f"Saved debug log to: {filepath}", ["os", "datetime"])
            return jsonify({"success": True, "path": filepath})
        else:
            return jsonify({"success": False, "error": "Could not determine path"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- VAULT APIS ---
@app.route('/api/vault', methods=['GET'])
def list_vault():
    folder = request.args.get('folder', 'input')
    if folder == 'input':
        target_dir = INPUT_FOLDER
    elif folder == 'encrypted':
        target_dir = ENCRYPTED_FOLDER
    elif folder == 'decrypted':
        target_dir = DECRYPTED_FOLDER
    else:
        return jsonify({"error": "invalid folder"}), 400
        
    if not os.path.exists(target_dir):
        return jsonify({"files": []})
        
    files = [f for f in os.listdir(target_dir) if os.path.isfile(os.path.join(target_dir, f))]
    # Sort files by modification/creation time in descending order (newest first)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(target_dir, x)), reverse=True)
    return jsonify({"files": files})

@app.route('/vault/<folder>/<path:filename>')
def serve_vault_file(folder, filename):
    if folder == 'input':
        target_dir = INPUT_FOLDER
    elif folder == 'encrypted':
        target_dir = ENCRYPTED_FOLDER
    elif folder == 'decrypted':
        target_dir = DECRYPTED_FOLDER
    else:
        return "Invalid folder", 400
        
    path = os.path.join(target_dir, filename)
    if not os.path.exists(path):
        return "File not found", 404
        
    # Support range requests natively using Flask's send_file with conditional=True
    return send_file(path, conditional=True)

@app.route('/api/vault/<folder>/<path:filename>', methods=['DELETE'])
def delete_vault_file(folder, filename):
    if folder == 'input':
        target_dir = INPUT_FOLDER
    elif folder == 'encrypted':
        target_dir = ENCRYPTED_FOLDER
    elif folder == 'decrypted':
        target_dir = DECRYPTED_FOLDER
    else:
        return jsonify({"error": "invalid folder"}), 400
    path = os.path.join(target_dir, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({"status": "ok"})
    return jsonify({"status": "not_found"}), 404

@app.route('/api/open_folder', methods=['POST'])
def open_folder():
    data = request.json or {}
    folder = data.get('folder', 'input')
    if folder == 'input':
        target_dir = INPUT_FOLDER
    elif folder == 'encrypted':
        target_dir = ENCRYPTED_FOLDER
    elif folder == 'decrypted':
        target_dir = DECRYPTED_FOLDER
    else:
        target_dir = VAULT_FOLDER
    
    try:
        os.startfile(os.path.abspath(target_dir))
    except AttributeError:
        pass
    return jsonify({"status": "ok"})

@app.route('/api/open_file', methods=['POST'])
def open_file():
    data = request.json or {}
    folder = data.get('folder', 'input')
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "filename required"}), 400
        
    if folder == 'input':
        target_dir = INPUT_FOLDER
    elif folder == 'encrypted':
        target_dir = ENCRYPTED_FOLDER
    elif folder == 'decrypted':
        target_dir = DECRYPTED_FOLDER
    else:
        return jsonify({"error": "invalid folder"}), 400
        
    path = os.path.join(target_dir, filename)
    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404
        
    try:
        if platform.system() == "Windows":
            os.startfile(os.path.abspath(path))
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.call(["open", os.path.abspath(path)])
        else:
            import subprocess
            subprocess.call(["xdg-open", os.path.abspath(path)])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Media-Encrypt Studio Local Server")
    parser.add_argument("--port", type=int, default=5050, help="Port to run Flask server on")
    parser.add_argument("--host", type=str, default=None, help="Host to bind Flask server to")
    args = parser.parse_args()
    
    PORT = args.port
    host = args.host
    
    if is_colab():
        host = host or '0.0.0.0'
        from google.colab.output import eval_js
        public_url = eval_js(f"google.colab.kernel.proxyPort({PORT})")
        print("\n" + "="*70)
        print(f"Running in Google Colab environment!")
        print(f"Please click the link below to open the Media-Encrypt Studio interface:")
        print(public_url)
        print("="*70 + "\n")
        app.run(host=host, port=PORT, debug=False)
    else:
        host = host or '127.0.0.1'
        use_webview = False
        if platform.system() == "Windows":
            try:
                import webview
                use_webview = True
            except ImportError:
                print("pywebview not found. Attempting to install pywebview for standalone window support...")
                try:
                    import subprocess
                    import sys
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebview"])
                    import webview
                    use_webview = True
                    print("pywebview successfully installed!")
                except Exception as e:
                    print(f"Could not auto-install pywebview: {e}")
                    print("Tip: Install 'pywebview' to run this app in a dedicated app window (pip install pywebview)")
                
        if use_webview:
            import webview
            from threading import Thread
            # Start Flask server in background thread
            t = Thread(target=lambda: app.run(host=host, port=PORT, debug=False, use_reloader=False))
            t.daemon = True
            t.start()
            
            # Start standalone app window
            print("Starting Media-Encrypt Studio in Webview window...")
            api = WebviewApi()
            window = webview.create_window("Media-Encrypt Studio", f"http://{host}:{PORT}", width=1020, height=820, js_api=api)
            api.set_window(window)
            webview.start()
        else:
            webbrowser.open(f"http://{host}:{PORT}")
            app.run(host=host, port=PORT, debug=False)
