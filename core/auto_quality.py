"""Auto Quality: target output size -> encoder bitrate plan.

The Auto Quality slider expresses the desired output size as a percentage
delta against the INPUT file size (0% = same size as the input, +20% = 20%
bigger). This module turns that single number into a concrete bitrate plan:
the bitrate budget of the target size is split between the video stream and
the audio stream, the container overhead is subtracted, and the result is
clamped to the range the encoders accept.

Pure math, no I/O: the caller supplies the probed size, duration and audio
bitrate. Keeping it here makes the plan testable and reusable by both the
single-file route (main.py) and the batch route (core/job_manager.py).
"""

# Slider range, mirrored by the UI control.
AUTO_QUALITY_MIN_PCT = -50
AUTO_QUALITY_MAX_PCT = 100

# Encoder-acceptable video bitrate window (matches the wave editor range).
AUTO_QUALITY_MIN_KBPS = 100
AUTO_QUALITY_MAX_KBPS = 25000

# Muxer overhead (moov atom / index) as a share of the total budget.
CONTAINER_OVERHEAD_RATIO = 0.02


def clamp_pct(pct):
    """Clamp a size delta to the supported slider range (-50..+100)."""
    try:
        value = int(round(float(pct)))
    except (TypeError, ValueError):
        return 0
    return max(AUTO_QUALITY_MIN_PCT, min(AUTO_QUALITY_MAX_PCT, value))


def estimate_audio_kbps(audio_bitrate, sample_rate=None, codec=None):
    """Bitrate reserved for the audio stream of the output.

    Returns 0 when the output carries no audio. Lossless / uncompressed
    codecs have no -b:a, so their size is estimated from the sample rate
    (16-bit stereo PCM, ~60% of that for FLAC) and therefore only
    approximate.
    """
    codec_l = str(codec or '').lower()
    if codec_l in ('flac', 'pcm_s16le', 'pcm_s24le', 'alac', 'wav'):
        try:
            sr = int(sample_rate or 48000)
        except (TypeError, ValueError):
            sr = 48000
        sr = max(8000, min(96000, sr))
        pcm_kbps = sr * 16 * 2 / 1000.0
        if 'pcm' in codec_l:
            return int(round(pcm_kbps))
        return int(round(pcm_kbps * 0.6))
    if not audio_bitrate:
        return 0
    try:
        value = int(float(str(audio_bitrate).lower().replace('k', '').replace('bps', '').strip()))
    except (TypeError, ValueError):
        return 0
    if value > 10000:
        value = round(value / 1000)
    return max(0, value)


def plan_size_target(input_bytes, duration_sec, pct, audio_kbps=0, floor_kbps=0):
    """Build the bitrate plan for a target output size.

    input_bytes   size of the source file on disk (bytes)
    duration_sec  source duration (seconds)
    pct           size delta in percent (-50..+100)
    audio_kbps    bitrate reserved for the audio stream (0 = no audio)
    floor_kbps    minimum video bitrate (e.g. the pasted center source, which
                  must not be starved by a low size target)

    Returns a plan dict, or None when the inputs are unusable (unknown size
    or duration) so the caller can keep its legacy bitrate path.
    """
    try:
        in_bytes = int(input_bytes or 0)
        duration = float(duration_sec or 0)
    except (TypeError, ValueError):
        return None
    if in_bytes <= 0 or duration <= 0:
        return None

    pct = clamp_pct(pct)
    target_bytes = int(round(in_bytes * (1.0 + pct / 100.0)))
    if target_bytes <= 0:
        return None

    total_kbps = (target_bytes * 8) / duration / 1000.0
    overhead_kbps = total_kbps * CONTAINER_OVERHEAD_RATIO
    try:
        audio_kbps = max(0, int(round(audio_kbps or 0)))
    except (TypeError, ValueError):
        audio_kbps = 0

    video_kbps = total_kbps - overhead_kbps - audio_kbps

    # A pasted center video is part of the composited frame: encoding it
    # below its own source bitrate would visibly ruin it, so it acts as a
    # floor on the target (the output then exceeds the size target).
    floor_applied = False
    try:
        floor = int(round(floor_kbps or 0))
    except (TypeError, ValueError):
        floor = 0
    if floor > 0 and video_kbps < floor:
        video_kbps = floor
        floor_applied = True

    clamped = None
    if video_kbps < AUTO_QUALITY_MIN_KBPS:
        video_kbps = AUTO_QUALITY_MIN_KBPS
        clamped = 'min'
    elif video_kbps > AUTO_QUALITY_MAX_KBPS:
        video_kbps = AUTO_QUALITY_MAX_KBPS
        clamped = 'max'

    return {
        'pct': pct,
        'input_bytes': in_bytes,
        'target_bytes': target_bytes,
        'duration_sec': duration,
        'total_kbps': int(round(total_kbps)),
        'audio_kbps': audio_kbps,
        'overhead_kbps': int(round(overhead_kbps)),
        'video_kbps': int(round(video_kbps)),
        'floor_applied': floor_applied,
        'clamped': clamped,
    }


def format_plan(plan):
    """One-line human summary of a plan (used by the Live Debugger)."""
    if not plan:
        return 'no plan'
    parts = [
        f"input {plan['input_bytes'] / 1048576:.1f} MB",
        f"target {plan['target_bytes'] / 1048576:.1f} MB ({plan['pct']:+d}%)",
        f"video {plan['video_kbps']}k",
        f"audio {plan['audio_kbps']}k",
    ]
    if plan.get('floor_applied'):
        parts.append('raised to the center-source floor')
    if plan.get('clamped'):
        parts.append(f"clamped ({plan['clamped']})")
    return ', '.join(parts)
