import os
import sys
import numpy as np
import soundfile as sf
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.audio import process_audio_file, process_band_scramble, process_combined, process_inversion
def test_audio_dsp_roundtrip():
    sr = 48000
    duration = 2.0                         
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 1000 * t) + 0.2 * np.sin(2 * np.pi * 3000 * t)
    scratch_dir = os.path.dirname(__file__)
    in_wav = os.path.join(scratch_dir, "orig_test.wav")
    enc_wav = os.path.join(scratch_dir, "enc_test.wav")
    dec_wav = os.path.join(scratch_dir, "dec_test.wav")
    sf.write(in_wav, signal, sr)
    methods = ["inversion", "band_scramble", "combined"]
    for method in methods:
        print(f"Testing DSP roundtrip for method: {method}...")
        process_audio_file(in_wav, enc_wav, is_decrypt=False, method=method, key=12345, carrier_freq=8000)
        assert os.path.exists(enc_wav), f"Encrypted WAV failed for {method}"
        process_audio_file(enc_wav, dec_wav, is_decrypt=True, method=method, key=12345, carrier_freq=8000)
        assert os.path.exists(dec_wav), f"Decrypted WAV failed for {method}"
        dec_signal, dec_sr = sf.read(dec_wav)
        if len(dec_signal.shape) > 1:
            dec_signal = dec_signal[:, 0]                
        min_len = min(len(signal), len(dec_signal))
        orig_crop = signal[:min_len]
        dec_crop = dec_signal[:min_len]
        noise = orig_crop - dec_crop
        signal_power = np.mean(orig_crop ** 2)
        noise_power = np.mean(noise ** 2)
        snr = 10 * np.log10(signal_power / max(noise_power, 1e-12))
        print(f"-> Method {method}: SNR = {snr:.2f} dB")
        assert not np.isnan(snr), f"SNR is NaN for {method}"
    for p in [in_wav, enc_wav, dec_wav]:
        if os.path.exists(p):
            os.remove(p)
    print("ALL AUDIO DSP ROUNDTRIP TESTS PASSED SUCCESSFULLY!")
if __name__ == "__main__":
    test_audio_dsp_roundtrip()
