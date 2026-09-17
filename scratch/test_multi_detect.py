import cv2
import numpy as np
from core.crypto import stamp_optical_markers, create_marker_pattern
def group_markers_into_rois(clustered_pts, m_size, w, h, placement='outside'):
    if len(clustered_pts) < 4:
        return []
    pts = sorted(clustered_pts, key=lambda p: (p[1], p[0]))
    tol = max(4, m_size // 3)
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
            if tr[0] <= tl[0] + m_size:
                continue
            if abs(tr[1] - tl[1]) > tol:
                continue
            for k in range(i + 1, n):
                if k in used_pts or k == j:
                    continue
                bl = pts[k]
                if bl[1] <= tl[1] + m_size:
                    continue
                if abs(bl[0] - tl[0]) > tol:
                    continue
                for l in range(i + 1, n):
                    if l in used_pts or l == j or l == k:
                        continue
                    br = pts[l]
                    if abs(br[0] - tr[0]) <= tol and abs(br[1] - bl[1]) <= tol:
                        if placement == 'inside':
                            rx1 = max(0, tl[0])
                            ry1 = max(0, tl[1])
                            rx2 = min(w, tr[0] + m_size)
                            ry2 = min(h, bl[1] + m_size)
                        else:
                            rx1 = max(0, tl[0] + m_size)
                            ry1 = max(0, tl[1] + m_size)
                            rx2 = min(w, tr[0])
                            ry2 = min(h, bl[1])
                        if rx2 > rx1 and ry2 > ry1:
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
    if not detected_rois and len(clustered_pts) == 4:
        xs = [c[0] for c in clustered_pts]
        ys = [c[1] for c in clustered_pts]
        if placement == 'inside':
            rx1 = max(0, min(xs))
            ry1 = max(0, min(ys))
            rx2 = min(w, max(xs) + m_size)
            ry2 = min(h, max(ys) + m_size)
        else:
            rx1 = max(0, min(xs) + m_size)
            ry1 = max(0, min(ys) + m_size)
            rx2 = min(w, max(xs))
            ry2 = min(h, max(ys))
        if rx2 > rx1 and ry2 > ry1:
            detected_rois.append((
                round(rx1 / w, 4),
                round(ry1 / h, 4),
                round(rx2 / w, 4),
                round(ry2 / h, 4)
            ))
    return detected_rois
def detect_all_optical_markers(img, placement='outside'):
    if img is None:
        return []
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    all_rois = []
    for m_size in [18, 24, 16, 32]:
        pattern = create_marker_pattern(m_size)
        pat_gray = cv2.cvtColor(pattern, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(gray, pat_gray, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= 0.80)
        pts = list(zip(*loc[::-1]))
        if len(pts) >= 4:
            clustered = []
            for (px, py) in pts:
                if not any(abs(px - cx) < m_size // 2 and abs(py - cy) < m_size // 2 for (cx, cy) in clustered):
                    clustered.append((int(px), int(py)))
            rois = group_markers_into_rois(clustered, m_size, w, h, placement=placement)
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
w, h = 640, 480
img = np.zeros((h, w, 3), dtype=np.uint8)
img, _ = stamp_optical_markers(img, 50, 50, 200, 200, placement='outside')
img, _ = stamp_optical_markers(img, 300, 250, 550, 400, placement='outside')
rois = detect_all_optical_markers(img, placement='outside')
print("Detected ROIs:", rois)
expected1 = (round(50/w, 4), round(50/h, 4), round(200/w, 4), round(200/h, 4))
expected2 = (round(300/w, 4), round(250/h, 4), round(550/w, 4), round(400/h, 4))
print("Expected 1:", expected1)
print("Expected 2:", expected2)
assert len(rois) == 2, f"Expected 2 rois, got {len(rois)}"
print("ALL TESTS PASSED!")
