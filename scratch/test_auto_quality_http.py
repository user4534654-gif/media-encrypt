#!/usr/bin/env python3
"""HTTP-level check of the Auto Quality flow.

Posts a real file to /api/job/start with auto_quality_pct, waits for the
batch job and compares the encrypted output size with the target.
"""

import io
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import imageio_ffmpeg

import main as studio

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def make_clip(path, seconds=15, vbr=500, abr=128):
    subprocess.run([
        FFMPEG, '-y', '-f', 'lavfi', '-i', f'testsrc=size=480x270:rate=25:duration={seconds}',
        '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}',
        '-c:v', 'libx264', '-b:v', f'{vbr}k', '-c:a', 'aac', '-b:a', f'{abr}k',
        '-pix_fmt', 'yuv420p', '-shortest', path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def run():
    tmp = tempfile.mkdtemp(prefix='aq_http_')
    src = os.path.join(tmp, 'clip.mp4')
    make_clip(src)
    in_size = os.path.getsize(src)

    client = studio.app.test_client()
    with open(src, 'rb') as fh:
        data = {
            'action': 'scramble',
            'enc_video': 'true',
            'enc_audio': 'true',
            'vid_format': 'auto',
            'vid_codec': 'auto',
            'vid_bitrate': 'auto',
            'vid_preset': 'auto',
            'auto_quality_pct': '20',
            'aud_sr': 'auto',
            'aud_codec': 'auto',
            'aud_bitrate': 'auto',
            'aud_method': 'inversion',
            'aud_splits': '10',
            'cols': '10',
            'rows': '10',
            'sid': 'autoquality',
            'spatial_compression_mode': 'off',
            'scramble_tune': 'on',
            'files': (fh, 'clip.mp4'),
        }
        resp = client.post('/api/job/start', data=data, content_type='multipart/form-data')
    print('POST /api/job/start ->', resp.status_code, resp.get_json())
    job_id = resp.get_json().get('job_id')

    status = {}
    for _ in range(120):
        time.sleep(0.5)
        status = client.get('/api/job/status').get_json()
        if status.get('status') in ('completed', 'error', 'cancelled'):
            break
    print('job status:', status.get('status'), '| errors:', status.get('errors'))

    keys = status.get('keys') or []
    if not keys:
        print('RESULT: FAIL (no output produced)')
        return 1
    out_path = keys[0].get('path')
    out_size = os.path.getsize(out_path)
    target = int(in_size * 1.2)
    delta = (out_size - target) / target * 100.0
    print(f'input {in_size/1024:.1f} KB -> target {target/1024:.1f} KB -> output {out_size/1024:.1f} KB ({delta:+.1f}%)')
    ok = status.get('status') == 'completed' and abs(delta) <= 15
    print('RESULT:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(run())

