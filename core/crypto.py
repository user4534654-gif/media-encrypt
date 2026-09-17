import zlib
import base64
import json
import os
import cv2
import numpy as np
import qrcode
def clean_key(raw_key):
    if not raw_key: return ""
    return raw_key.replace("KEY:", "").strip()
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
def compress_key(key_str, extra_payload=None):
    return str(key_str)
def decompress_key(key_input):
    cleaned = clean_key(key_input)
    if cleaned.startswith("K85:"):
        b85_part = cleaned[4:].strip()
        try:
            compressed = base64.b85decode(b85_part.encode('ascii'))
            raw_bytes = zlib.decompress(compressed)
            payload = json.loads(raw_bytes.decode('utf-8'))
            return payload.get("k", ""), payload.get("d", None)
        except Exception:
            return cleaned, None
    return cleaned, None
def generate_qr_code(data_str, output_path):
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=3,
        )
        qr.add_data(data_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
        return output_path
    except Exception as e:
        print(f"Warning: Failed to generate QR code: {e}")
        return None
def create_marker_pattern(size=24):
    pattern = np.zeros((size, size, 3), dtype=np.uint8)
    w1 = max(2, size // 6)
    pattern[w1 : size - w1, w1 : size - w1] = 255
    w2 = max(w1 + 2, size // 3)
    pattern[w2 : size - w2, w2 : size - w2] = 0
    return pattern
def _calculate_marker_boxes(w, h, rx1, ry1, rx2, ry2, placement='outside', size=18):
    import math
    rx1, rx2 = min(rx1, rx2), max(rx1, rx2)
    ry1, ry2 = min(ry1, ry2), max(ry1, ry2)
    rx1_i = int(math.floor(rx1))
    ry1_i = int(math.floor(ry1))
    rx2_i = int(math.ceil(rx2))
    ry2_i = int(math.ceil(ry2))
    if placement == 'outside':
        tl = (max(0, rx1_i - size), max(0, ry1_i - size), rx1_i, ry1_i)
        tr = (rx2_i, max(0, ry1_i - size), min(w, rx2_i + size), ry1_i)
        bl = (max(0, rx1_i - size), ry2_i, rx1_i, min(h, ry2_i + size))
        br = (rx2_i, ry2_i, min(w, rx2_i + size), min(h, ry2_i + size))
    else:         
        tl = (rx1_i, ry1_i, min(rx2_i, rx1_i + size), min(ry2_i, ry1_i + size))
        tr = (max(rx1_i, rx2_i - size), ry1_i, rx2_i, min(ry2_i, ry1_i + size))
        bl = (rx1_i, max(ry1_i, ry2_i - size), min(rx2_i, rx1_i + size), ry2_i)
        br = (max(rx1_i, rx2_i - size), max(ry1_i, ry2_i - size), rx2_i, ry2_i)
    return [tl, tr, bl, br]
_CACHED_PATTERNS = {}
def get_cached_marker_pattern_gray(size=18):
    if size not in _CACHED_PATTERNS:
        pat = create_marker_pattern(size)
        _CACHED_PATTERNS[size] = cv2.cvtColor(pat, cv2.COLOR_BGR2GRAY)
    return _CACHED_PATTERNS[size]
def check_marker_presence(img, coords, marker_size=18, threshold=0.65, search_padding=3):
    if img is None or not coords or len(coords) < 4:
        return False
    h, w = img.shape[:2]
    pat_gray = get_cached_marker_pattern_gray(marker_size)
    pw, ph = pat_gray.shape[1], pat_gray.shape[0]
    matches = 0
    for (x1, y1, x2, y2) in coords:
        if x2 <= x1 or y2 <= y1:
            continue
        sx1 = max(0, x1 - search_padding)
        sy1 = max(0, y1 - search_padding)
        sx2 = min(w, x2 + search_padding)
        sy2 = min(h, y2 + search_padding)
        if (sx2 - sx1) < pw or (sy2 - sy1) < ph:
            continue
        search_patch = img[sy1:sy2, sx1:sx2]
        if len(search_patch.shape) == 3:
            patch_gray = cv2.cvtColor(search_patch, cv2.COLOR_BGR2GRAY)
        else:
            patch_gray = search_patch
        res = cv2.matchTemplate(patch_gray, pat_gray, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, _max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            matches += 1
            if matches >= 3:
                return True
    return matches >= 3
def stamp_optical_markers(img, rx1, ry1, rx2, ry2, placement='outside', marker_size=18):
    h, w = img.shape[:2]
    coords = _calculate_marker_boxes(w, h, rx1, ry1, rx2, ry2, placement, marker_size)
    pattern = create_marker_pattern(marker_size)
    patches_b64 = []
    out_img = img.copy()
    for (x1, y1, x2, y2) in coords:
        bw, bh = x2 - x1, y2 - y1
        if bw <= 0 or bh <= 0:
            patches_b64.append("")
            continue
        orig_patch = out_img[y1:y2, x1:x2].copy()
        ret, buf = cv2.imencode('.png', orig_patch)
        if ret:
            patches_b64.append(base64.b64encode(buf).decode('ascii'))
        else:
            patches_b64.append("")
        pat_resized = cv2.resize(pattern, (bw, bh), interpolation=cv2.INTER_NEAREST)
        out_img[y1:y2, x1:x2] = pat_resized
    payload = {
        "coords": coords,
        "placement": placement,
        "size": marker_size,
        "patches": patches_b64
    }
    return out_img, payload
def inpaint_optical_markers(img, rx1, ry1, rx2, ry2, placement='outside', marker_size=18):
    if img is None:
        return img
    h, w = img.shape[:2]
    if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
        rx1, ry1, rx2, ry2 = int(rx1 * w), int(ry1 * h), int(rx2 * w), int(ry2 * h)
    coords = _calculate_marker_boxes(w, h, rx1, ry1, rx2, ry2, placement, marker_size)
    mask = np.zeros((h, w), dtype=np.uint8)
    for (x1, y1, x2, y2) in coords:
        mx1, my1 = max(0, x1 - 1), max(0, y1 - 1)
        mx2, my2 = min(w, x2 + 1), min(h, y2 + 1)
        if mx2 > mx1 and my2 > my1:
            mask[my1:my2, mx1:mx2] = 255
    try:
        inpainted = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
        return inpainted
    except Exception as e:
        print(f"Warning: inpaint_optical_markers failed: {e}")
        return img
def restore_optical_markers(img, optical_payload=None, rx1=None, ry1=None, rx2=None, ry2=None, placement='outside', marker_size=18):
    if img is None:
        return img
    if optical_payload and isinstance(optical_payload, dict):
        coords = optical_payload.get("coords", [])
        patches = optical_payload.get("patches", [])
        has_valid_patches = any(p for p in patches)
        if has_valid_patches:
            out_img = img.copy()
            restored_any = False
            for (x1, y1, x2, y2), p_b64 in zip(coords, patches):
                if not p_b64:
                    continue
                try:
                    buf = base64.b64decode(p_b64.encode('ascii'))
                    patch = cv2.imdecode(np.frombuffer(buf, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if patch is not None:
                        bh, bw = patch.shape[:2]
                        out_img[y1 : y1 + bh, x1 : x1 + bw] = patch
                        restored_any = True
                except Exception as e:
                    print(f"Warning: Failed to restore optical marker patch: {e}")
            if restored_any:
                return out_img
    if rx1 is not None and ry1 is not None and rx2 is not None and ry2 is not None:
        return inpaint_optical_markers(img, rx1, ry1, rx2, ry2, placement=placement, marker_size=marker_size)
    if optical_payload and isinstance(optical_payload, dict):
        coords = optical_payload.get("coords", [])
        if len(coords) == 4:
            h, w = img.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            for (x1, y1, x2, y2) in coords:
                mx1, my1 = max(0, x1 - 1), max(0, y1 - 1)
                mx2, my2 = min(w, x2 + 1), min(h, y2 + 1)
                if mx2 > mx1 and my2 > my1:
                    mask[my1:my2, mx1:mx2] = 255
            try:
                return cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
            except Exception:
                pass
    return img
def _group_markers_into_rois(clustered_pts, m_size, w, h, placement='outside', img_for_verification=None):
    if len(clustered_pts) < 4:
        return []
    pts = sorted(clustered_pts, key=lambda p: (p[1], p[0]))
    tol = max(4, min(10, m_size // 3))
    detected_rois = []
    used_pts = set()
    n = len(pts)
    for i in range(n):
        if i in used_pts:
            continue
        tl = pts[i]
        for j in range(i + 1, n):
            if j in used_pts:
                continue
            tr = pts[j]
            if tr[0] <= tl[0] + (2 * m_size):
                continue
            if abs(tr[1] - tl[1]) > tol:
                continue
            for k in range(i + 1, n):
                if k in used_pts or k == j:
                    continue
                bl = pts[k]
                if bl[1] <= tl[1] + (2 * m_size):
                    continue
                if abs(bl[0] - tl[0]) > tol:
                    continue
                for l in range(i + 1, n):
                    if l in used_pts or l == j or l == k:
                        continue
                    br = pts[l]
                    if abs(br[0] - tr[0]) <= tol and abs(br[1] - bl[1]) <= tol:
                        if placement == 'inside':
                            rx1 = max(0, min(tl[0], bl[0]))
                            ry1 = max(0, min(tl[1], tr[1]))
                            rx2 = min(w, max(tr[0] + m_size, br[0] + m_size))
                            ry2 = min(h, max(bl[1] + m_size, br[1] + m_size))
                        else:             
                            rx1 = max(0, max(tl[0] + m_size, bl[0] + m_size))
                            ry1 = max(0, max(tl[1] + m_size, tr[1] + m_size))
                            rx2 = min(w, min(tr[0], br[0]))
                            ry2 = min(h, min(bl[1], br[1]))
                        if (rx2 - rx1) >= (2 * m_size) and (ry2 - ry1) >= (2 * m_size):
                            if img_for_verification is not None:
                                test_boxes = _calculate_marker_boxes(w, h, rx1, ry1, rx2, ry2, placement, m_size)
                                if not check_marker_presence(img_for_verification, test_boxes, marker_size=m_size, threshold=0.65):
                                    continue
                            norm_roi = (
                                round(rx1 / w, 4),
                                round(ry1 / h, 4),
                                round(rx2 / w, 4),
                                round(ry2 / h, 4)
                            )
                            if not any(
                                abs(norm_roi[0] - ex[0]) < 0.03 and
                                abs(norm_roi[1] - ex[1]) < 0.03 and
                                abs(norm_roi[2] - ex[2]) < 0.03 and
                                abs(norm_roi[3] - ex[3]) < 0.03
                                for ex in detected_rois
                            ):
                                detected_rois.append(norm_roi)
                                used_pts.update([i, j, k, l])
                        break
                if i in used_pts:
                    break
            if i in used_pts:
                break
    return detected_rois
def detect_all_optical_markers(img, placement='outside'):
    if img is None:
        return []
    h, w = img.shape[:2]
    if h < 32 or w < 32:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    all_rois = []
    for m_size in [18, 24, 16, 32]:
        pattern = create_marker_pattern(m_size)
        pat_gray = cv2.cvtColor(pattern, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray, pat_gray, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.78)
        pts = list(zip(*loc[::-1]))          
        if len(pts) >= 4:
            clustered = []
            half = max(4, m_size // 2)
            for (px, py) in pts:
                if not any(abs(px - cx) < half and abs(py - cy) < half for (cx, cy) in clustered):
                    clustered.append((int(px), int(py)))
            if len(clustered) >= 4:
                rois = _group_markers_into_rois(clustered, m_size, w, h, placement=placement, img_for_verification=img)
                for r in rois:
                    if not any(
                        abs(r[0] - ex[0]) < 0.03 and
                        abs(r[1] - ex[1]) < 0.03 and
                        abs(r[2] - ex[2]) < 0.03 and
                        abs(r[3] - ex[3]) < 0.03
                        for ex in all_rois
                    ):
                        all_rois.append(r)
        if all_rois:
            return all_rois
    return all_rois
def detect_optical_markers(img, placement='outside'):
    rois = detect_all_optical_markers(img, placement=placement)
    return rois[0] if rois else None
