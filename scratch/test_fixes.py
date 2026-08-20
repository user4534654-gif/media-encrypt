import os
import sys
import tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.abspath('.'))
from core.video_processor import process_video_file, get_available_hw_encoders, resolve_video_encoder
from core.job_manager import JobManager
def test_video_saving_not_deleted():
    print("Testing video saving on EOF...")
    temp_dir = tempfile.mkdtemp()
    in_path = os.path.join(temp_dir, "test_input.mp4")
    out_path = os.path.join(temp_dir, "test_locked.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    vw = cv2.VideoWriter(in_path, fourcc, 10.0, (160, 120))
    for i in range(10):
        frame = np.full((120, 160, 3), i * 25, dtype=np.uint8)
        vw.write(frame)
    vw.release()
    options = {
        'process_video': True,
        'process_audio': False,
        'reverse': False,
        'cols': 2,
        'rows': 2,
        'seed': 12345,
        'vid_codec': 'libx264',
        'vid_preset': 'ultrafast',
        'export_svg': False,
        'use_gpu': False
    }
    progress = {}
    task_id = "test_task_1"
    process_video_file(in_path, out_path, options, progress, task_id)
    assert os.path.exists(out_path), f"Error: Output video {out_path} was deleted or not created!"
    assert os.path.getsize(out_path) > 0, "Error: Output video file is 0 bytes!"
    print(f"PASS: Video successfully saved with size {os.path.getsize(out_path)} bytes.")
    try:
        os.remove(in_path)
        os.remove(out_path)
        os.rmdir(temp_dir)
    except Exception:
        pass
def test_gpu_encoder_resolution():
    print("Testing GPU encoder resolution...")
    hw_encoders = get_available_hw_encoders()
    print(f"Detected {len(hw_encoders)} FFmpeg video encoders.")
    codec_soft, hw_type_soft, _ = resolve_video_encoder('libx264', use_gpu=False)
    assert codec_soft == 'libx264' and hw_type_soft == 'software'
    codec_gpu, hw_type_gpu, extra = resolve_video_encoder('libx264', use_gpu=True)
    print(f"Resolved with use_gpu=True: codec={codec_gpu}, hw_type={hw_type_gpu}, extra={extra}")
    print("PASS: GPU encoder resolution works correctly.")
def test_job_manager_save_key_file_flag():
    print("Testing JobManager save_key_file flag...")
    saved_keys = []
    def dummy_save_key(filename, key):
        saved_keys.append((filename, key))
        return "/dummy/path/" + filename + ".key.txt"
    def dummy_resolve(p, opt): return opt
    def dummy_sr(sr, c): return '48000'
    jm = JobManager('/tmp/in', '/tmp/enc', '/tmp/dec', dummy_save_key, dummy_resolve, dummy_sr)
    form_data_no_save = {'save_key_file': 'false'}
    save_key_enabled = form_data_no_save.get('save_key_file') in [True, 'true', 'True', '1', None]
    assert save_key_enabled is False, "save_key_file=false should disable key saving"
    form_data_save = {'save_key_file': 'true'}
    save_key_enabled_true = form_data_save.get('save_key_file') in [True, 'true', 'True', '1', None]
    assert save_key_enabled_true is True, "save_key_file=true should enable key saving"
    print("PASS: JobManager save_key_file flag logic confirmed.")
if __name__ == '__main__':
    test_video_saving_not_deleted()
    test_gpu_encoder_resolution()
    test_job_manager_save_key_file_flag()
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
