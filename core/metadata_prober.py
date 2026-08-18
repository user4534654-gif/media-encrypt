import os
import subprocess
import re
import sys
import imageio_ffmpeg
def _creation_flags():
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0
def _fmt_clock(duration):
    h = int(duration // 3600)
    m = int((duration % 3600) // 60)
    s = duration % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"
def _probe_with_pyav(file_path, info):
    import av
    container = av.open(file_path)
    try:
        fmt = container.format
        if fmt is not None and fmt.name:
            info['format'] = fmt.name
        duration = container.duration
        if duration:
            seconds = float(duration) / float(av.time_base)
            if seconds > 0:
                info['duration'] = _fmt_clock(seconds)
                info['duration_sec'] = seconds
        container_bitrate = getattr(container, 'bit_rate', None)
        if not container_bitrate and container.size and info.get('duration_sec'):
            container_bitrate = int((container.size * 8) / info['duration_sec'])
        video_streams = [s for s in container.streams if s.type == 'video']
        audio_streams = [s for s in container.streams if s.type == 'audio']
        if video_streams:
            vs = video_streams[0]
            ctx = vs.codec_context
            codec_name = ctx.name or 'unknown'
            info['video_codec'] = codec_name.lower()
            if ctx.width and ctx.height:
                info['resolution'] = f"{ctx.width}x{ctx.height}"
            stream_bitrate = getattr(vs, 'bit_rate', None) or getattr(ctx, 'bit_rate', None)
            if stream_bitrate:
                info['video_bitrate_bps'] = int(stream_bitrate)
        if audio_streams:
            aus = audio_streams[0]
            ctx = aus.codec_context
            codec_name = ctx.name or 'unknown'
            info['audio_codec'] = codec_name.lower()
            if ctx.sample_rate:
                info['audio_sr'] = str(ctx.sample_rate)
            stream_bitrate = getattr(aus, 'bit_rate', None) or getattr(ctx, 'bit_rate', None)
            if stream_bitrate:
                info['audio_bitrate_bps'] = int(stream_bitrate)
        if not info['video_bitrate_bps'] and container_bitrate and video_streams:
            est_audio_bps = 160000 if audio_streams else 0
            info['video_bitrate_bps'] = max(100000, int(container_bitrate - est_audio_bps))
        if not info['audio_bitrate_bps'] and audio_streams:
            info['audio_bitrate_bps'] = 192000
    finally:
        container.close()
    if info.get('video_bitrate_bps'):
        info['video_bitrate'] = f"{max(1, round(info['video_bitrate_bps'] / 1000))}k"
    if info.get('audio_bitrate_bps'):
        info['audio_bitrate'] = f"{max(1, round(info['audio_bitrate_bps'] / 1000))}k"
    return info
def sanitize_audio_bitrate(bitrate_str, codec=None):
    if not bitrate_str or bitrate_str == 'auto':
        return '320k'
    codec_lower = str(codec).lower() if codec else ''
    if codec_lower in ['flac', 'pcm_s16le', 'pcm_s24le', 'alac']:
        return None
    try:
        val_str = str(bitrate_str).lower().replace('k', '').replace('bps', '').strip()
        val = int(val_str)
        if val > 10000:
            val = round(val / 1000)
    except Exception:
        val = 192
    if 'opus' in codec_lower:
        val = max(32, min(val, 512))
    elif 'mp3' in codec_lower:
        val = max(32, min(val, 320))
    elif 'aac' in codec_lower:
        val = max(32, min(val, 320))
    else:
        val = max(32, min(val, 320))
    return f"{val}k"
def _probe_with_ffmpeg(file_path, info):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    result = subprocess.run(
        [ffmpeg_exe, '-i', file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='ignore',
        creationflags=_creation_flags()
    )
    metadata = result.stderr
    video_match = re.search(r'Video:\s+([a-zA-Z0-9_-]+)', metadata)
    if video_match:
        info['video_codec'] = video_match.group(1).lower()
    res_match = re.search(r'Video:.*,\s+(\d{3,4})x(\d{3,4})', metadata)
    if res_match:
        info['resolution'] = f"{res_match.group(1)}x{res_match.group(2)}"
    dur_match = re.search(r'Duration:\s+(\d{2}):(\d{2}):(\d{2}\.\d{2})', metadata)
    if dur_match:
        h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), float(dur_match.group(3))
        info['duration_sec'] = h * 3600 + m * 60 + s
        info['duration'] = _fmt_clock(info['duration_sec'])
    audio_match = re.search(r'Audio:\s+([a-zA-Z0-9_-]+)', metadata)
    if audio_match:
        info['audio_codec'] = audio_match.group(1).lower()
    sr_match = re.search(r'Audio:.*,\s+(\d+)\s+Hz', metadata)
    if sr_match:
        info['audio_sr'] = sr_match.group(1)
    video_bit = re.search(r'Video:.*?(\d+)\s+kb/s', metadata)
    if video_bit:
        info['video_bitrate'] = f"{video_bit.group(1)}k"
    audio_bit = re.search(r'Audio:.*?(\d+)\s+kb/s', metadata)
    if audio_bit:
        info['audio_bitrate'] = f"{audio_bit.group(1)}k"
    if not info.get('video_bitrate'):
        bitrate_match = re.search(r'bitrate:\s+(\d+)\s+kb/s', metadata)
        if bitrate_match:
            info['video_bitrate'] = f"{bitrate_match.group(1)}k"
    return info
def probe_media_file(file_path):
    info = {
        'format': os.path.splitext(file_path)[1].lower(),
        'file_size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2) if os.path.exists(file_path) else 0,
        'video_codec': None,
        'video_bitrate': None,
        'video_bitrate_bps': None,
        'resolution': None,
        'duration': None,
        'duration_sec': None,
        'audio_codec': None,
        'audio_sr': None,
        'audio_bitrate': None,
        'audio_bitrate_bps': None,
    }
    if not os.path.exists(file_path):
        return info
    try:
        try:
            info = _probe_with_pyav(file_path, info)
        except (ImportError, ModuleNotFoundError):
            info = _probe_with_ffmpeg(file_path, info)
        except Exception:
            info = _probe_with_ffmpeg(file_path, info)
    except Exception as e:
        print(f"Error probing media file: {e}")
    return info
