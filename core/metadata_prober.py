import os
import subprocess
import re
import sys

import imageio_ffmpeg


# Canonical still-image filename extensions (with leading dots, lowercase).
# This is the SINGLE source of truth for "is this file an image?" — the same
# tuple used to be copy-pasted in job_manager / pipeline / main and drifted
# (e.g. '.jfif' was missing everywhere, so JPEGs named *.jfif were routed to
# the VIDEO pipeline and exported as .mp4). Import these helpers instead of
# writing a new endswith tuple. NOTE: '.svg' is intentionally excluded —
# neither cv2 nor the bundled Pillow can rasterize vectors, so SVGs must NOT
# enter the image pipeline.
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.jpe', '.jfif', '.jif', '.jfi',
                    '.png', '.webp', '.avif', '.bmp',
                    '.tiff', '.tif', '.gif', '.ico')


def is_image_filename(filename):
    """True when filename ends with a known still-image extension."""
    return str(filename or '').lower().endswith(IMAGE_EXTENSIONS)


# Filename extensions with no OpenCV/Pillow encoder, mapped to a safe
# same-codec standard extension. Apply when DECIDING output filenames so the
# recorded vault path always matches the bytes on disk (e.g. a '.jfif' input
# with img_format=auto must land as 'locked_*.jpg', never crash the writer
# or record a name that was silently rewritten downstream).
WRITER_ALIASES = {'.jfif': '.jpg', '.jif': '.jpg', '.jfi': '.jpg', '.ico': '.png'}


def writable_image_ext(ext):
    """Map an image extension to one the writers can actually encode."""
    return WRITER_ALIASES.get(str(ext or '').lower(), str(ext or '').lower())


def _creation_flags():
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _fmt_clock(duration):
    """Convert seconds to the 00:00:00.00 style string used elsewhere."""
    h = int(duration // 3600)
    m = int((duration % 3600) // 60)
    s = duration % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}"


def _probe_with_pyav(file_path, info):
    """Accurate per-stream probing using PyAV (bundled FFmpeg libraries)."""
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

        # Container-level total bitrate (bits/second), typically from the header.
        container_bitrate = getattr(container, 'bit_rate', None)
        if not container_bitrate and container.size and info.get('duration_sec'):
            # Derive bitrate from file size + duration as a reliable fallback.
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

        # Per-stream bitrate unknown for a stream -> estimate video bitrate
        if not info['video_bitrate_bps'] and container_bitrate and video_streams:
            # If audio stream is present, subtract estimated audio overhead
            est_audio_bps = 160000 if audio_streams else 0
            info['video_bitrate_bps'] = max(100000, int(container_bitrate - est_audio_bps))
        if not info['audio_bitrate_bps'] and audio_streams:
            # For audio streams with missing per-stream bitrate in VBR containers (e.g. Opus in WebM),
            # default to a high-quality standard 192kbps (never container video bitrate).
            info['audio_bitrate_bps'] = 192000
    finally:
        container.close()

    if info.get('video_bitrate_bps'):
        info['video_bitrate'] = f"{max(1, round(info['video_bitrate_bps'] / 1000))}k"
    if info.get('audio_bitrate_bps'):
        info['audio_bitrate'] = f"{max(1, round(info['audio_bitrate_bps'] / 1000))}k"
    return info


def parse_bitrate_kbps(bitrate_str):
    """Parse a bitrate string to integer kbps ('3000k' -> 3000).

    Accepts '3000k', '3000', 3000, '1500000bps'-style values (raw bps above
    10000 are treated as bits/sec and converted). Returns 0 when unknown.
    """
    if bitrate_str is None:
        return 0
    try:
        s = str(bitrate_str).lower().replace('bps', '').replace('k', '').strip()
        val = int(float(s))
        if val > 10000:
            val = round(val / 1000)
        return max(0, val)
    except Exception:
        return 0


def pick_max_video_bitrate(*bitrate_strs, fallback='3000k'):
    """Pick the highest video bitrate from candidates ('1499k' style).

    The composited output contains BOTH the background and the center video
    (center is pasted/resized into the frame and scrambled together), so
    encoding at the lower of the two starves the sharper source. The ceiling
    must cover the most demanding source -> max, never average/min.
    Returns a 'NNNk' string, or fallback when every candidate is unknown.
    """
    best = 0
    for b in bitrate_strs:
        best = max(best, parse_bitrate_kbps(b))
    if best > 0:
        return f"{best}k"
    return fallback


def sanitize_audio_bitrate(bitrate_str, codec=None):
    """
    Sanitizes and clamps the audio bitrate based on codec capabilities.
    Returns string like '320k', '192k', or None for lossless/uncompressed codecs.
    """
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
    """Fallback heuristic probing using the bundled ffmpeg and its stderr output."""
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

    # Per-stream bitrates appear on the stream lines, e.g.
    #   Stream #0:0: Video: h264 (High) ... , 2000 kb/s
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
    """
    Probes the media file to gather accurate per-stream metadata (codecs,
    bitrates, resolution, sample rates, duration). Uses PyAV when available
    (most accurate), falling back to parsing the bundled ffmpeg output.
    """
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
            # PyAV is not installed; fall back to parsing ffmpeg stderr output.
            info = _probe_with_ffmpeg(file_path, info)
        except Exception:
            # PyAV could not open the file; try the ffmpeg fallback.
            info = _probe_with_ffmpeg(file_path, info)
    except Exception as e:
        print(f"Error probing media file: {e}")

    return info