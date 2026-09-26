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
        def _shift(x1, y1):
            if w > size:
                x1 = min(max(x1, 0), w - size)
            else:
                x1 = 0
            if h > size:
                y1 = min(max(y1, 0), h - size)
            else:
                y1 = 0
            return (x1, y1, min(w, x1 + size), min(h, y1 + size))
        tl = _shift(rx1_i - size, ry1_i - size)
        tr = _shift(rx2_i, ry1_i - size)
        bl = _shift(rx1_i - size, ry2_i)
        br = _shift(rx2_i, ry2_i)
    else:         
        tl = (rx1_i, ry1_i, min(rx2_i, rx1_i + size), min(ry2_i, ry1_i + size))
        tr = (max(rx1_i, rx2_i - size), ry1_i, rx2_i, min(ry2_i, ry1_i + size))
        bl = (rx1_i, max(ry1_i, ry2_i - size), min(rx2_i, rx1_i + size), ry2_i)
        br = (max(rx1_i, rx2_i - size), max(ry1_i, ry2_i - size), rx2_i, ry2_i)
    return [tl, tr, bl, br]
def effective_marker_placement(center=False, center_path=None,
                               patch_segments=None, patch_roi=None,
                               optical_markers=False, placement='outside'):
    return placement or 'outside'
_CACHED_PATTERNS = {}
def get_cached_marker_pattern_gray(size=18):
    if size not in _CACHED_PATTERNS:
        pat = create_marker_pattern(size)
        _CACHED_PATTERNS[size] = cv2.cvtColor(pat, cv2.COLOR_BGR2GRAY)
    return _CACHED_PATTERNS[size]
def _marker_match_scores(img, boxes, marker_size=18):
    if img is None or not boxes:
        return []
    h, w = img.shape[:2]
    pat_gray = get_cached_marker_pattern_gray(marker_size)
    pw, ph = pat_gray.shape[1], pat_gray.shape[0]
    scores = []
    for (x1, y1, x2, y2) in boxes:
        if x2 <= x1 or y2 <= y1:
            scores.append(0.0)
            continue
        sx1 = max(0, x1 - 3)
        sy1 = max(0, y1 - 3)
        sx2 = min(w, x2 + 3)
        sy2 = min(h, y2 + 3)
        if (sx2 - sx1) < pw or (sy2 - sy1) < ph:
            scores.append(0.0)
            continue
        search_patch = img[sy1:sy2, sx1:sx2]
        if len(search_patch.shape) == 3:
            patch_gray = cv2.cvtColor(search_patch, cv2.COLOR_BGR2GRAY)
        else:
            patch_gray = search_patch
        res = cv2.matchTemplate(patch_gray, pat_gray, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, _max_loc = cv2.minMaxLoc(res)
        scores.append(float(max_val))
    return scores
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
        rx1, ry1, rx2, ry2 = int(round(rx1 * w)), int(round(ry1 * h)), int(round(rx2 * w)), int(round(ry2 * h))
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
def _refine_marker_box(img, approx_box, radius=8):
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    base = get_cached_marker_pattern_gray(18)
    ax1, ay1, ax2, ay2 = approx_box
    best = None
    for sw in range(12, 33, 2):
        for sh in range(12, 33, 2):
            pat = base if (sw == 18 and sh == 18) else cv2.resize(base, (sw, sh), interpolation=cv2.INTER_NEAREST)
            sx1, sy1 = max(0, ax1 - radius), max(0, ay1 - radius)
            sx2, sy2 = min(w, ax2 + radius), min(h, ay2 + radius)
            if sx2 - sx1 < sw or sy2 - sy1 < sh:
                continue
            res = cv2.matchTemplate(gray[sy1:sy2, sx1:sx2], pat, cv2.TM_CCOEFF_NORMED)
            _mn, mx, _mnl, mxl = cv2.minMaxLoc(res)
            cand = (float(mx), sx1 + mxl[0], sy1 + mxl[1], sw, sh)
            if best is None or cand[0] > best[0] + 1e-9 or (abs(cand[0] - best[0]) <= 1e-9 and sw * sh > best[3] * best[4]):
                best = cand
    if best is None or best[0] < 0.45:
        return None
    _v, bx, by, sw, sh = best
    return (bx, by, bx + sw, by + sh, _v)
def refine_roi_from_centers(img, roi, placement='outside', m_size=18):
    if img is None or not roi or len(roi) < 4:
        return roi
    h, w = img.shape[:2]
    rx1, ry1, rx2, ry2 = roi
    if max(rx1, ry1, rx2, ry2) <= 1.0 and min(rx1, ry1, rx2, ry2) >= 0:
        px1, py1, px2, py2 = int(round(rx1 * w)), int(round(ry1 * h)), int(round(rx2 * w)), int(round(ry2 * h))
    else:
        px1, py1, px2, py2 = int(rx1), int(ry1), int(rx2), int(ry2)
    boxes = _calculate_marker_boxes(w, h, px1, py1, px2, py2, placement, m_size)
    refined = []
    for box in boxes:
        bw, bh = box[2] - box[0], box[3] - box[1]
        if bw <= 4 or bh <= 4:
            refined.append(None)
            continue
        refined.append(_refine_marker_box(img, box))
    TL, TR, BL, BR = refined
    if sum(1 for b in refined if b) < 3:
        return roi
    if placement == 'inside':
        ex1 = [b[0] for b in (TL, BL) if b]
        ey1 = [b[1] for b in (TL, TR) if b]
        ex2 = [b[2] for b in (TR, BR) if b]
        ey2 = [b[3] for b in (BL, BR) if b]
    else:
        ex1 = [b[2] for b in (TL, BL) if b]
        ey1 = [b[3] for b in (TL, TR) if b]
        ex2 = [b[0] for b in (TR, BR) if b]
        ey2 = [b[1] for b in (BL, BR) if b]
    nx1 = int(round(sum(ex1) / len(ex1))) if ex1 else px1
    ny1 = int(round(sum(ey1) / len(ey1))) if ey1 else py1
    nx2 = int(round(sum(ex2) / len(ex2))) if ex2 else px2
    ny2 = int(round(sum(ey2) / len(ey2))) if ey2 else py2
    nx1, ny1 = max(0, nx1), max(0, ny1)
    nx2, ny2 = min(w, nx2), min(h, ny2)
    if nx2 <= nx1 or ny2 <= ny1:
        return roi
    return (round(nx1 / w, 4), round(ny1 / h, 4), round(nx2 / w, 4), round(ny2 / h, 4))
def _find_marker_core_centers(gray, min_area=20, max_area=400, max_candidates=60):
    mask = np.where(gray < 80, 255, 0).astype(np.uint8)
    n, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    scored = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        if w <= 0 or h <= 0 or max(w, h) / max(1, min(w, h)) > 2.0:
            continue
        if area < 0.6 * w * h:
            continue
        scored.append((area, float(centroids[i][0]), float(centroids[i][1])))
    scored.sort(key=lambda t: -t[0])
    out = []
    for (_a, cx, cy) in scored[:max_candidates]:
        if not any(abs(cx - qx) < 6 and abs(cy - qy) < 6 for (qx, qy) in out):
            out.append((cx, cy))
    return out
def _anamorphic_pattern(sw, sh):
    w1x = max(2, sw // 6)
    w2x = max(w1x + 2, sw // 3)
    w1y = max(2, sh // 6)
    w2y = max(w1y + 2, sh // 3)
    pat = np.zeros((sh, sw), dtype=np.uint8)
    pat[w1y:sh - w1y, w1x:sw - w1x] = 255
    pat[w2y:sh - w2y, w2x:sw - w2x] = 0
    return pat
def _anamorphic_score(gray, cx, cy, sw, sh):
    h, w = gray.shape[:2]
    x1, y1 = int(round(cx - sw / 2)), int(round(cy - sh / 2))
    if x1 < 0 or y1 < 0 or x1 + sw > w or y1 + sh > h:
        return -1.0
    win = gray[y1:y1 + sh, x1:x1 + sw].astype(np.float32).ravel()
    pat = _anamorphic_pattern(sw, sh).astype(np.float32).ravel()
    win -= win.mean()
    pat -= pat.mean()
    denom = float(np.sqrt((win * win).sum() * (pat * pat).sum()))
    if denom <= 1e-9:
        return -1.0
    return float((win * pat).sum() / denom)
def _measure_anamorphic_size(gray, cx, cy, sizes=range(10, 37, 2)):
    best = (18, 18, -1.0)
    for sw in sizes:
        for sh in sizes:
            v = _anamorphic_score(gray, cx, cy, sw, sh)
            if v > best[2]:
                best = (sw, sh, v)
    return best
def _measure_corner_marker(gray, corner, win=56):
    h, w = gray.shape[:2]
    win = max(24, min(win, w // 2, h // 2))
    if corner == 'tl':
        patch, ox, oy = gray[0:win, 0:win], 0, 0
        touch = lambda x, y, bw, bh: x <= 2 and y <= 2
        anchor = lambda sw, sh: (ox, oy, ox + sw, oy + sh)
    elif corner == 'tr':
        patch, ox, oy = gray[0:win, w - win:w], w - win, 0
        touch = lambda x, y, bw, bh: x + bw >= win - 1 - 2 and y <= 2
        anchor = lambda sw, sh: (ox + win - sw, oy, ox + win, oy + sh)
    elif corner == 'bl':
        patch, ox, oy = gray[h - win:h, 0:win], 0, h - win
        touch = lambda x, y, bw, bh: x <= 2 and y + bh >= win - 1 - 2
        anchor = lambda sw, sh: (ox, oy + win - sh, ox + sw, oy + win)
    else:
        patch, ox, oy = gray[h - win:h, w - win:w], w - win, h - win
        touch = lambda x, y, bw, bh: x + bw >= win - 1 - 2 and y + bh >= win - 1 - 2
        anchor = lambda sw, sh: (ox + win - sw, oy + win - sh, ox + win, oy + win)
    dark = (patch < 100).astype(np.uint8) * 255
    n, _labels, stats, _cent = cv2.connectedComponentsWithStats(dark, 8)
    best, best_area = None, 0
    for i in range(1, n):
        x, y = int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP])
        bw, bh = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        area = int(stats[i, cv2.CC_STAT_AREA])
        if bw < 8 or bh < 8 or bw > win or bh > win:
            continue
        if area < 0.30 * bw * bh or area <= best_area:
            continue
        if not touch(x, y, bw, bh):
            continue
        best, best_area = (x, y, bw, bh), area
    if best is None:
        return None
    _x, _y, bw0, bh0 = best
    top = None
    for sw in range(max(8, bw0 - 3), min(win, bw0 + 3) + 1):
        for sh in range(max(8, bh0 - 3), min(win, bh0 + 3) + 1):
            ax1, ay1, ax2, ay2 = anchor(sw, sh)
            cx, cy = (ax1 + ax2) / 2.0, (ay1 + ay2) / 2.0
            v = _anamorphic_score(gray, cx, cy, sw, sh)
            if top is None or v > top[0]:
                top = (v, ax1, ay1, ax2, ay2)
    if top is None or top[0] < 0.50:
        return None
    return (top[1], top[2], top[3], top[4], top[0])
def _detect_corner_anchored_roi(img, placement='outside'):
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape[:2]
    if h < 32 or w < 32:
        return []
    boxes = {}
    for corner in ('tl', 'tr', 'bl', 'br'):
        m = _measure_corner_marker(gray, corner)
        if m is None:
            return []
        boxes[corner] = m
    if placement == 'inside':
        nx1 = min(boxes['tl'][0], boxes['bl'][0])
        ny1 = min(boxes['tl'][1], boxes['tr'][1])
        nx2 = max(boxes['tr'][2], boxes['br'][2])
        ny2 = max(boxes['bl'][3], boxes['br'][3])
    else:
        nx1 = max(boxes['tl'][2], boxes['bl'][2])
        ny1 = max(boxes['tl'][3], boxes['tr'][3])
        nx2 = min(boxes['tr'][0], boxes['br'][0])
        ny2 = min(boxes['bl'][1], boxes['br'][1])
    nx1, ny1 = max(0, nx1), max(0, ny1)
    nx2, ny2 = min(w, nx2), min(h, ny2)
    if nx2 <= nx1 + 10 or ny2 <= ny1 + 10:
        return []
    return [(round(nx1 / w, 4), round(ny1 / h, 4), round(nx2 / w, 4), round(ny2 / h, 4))]
def _detect_anamorphic_roi(img, placement='outside', min_score=0.50):
    corner = _detect_corner_anchored_roi(img, placement)
    if corner:
        return corner
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape[:2]
    if h < 32 or w < 32:
        return []
    centers = _find_marker_core_centers(gray)
    if len(centers) < 4:
        return []
    measured = []
    for (cx, cy) in centers:
        sw, sh, v = _measure_anamorphic_size(gray, cx, cy)
        if v >= min_score:
            measured.append((cx, cy, sw, sh, v))
    if len(measured) < 4:
        return []
    by_y = sorted(measured, key=lambda t: t[1])
    top = sorted(by_y[:2], key=lambda t: t[0])
    bot = sorted(by_y[-2:], key=lambda t: t[0])
    (tlx, tly, tlsw, tlsh) = (top[0][0], top[0][1], top[0][2], top[0][3])
    (trx, try_, trsw, trsh) = (top[1][0], top[1][1], top[1][2], top[1][3])
    (blx, bly, blsw, blsh) = (bot[0][0], bot[0][1], bot[0][2], bot[0][3])
    (brx, bry, brsw, brsh) = (bot[1][0], bot[1][1], bot[1][2], bot[1][3])
    tol = 12
    if abs(tly - try_) > tol or abs(bly - bry) > tol:
        return []
    if abs(tlx - blx) > tol or abs(trx - brx) > tol:
        return []
    if trx <= tlx + 30 or bry <= tly + 30:
        return []
    import statistics
    sw = int(round(statistics.median([tlsw, trsw, blsw, brsw])))
    sh = int(round(statistics.median([tlsh, trsh, blsh, brsh])))
    if placement == 'inside':
        nx1 = min(tlx - sw / 2, blx - sw / 2)
        ny1 = min(tly - sh / 2, try_ - sh / 2)
        nx2 = max(trx + sw / 2, brx + sw / 2)
        ny2 = max(bly + sh / 2, bry + sh / 2)
    else:
        nx1 = max(tlx + sw / 2, blx + sw / 2)
        ny1 = max(tly + sh / 2, try_ + sh / 2)
        nx2 = min(trx - sw / 2, brx - sw / 2)
        ny2 = min(bly - sh / 2, bry - sh / 2)
    nx1, ny1 = max(0, int(round(nx1))), max(0, int(round(ny1)))
    nx2, ny2 = min(w, int(round(nx2))), min(h, int(round(ny2)))
    if nx2 - nx1 < 2 * sw or ny2 - ny1 < 2 * sh:
        return []
    verify = []
    for (cx, cy) in ((tlx, tly), (trx, try_), (blx, bly), (brx, bry)):
        verify.append(_anamorphic_score(gray, cx, cy, sw, sh))
    if sum(1 for v in verify if v >= 0.45) < 3:
        return []
    return [(round(nx1 / w, 4), round(ny1 / h, 4), round(nx2 / w, 4), round(ny2 / h, 4))]
def detect_all_optical_markers(img, placement='outside'):
    if img is None:
        return []
    h, w = img.shape[:2]
    if h < 32 or w < 32:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    all_rois = []
    candidates = []                 
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
                        candidates.append((r, m_size))
    if not candidates:
        try:
            return _detect_anamorphic_roi(img, placement=placement)
        except Exception:
            return []
    scored = []
    for (r, m) in candidates:
        boxes = _calculate_marker_boxes(w, h, r[0], r[1], r[2], r[3], placement, m)
        scores = _marker_match_scores(img, boxes, m)
        scored.append(((sum(1 for v in scores if v >= 0.65), sum(scores)), r, m))
    scored.sort(key=lambda t: t[0], reverse=True)
    refined_rois = []
    for (_key, r, m) in scored:
        try:
            rr = refine_roi_from_centers(img, r, placement, m)
        except Exception:
            rr = r
        if not any(
            abs(rr[0] - ex[0]) < 0.03 and abs(rr[1] - ex[1]) < 0.03 and
            abs(rr[2] - ex[2]) < 0.03 and abs(rr[3] - ex[3]) < 0.03
            for ex in refined_rois
        ):
            refined_rois.append(rr)
    return refined_rois
def detect_optical_markers(img, placement='outside'):
    rois = detect_all_optical_markers(img, placement=placement)
    return rois[0] if rois else None
