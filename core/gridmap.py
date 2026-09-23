
import json
import hashlib
import cv2
import numpy as np
from core.crypto import seeded_shuffle
from core.grid_utils import (
    get_blocks,
    get_outer_blocks,
    find_best_grid,
    center_inner_grid,
)
GRIDMAP_FORMAT = "media-encrypt-gridmap/1"
def build_gridmap(w, h, cols, rows, seed, has_center=False, center_size="1/4"):
    w, h, cols, rows, seed = int(w), int(h), int(cols), int(rows), int(seed)
    gm = {
        "format": GRIDMAP_FORMAT,
        "w": w, "h": h, "cols": cols, "rows": rows, "seed": seed,
        "has_center": bool(has_center), "center_size": str(center_size),
        "blocks": [list(b) for b in get_blocks(w, h, cols, rows)],
        "perm": None,
        "center": None,
    }
    n = cols * rows
    if not has_center:
        gm["perm"] = {
            "mode": "full",
            "shuffled": seeded_shuffle(list(range(n)), seed),
        }
    else:
        outer, inner, (cx1, cy1, cx2, cy2) = get_outer_blocks(
            cols, rows, w, h, center_size=center_size)
        n_outer = len(outer)
        c1, r1 = find_best_grid(n_outer, target_ratio=cols / rows)
        ci, ri = center_inner_grid(cols, rows, center_size)
        cw, ch = int(cx2 - cx1), int(cy2 - cy1)
        gm["center"] = {
            "outer": list(outer),
            "inner": list(inner),
            "bbox": [int(cx1), int(cy1), int(cx2), int(cy2)],
            "packed_grid": [int(c1), int(r1)],
            "packed_blocks": [list(b) for b in get_blocks(w, h, c1, r1)],
            "inner_grid": [int(ci), int(ri)],
            "inner_blocks": [list(b) for b in get_blocks(cw, ch, ci, ri)],
            "shuffled_outer": seeded_shuffle(list(outer), seed),
            "shuffled_center": seeded_shuffle(list(range(ci * ri)), seed),
        }
    return gm
def export_gridmap_json(path, gridmap):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(gridmap, f, indent=2, sort_keys=True)
        f.write("\n")
    return path
def load_gridmap_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
def _scale_text(min_side):
    scale = max(0.4, min(2.0, min_side / 40.0))
    thick = 1 if min_side < 40 else 2
    return scale, thick
def export_gridmap_png(path, gridmap):
    w, h = gridmap["w"], gridmap["h"]
    img = np.zeros((h, w, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    def label(x1, y1, x2, y2, num, color):
        bw, bh = x2 - x1, y2 - y1
        if bw <= 0 or bh <= 0:
            return
        cv2.rectangle(img, (x1, y1), (x2 - 1, y2 - 1), color, 1)
        ms = min(bw, bh)
        if ms >= 12:
            scale, thick = _scale_text(ms)
            txt = str(num)
            (tw, th), _ = cv2.getTextSize(txt, font, scale, thick)
            tx = x1 + max(0, (bw - tw) // 2)
            ty = y1 + max(0, (bh + th) // 2)
            cv2.putText(img, txt, (tx, ty), font, scale, color, thick,
                        cv2.LINE_8)
    blocks = gridmap["blocks"]
    if not gridmap["has_center"]:
        shuffled = gridmap["perm"]["shuffled"]
        for i, (x1, y1, x2, y2) in enumerate(blocks):
            label(x1, y1, x2, y2, shuffled[i] + 1, (0, 0, 255))
    else:
        c = gridmap["center"]
        pos_of = {dest: j for j, dest in enumerate(c["shuffled_outer"])}
        for j, dest in enumerate(c["outer"]):
            x1, y1, x2, y2 = blocks[dest]
            label(x1, y1, x2, y2, dest + 1, (255, 0, 0))
        x1, y1, x2, y2 = c["bbox"]
        if x2 > x1 and y2 > y1:
            cv2.rectangle(img, (x1, y1), (x2 - 1, y2 - 1), (0, 0, 255), 2)
        inner_blocks = c["inner_blocks"]
        shuffled_c = c["shuffled_center"]
        for i, (bx1, by1, bx2, by2) in enumerate(inner_blocks):
            label(x1 + bx1, y1 + by1, x1 + bx2, y1 + by2,
                  shuffled_c[i] + 1, (0, 0, 255))
        _ = pos_of
    cv2.imwrite(path, img)
    return path
def gridmap_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()
