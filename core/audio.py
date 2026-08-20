import soundfile as sf
import numpy as np
from core.logger import LiveDebugger
def numpy_lowpass_filter(data, cutoff, sr):
    if cutoff <= 0 or cutoff >= sr / 2.0:
        return data
    n = len(data)
    fft_vals = np.fft.rfft(data, n)
    freqs = np.fft.rfftfreq(n, d=1.0/sr)
    trans_width = min(1000.0, cutoff * 0.15)
    f_start = max(0.0, cutoff - trans_width)
    f_end = min(sr / 2.0, cutoff)
    weights = np.ones_like(freqs)
    mask_trans = (freqs >= f_start) & (freqs <= f_end)
    if f_end > f_start:
        weights[mask_trans] = 0.5 * (1.0 + np.cos(np.pi * (freqs[mask_trans] - f_start) / (f_end - f_start)))
    weights[freqs > f_end] = 0.0
    fft_vals = fft_vals * weights
    return np.fft.irfft(fft_vals, n)
def mulberry32(seed):
    state = seed & 0xFFFFFFFF
    def prng():
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        val1 = (t ^ (t >> 15)) & 0xFFFFFFFF
        val2 = (t | 1) & 0xFFFFFFFF
        t = (val1 * val2) & 0xFFFFFFFF
        imul_val1 = (t ^ (t >> 7)) & 0xFFFFFFFF
        imul_val2 = (t | 61) & 0xFFFFFFFF
        imul_res = (imul_val1 * imul_val2) & 0xFFFFFFFF
        t = (t ^ (t + imul_res)) & 0xFFFFFFFF
        res_t = (t ^ (t >> 14)) & 0xFFFFFFFF
        return res_t / 4294967296.0
    return prng
def get_permutation(n, seed):
    prng = mulberry32(seed)
    arr = list(range(n))
    for i in range(n - 1, 0, -1):
        j = int(prng() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr
def get_inverse_permutation(n, seed):
    arr = get_permutation(n, seed)
    inv = [0] * n
    for i in range(n):
        inv[arr[i]] = i
    return inv
def process_band_scramble(y, sr, key, num_splits=10, reverse=False):
    block_size = 2048
    hop_size = 1024
    win = np.sin(np.pi * np.arange(block_size) / block_size)
    pad_len = block_size - (len(y) % hop_size)
    y_pad = np.pad(y, (0, pad_len + block_size))
    num_frames = (len(y_pad) - block_size) // hop_size + 1
    out_signal = np.zeros_like(y_pad)
    freq_bins = block_size // 2 + 1
    freq_indices = np.arange(freq_bins)
    bands = np.array_split(freq_indices, num_splits)
    for f_idx in range(num_frames):
        start = f_idx * hop_size
        frame = y_pad[start:start + block_size] * win
        S = np.fft.rfft(frame)
        S_out = np.zeros_like(S)
        for i, band_indices in enumerate(bands):
            band_data = S[band_indices]
            rng = np.random.RandomState(key + i)
            perm = rng.permutation(len(band_data))
            if reverse:
                inv = np.argsort(perm)
                S_out[band_indices] = band_data[inv]
            else:
                S_out[band_indices] = band_data[perm]
        frame_out = np.fft.irfft(S_out, n=block_size) * win
        out_signal[start:start + block_size] += frame_out
    return out_signal[:len(y)]
def process_combined(y, sr, key, num_splits=10, carrier_freq=8000, reverse=False):
    block_size = 2048
    hop_size = 1024
    win = np.sin(np.pi * np.arange(block_size) / block_size)
    pad_len = block_size - (len(y) % hop_size)
    y_pad = np.pad(y, (0, pad_len + block_size))
    if not reverse:
        t = np.arange(len(y_pad)) / sr
        carrier = np.cos(2 * np.pi * carrier_freq * t)
        y_mod = y_pad * carrier
        num_frames = (len(y_mod) - block_size) // hop_size + 1
        out_signal = np.zeros_like(y_mod)
        freq_bins = block_size // 2 + 1
        freq_indices = np.arange(1, freq_bins - 1)
        bands = np.array_split(freq_indices, num_splits)
        for f_idx in range(num_frames):
            start = f_idx * hop_size
            frame = y_mod[start:start + block_size] * win
            S = np.fft.rfft(frame)
            S_enc = S.copy()
            for i, band_indices in enumerate(bands):
                perm = get_permutation(len(band_indices), key + i)
                S_enc[band_indices] = S[band_indices][perm]
            frame_out = np.fft.irfft(S_enc, n=block_size) * win
            out_signal[start:start + block_size] += frame_out
        return out_signal[:len(y)]
    else:
        num_frames = (len(y_pad) - block_size) // hop_size + 1
        y_demod_blocks = np.zeros_like(y_pad)
        freq_bins = block_size // 2 + 1
        freq_indices = np.arange(1, freq_bins - 1)
        bands = np.array_split(freq_indices, num_splits)
        for f_idx in range(num_frames):
            start = f_idx * hop_size
            frame = y_pad[start:start + block_size] * win
            S_enc = np.fft.rfft(frame)
            S_dec = S_enc.copy()
            for i, band_indices in enumerate(bands):
                inv = get_inverse_permutation(len(band_indices), key + i)
                S_dec[band_indices] = S_enc[band_indices][inv]
            frame_out = np.fft.irfft(S_dec, n=block_size) * win
            y_demod_blocks[start:start + block_size] += frame_out
        t = np.arange(len(y_demod_blocks)) / sr
        carrier = np.cos(2 * np.pi * carrier_freq * t)
        y_demod = y_demod_blocks * carrier
        nyquist = 0.5 * sr
        cutoff = min(carrier_freq, nyquist * 0.9)
        if cutoff <= 0:
            cutoff = nyquist * 0.5
        decrypted_audio = numpy_lowpass_filter(y_demod, cutoff, sr) * 2.0
        return decrypted_audio[:len(y)]
def process_inversion(y, sr, carrier_freq=8000, reverse=False):
    t = np.arange(len(y)) / sr
    carrier = np.cos(2 * np.pi * carrier_freq * t)
    processed = y * carrier
    if reverse:
        nyquist = 0.5 * sr
        cutoff = min(carrier_freq, nyquist * 0.9)
        if cutoff <= 0:
            cutoff = nyquist * 0.5
        processed = numpy_lowpass_filter(processed, cutoff, sr) * 2.0
    return processed
@LiveDebugger.trace(module_name="AUDIO")
def process_audio_file(in_wav, out_wav, is_decrypt=False, method="inversion", key=42, num_splits=10, carrier_freq=8000, vol_factor=1.0, aud_track="both", patch_intervals=None):
    try:
        y, sr = sf.read(in_wav)
        if len(y.shape) == 1:
            y = np.vstack((y, y)).T
        total_samples = len(y)
        processed = y.copy()
        def _process_slice(slice_data):
            if len(slice_data) == 0:
                return slice_data
            if method == "band_scramble":
                return process_band_scramble(slice_data, sr, key, num_splits, is_decrypt)
            elif method == "combined":
                return process_combined(slice_data, sr, key, num_splits, carrier_freq, is_decrypt)
            else:
                return process_inversion(slice_data, sr, carrier_freq, is_decrypt)
        for ch in range(y.shape[1]):
            ch_signal = y[:, ch]
            should_process_ch = True
            if aud_track == "left" and ch != 0:
                should_process_ch = False
            elif aud_track == "right" and ch != 1:
                should_process_ch = False
            if not should_process_ch:
                processed[:, ch] = ch_signal
                continue
            if patch_intervals and len(patch_intervals) > 0:
                ch_out = ch_signal.copy()
                for start_sec, end_sec in patch_intervals:
                    idx_start = max(0, min(total_samples, int(round(start_sec * sr))))
                    idx_end = max(0, min(total_samples, int(round(end_sec * sr))))
                    if idx_end <= idx_start:
                        continue
                    seg = ch_signal[idx_start:idx_end]
                    if is_decrypt and vol_factor > 0.001:
                        seg = seg * (1.0 / vol_factor)
                    seg_proc = _process_slice(seg)
                    if not is_decrypt:
                        seg_proc = seg_proc * vol_factor
                    if len(seg_proc) > len(seg):
                        seg_proc = seg_proc[:len(seg)]
                    elif len(seg_proc) < len(seg):
                        seg_proc = np.pad(seg_proc, (0, len(seg) - len(seg_proc)))
                    ch_out[idx_start:idx_end] = seg_proc
                processed[:, ch] = ch_out
            else:
                ch_signal_in = ch_signal
                if is_decrypt and vol_factor > 0.001:
                    ch_signal_in = ch_signal * (1.0 / vol_factor)
                ch_processed = _process_slice(ch_signal_in)
                if not is_decrypt:
                    ch_processed = ch_processed * vol_factor
                if len(ch_processed) > len(ch_signal):
                    ch_processed = ch_processed[:len(ch_signal)]
                elif len(ch_processed) < len(ch_signal):
                    ch_processed = np.pad(ch_processed, (0, len(ch_signal) - len(ch_processed)))
                processed[:, ch] = ch_processed
        out_audio = processed
        out_audio = np.clip(out_audio, -1.0, 1.0)
        sf.write(out_wav, out_audio, sr, subtype='PCM_16')
        return True
    except Exception as e:
        print("Audio Processor Error:", e)
        raise e
