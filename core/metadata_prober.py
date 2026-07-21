import subprocess
import re
import os
import imageio_ffmpeg

def probe_media_file(file_path):
    """
    Probes the media file using ffmpeg -i to gather metadata about video/audio codecs,
    bitrates, sample rates, etc.
    """
    info = {
        'format': os.path.splitext(file_path)[1].lower(),
        'file_size_mb': round(os.path.getsize(file_path) / (1024 * 1024), 2) if os.path.exists(file_path) else 0,
        'video_codec': None,
        'video_bitrate': None,
        'resolution': None,
        'duration': None,
        'audio_codec': None,
        'audio_sr': None,
        'audio_bitrate': None
    }
    
    try:
        import sys
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run(
            [ffmpeg_exe, '-i', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            creationflags=creation_flags
        )
        metadata = result.stderr
        
        # 1. Video stream detection
        video_match = re.search(r'Video:\s+([a-zA-Z0-9_-]+)', metadata)
        if video_match:
            info['video_codec'] = video_match.group(1).lower()
            
        # 2. Resolution detection (e.g. 1920x1080)
        res_match = re.search(r'Video:.*,\s+(\d{3,4})x(\d{3,4})', metadata)
        if res_match:
            info['resolution'] = f"{res_match.group(1)}x{res_match.group(2)}"
            
        # 3. Duration detection (e.g. 00:01:23.45)
        dur_match = re.search(r'Duration:\s+(\d{2}:\d{2}:\d{2}\.\d{2})', metadata)
        if dur_match:
            info['duration'] = dur_match.group(1)
            
        # 4. Audio stream detection
        audio_match = re.search(r'Audio:\s+([a-zA-Z0-9_-]+)', metadata)
        if audio_match:
            info['audio_codec'] = audio_match.group(1).lower()
            
        # 5. Audio sample rate detection
        sr_match = re.search(r'Audio:.*,\s+(\d+)\s+Hz', metadata)
        if sr_match:
            info['audio_sr'] = sr_match.group(1)
            
        # 6. Bitrate detection
        bitrate_match = re.search(r'bitrate:\s+(\d+)\s+kb/s', metadata)
        if bitrate_match:
            info['video_bitrate'] = f"{bitrate_match.group(1)}k"
            info['audio_bitrate'] = "192k"
            
    except Exception as e:
        print(f"Error probing media file: {e}")
        
    return info
