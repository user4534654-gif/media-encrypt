import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np
import cv2
from main import job_manager, INPUT_FOLDER, ENCRYPTED_FOLDER, DECRYPTED_FOLDER
def test_job_execution_and_cancellation():
    print("=== TEST 1: Job Manager & Image Processing ===")
    test_img_path = os.path.join(INPUT_FOLDER, "test_sample.png")
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = (120, 200, 50)
    cv2.imwrite(test_img_path, img)
    files_info = [{
        "filename": "test_sample.png",
        "path": test_img_path,
        "display_name": "test_sample.png"
    }]
    form_data = {
        "enc_video": "true",
        "enc_audio": "false",
        "cols": "4",
        "rows": "4",
        "sid": "abc1234",
        "export_svg": "false"
    }
    ok, msg, jid = job_manager.start_job("scramble", files_info, form_data)
    assert ok, f"Failed to start job: {msg}"
    print(f"Started job: {jid}")
    if job_manager.worker_thread:
        job_manager.worker_thread.join(timeout=10.0)
    st = job_manager.get_status()
    print(f"Job finished status: {st['status']}, progress: {st['progress']}, keys: {len(st['keys'])}, errors: {st['errors']}")
    assert st['status'] == 'completed', f"Expected completed, got {st['status']}"
    assert len(st['keys']) == 1, "Expected 1 key generated"
    out_file = st['keys'][0]['path']
    assert os.path.exists(out_file), f"Output file should exist: {out_file}"
    print(f"Output generated successfully: {out_file}")
    print("\n=== TEST 2: Cancellation Test ===")
    multi_files = []
    for i in range(5):
        p = os.path.join(INPUT_FOLDER, f"test_cancel_{i}.png")
        cv2.imwrite(p, img)
        multi_files.append({"filename": f"test_cancel_{i}.png", "path": p, "display_name": f"test_cancel_{i}.png"})
    ok, msg, jid = job_manager.start_job("scramble", multi_files, form_data)
    assert ok, f"Failed to start multi-file job: {msg}"
    print(f"Started multi-file job {jid}, cancelling immediately...")
    time.sleep(0.01)
    c_ok, c_msg = job_manager.cancel_job()
    assert c_ok, f"Cancellation failed: {c_msg}"
    if job_manager.worker_thread:
        job_manager.worker_thread.join(timeout=3.0)
    st_cancel = job_manager.get_status()
    print(f"Cancelled job status: {st_cancel['status']}")
    assert st_cancel['status'] == 'cancelled', f"Expected cancelled, got {st_cancel['status']}"
    print("Cancellation test passed successfully!")
    print("\n=== ALL TESTS PASSED! ===")
if __name__ == '__main__':
    test_job_execution_and_cancellation()
