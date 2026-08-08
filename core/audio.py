import soundfile as sf
import numpy as np
from core.logger import LiveDebugger
def numpy_lowpass_filter(data, cutoff, sr):
    n = len(data)
    fft_vals = np.fft.rfft(data, n)
    freqs = np.fft.rfftfreq(n, d=1.0/sr)
    fft_vals[freqs > cutoff] = 0.0
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
    pad_len = block_size - (len(y) % block_size)
    if pad_len == block_size:
        pad_len = 0
    y_pad = np.pad(y, (0, pad_len))
    blocks = y_pad.reshape(-1, block_size)
    S = np.fft.rfft(blocks, axis=1).T                                  
    freq_bins = S.shape[0]
    freq_indices = np.arange(freq_bins)
    bands = np.array_split(freq_indices, num_splits)
    S_out = np.zeros_like(S)
    for i, band_indices in enumerate(bands):
        band_data = S[band_indices, :]
        original_shape = band_data.shape
        flat_data = band_data.flatten()
        rng = np.random.RandomState(key + i)
        perm = rng.permutation(len(flat_data))
        if reverse:
            inv = np.argsort(perm)
            out_flat = flat_data[inv]
        else:
            out_flat = flat_data[perm]
        S_out[band_indices, :] = out_flat.reshape(original_shape)
    S_out = S_out.T
    blocks_out = np.fft.irfft(S_out, n=block_size, axis=1)
    return blocks_out.reshape(-1)
def process_combined(y, sr, key, num_splits=10, carrier_freq=8000, reverse=False):
    block_size = 2048
    pad_len = block_size - (len(y) % block_size)
    if pad_len == block_size:
        pad_len = 0
    y_padded = np.pad(y, (0, pad_len))
    num_blocks = len(y_padded) // block_size
    if not reverse:
        t = np.arange(len(y_padded)) / sr
        carrier = np.cos(2 * np.pi * carrier_freq * t)
        y_mod = y_padded * carrier
        blocks = y_mod.reshape(num_blocks, block_size)
        S = np.fft.rfft(blocks, axis=1).T
        freq_bins = S.shape[0]
        freq_indices = np.arange(1, freq_bins - 1)
        bands = np.array_split(freq_indices, num_splits)
        S_enc = S.copy()
        for i, band_indices in enumerate(bands):
            perm = get_permutation(len(band_indices), key + i)
            S_enc[band_indices, :] = S[band_indices, :][perm, :]
        S_enc = S_enc.T
        blocks_enc = np.fft.irfft(S_enc, n=block_size, axis=1)
        return blocks_enc.reshape(-1)
    else:
        blocks = y_padded.reshape(num_blocks, block_size)
        S_enc = np.fft.rfft(blocks, axis=1).T
        freq_bins = S_enc.shape[0]
        freq_indices = np.arange(1, freq_bins - 1)
        bands = np.array_split(freq_indices, num_splits)
        S_dec = S_enc.copy()
        for i, band_indices in enumerate(bands):
            inv = get_inverse_permutation(len(band_indices), key + i)
            S_dec[band_indices, :] = S_enc[band_indices, :][inv, :]
        S_dec = S_dec.T
        blocks_dec = np.fft.irfft(S_dec, n=block_size, axis=1)
        y_demod_blocks = blocks_dec.reshape(-1)
        t = np.arange(len(y_demod_blocks)) / sr
        carrier = np.cos(2 * np.pi * carrier_freq * t)
        y_demod = y_demod_blocks * carrier
        nyquist = 0.5 * sr
        cutoff = min(carrier_freq, nyquist * 0.9)
        decrypted_audio = numpy_lowpass_filter(y_demod, cutoff, sr) * 2.0
        return decrypted_audio
def process_inversion(y, sr, carrier_freq=8000, reverse=False):
    t = np.arange(len(y)) / sr
    carrier = np.cos(2 * np.pi * carrier_freq * t)
    processed = y * carrier
    if reverse:
        nyquist = 0.5 * sr
        cutoff = min(carrier_freq, nyquist * 0.9)
        processed = numpy_lowpass_filter(processed, cutoff, sr) * 2.0
    return processed
@LiveDebugger.trace(module_name="AUDIO")
def process_audio_file(in_wav, out_wav, is_decrypt=False, method="inversion", key=42, num_splits=10, carrier_freq=8000, vol_factor=1.0, aud_track="both"):
    try:
        y, sr = sf.read(in_wav)
        if len(y.shape) == 1:
            y = np.vstack((y, y)).T
        processed = np.zeros_like(y)
        for ch in range(y.shape[1]):
            ch_signal = y[:, ch]
            should_process_ch = True
            if aud_track == "left" and ch != 0:
                should_process_ch = False
            elif aud_track == "right" and ch != 1:
                should_process_ch = False
            if should_process_ch:
                ch_signal_in = ch_signal
                if is_decrypt:
                    if vol_factor > 0.001:
                        ch_signal_in = ch_signal * (1.0 / vol_factor)
                if method == "band_scramble":
                    ch_processed = process_band_scramble(ch_signal_in, sr, key, num_splits, is_decrypt)
                elif method == "combined":
                    ch_processed = process_combined(ch_signal_in, sr, key, num_splits, carrier_freq, is_decrypt)
                else:
                    ch_processed = process_inversion(ch_signal_in, sr, carrier_freq, is_decrypt)
                if not is_decrypt:
                    ch_processed = ch_processed * vol_factor
            else:
                ch_processed = ch_signal
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
