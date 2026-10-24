#!/usr/bin/env python3
"""End-to-end check of the Auto Quality size target.

Builds a short test clip, runs it through the real encrypt pipeline with
the Auto Quality bitrate plan, and compares the encoded size against the
requested target (input size x (1 + pct)).
"""

import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import imageio_ffmpeg

from core.pipeline import process_media
from core.metadata_prober import probe_media_file
from main import resolve_auto_quality

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def make_clip(path, seconds=20, vbr=600, abr=128):
    subprocess.run([
        FFMPEG, '-y', '-f', 'lavfi', '-i', f'testsrc=size=640x360:rate=30:duration={seconds}',
        '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}',
        '-c:v', 'libx264', '-b:v', f'{vbr}k', '-c:a', 'aac', '-b:a', f'{abr}k',
        '-shortest', path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def run_case(src, pct, workdir):
    options = {
        'vid_format': 'auto',
        'vid_codec': 'auto',
        'vid_bitrate': 'auto',
        'auto_quality_pct': pct,
        'vid_preset': 'auto',
        'aud_sr': 'auto',
        'aud_codec': 'auto',
        'aud_bitrate': 'auto',
        'aud_method': 'auto',
        'aud_splits': 'auto',
        'vol_factor': 'auto',
        'process_video': True,
        'process_audio': True,
        'reverse': False,
        'cols': 10,
        'rows': 10,
        'seed': 1234,
        'aud_key': 1234,
        'carrier_freq': 8000,
        'aud_track': 'both',
        'scramble_tune': 'on',
    }
    options = resolve_auto_quality(src, options)
    out = os.path.join(workdir, f'locked_pct{pct}.mp4')
    process_media(src, out, options, {f'task_{pct}': 0}, f'task_{pct}')

    plan = options.get('auto_quality_plan') or {}
    in_size = os.path.getsize(src)
    out_size = os.path.getsize(out)
    target = plan.get('target_bytes') or 0
    delta = ((out_size - target) / target * 100.0) if target else 0.0
    print(f'  pct {pct:+4d}%  bitrate {options["vid_bitrate"]:>8}  '
          f'input {in_size/1024:8.1f} KB  target {target/1024:8.1f} KB  '
          f'output {out_size/1024:8.1f} KB  ({delta:+.1f}%)')
    return out_size, target, delta


def main():
    tmp = tempfile.mkdtemp(prefix='aq_e2e_')
    src = os.path.join(tmp, 'input.mp4')
    make_clip(src)
    info = probe_media_file(src)
    print(f'source: {os.path.getsize(src)/1024:.1f} KB, {info.get("duration")}, '
          f'video {info.get("video_bitrate")}, audio {info.get("audio_bitrate")}')

    failures = 0
    for pct in (0, 20, -50):
        out_size, target, delta = run_case(src, pct, tmp)
        # The encoder overshoots the ceiling only slightly; 15% is the
        # tolerance for a capped-ABR target.
        if abs(delta) > 15:
            print(f'    -> OUT OF TOLERANCE ({delta:+.1f}%)')
            failures += 1

    print('RESULT:', 'FAIL' if failures else 'PASS')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
