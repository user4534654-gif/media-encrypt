def clean_key(raw_key):
    if not raw_key: return ""
    return raw_key.replace("KEY:", "").replace(" ", "").strip()
def hash_str(s):
    h = 5381
    for c in s: h = (h * 33 + ord(c)) & 0xFFFFFFFF
    return h
def seeded_shuffle(arr, seed):
    rng_state = seed & 0xFFFFFFFF
    for i in range(len(arr) - 1, 0, -1):
        rng_state = (rng_state * 1103515245 + 12345) & 0xFFFFFFFF
        r = rng_state % (i + 1)
        arr[i], arr[r] = arr[r], arr[i]
    return arr
