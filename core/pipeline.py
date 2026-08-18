import os
import sys
import subprocess
import imageio_ffmpeg
from core.logger import LiveDebugger
creation_flags = 0
if sys.platform == "win32":
    creation_flags = subprocess.CREATE_NO_WINDOW
from core.audio import process_audio_file
from core.image_processor import process_image_file
from core.video_processor import process_video_file
from core.tempdir import get_temp_file_path
@LiveDebugger.trace(module_name="PIPELINE")
def process_media(input_path, output_path, options, progress_dict, task_id):
    proc_aud = options.get('process_audio')
    reverse = options.get('reverse')
    carrier_freq = options.get('carrier_freq', 8000)
    is_image = input_path.lower().endswith(('.jpg', '.png', '.jpeg', '.bmp', '.webp', '.avif'))
    is_audio = input_path.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a'))
    if is_image:
        LiveDebugger.log("ROUTE", f"Routing '{os.path.basename(input_path)}' to IMAGE processing pipeline", level="INFO", module="PIPELINE")
        process_image_file(input_path, output_path, options, progress_dict, task_id)
        return
    if is_audio:
        LiveDebugger.log("ROUTE", f"Routing '{os.path.basename(input_path)}' to AUDIO processing pipeline", level="INFO", module="PIPELINE")
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_wav = get_temp_file_path(os.path.basename(input_path) + "_temp.wav")
        LiveDebugger.log("AUDIO_DECODE", f"Converting audio input to temp WAV -> {temp_wav}", level="DEBUG", module="PIPELINE")
        subprocess.run([ffmpeg_exe, '-y', '-i', input_path, temp_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        if proc_aud: 
            LiveDebugger.log("AUDIO_SCRAMBLE", f"Processing audio track | decrypt={reverse}, method={options.get('aud_method', 'inversion')}", level="DEBUG", module="PIPELINE")
            process_audio_file(
                temp_wav, temp_wav, is_decrypt=reverse,
                method=options.get('aud_method', 'inversion'),
                key=options.get('aud_key', 42),
                num_splits=options.get('aud_splits', 10),
                carrier_freq=carrier_freq,
                vol_factor=options.get('vol_factor', 1.0),
                aud_track=options.get('aud_track', 'both')
            )
        progress_dict[task_id] = 50
        from core.metadata_prober import sanitize_audio_bitrate
        out_lower = output_path.lower()
        if out_lower.endswith('.wav'):
            codec_args = ['-c:a', 'pcm_s16le']
        elif out_lower.endswith('.mp3'):
            aud_b = sanitize_audio_bitrate(options.get('aud_bitrate', '192k'), 'libmp3lame') or '192k'
            codec_args = ['-c:a', 'libmp3lame', '-b:a', aud_b]
        else:
            target_codec = options.get('aud_codec', 'aac')
            aud_b = sanitize_audio_bitrate(options.get('aud_bitrate', '192k'), target_codec)
            if aud_b and target_codec not in ['pcm_s16le', 'flac']:
                codec_args = ['-c:a', target_codec, '-b:a', aud_b]
            else:
                codec_args = ['-c:a', target_codec]
        LiveDebugger.log("AUDIO_ENCODE", f"Encoding final audio output -> '{output_path}' with args: {codec_args}", level="DEBUG", module="PIPELINE")
        subprocess.run([ffmpeg_exe, '-y', '-i', temp_wav] + codec_args + ['-ar', options.get('aud_sr', '48000'), output_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        if os.path.exists(temp_wav): 
            os.remove(temp_wav)
        progress_dict[task_id] = 100
        LiveDebugger.log("COMPLETE", f"Audio processing finished successfully: '{output_path}'", level="INFO", module="PIPELINE")
        return
    LiveDebugger.log("ROUTE", f"Routing '{os.path.basename(input_path)}' to VIDEO processing pipeline", level="INFO", module="PIPELINE")
    process_video_file(input_path, output_path, options, progress_dict, task_id)
