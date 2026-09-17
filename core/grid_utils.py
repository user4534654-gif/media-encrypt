def find_best_grid(n, target_ratio=1.0):
    best_c, best_r = 1, n
    min_diff = float('inf')
    for i in range(1, int(n**0.5) + 1):
        if n % i == 0:
            r = i
            c = n // i
            ratio = c / r
            diff = abs(ratio - target_ratio)
            if diff < min_diff:
                min_diff = diff
                best_c, best_r = c, r
            ratio2 = r / c
            diff2 = abs(ratio2 - target_ratio)
            if diff2 < min_diff:
                min_diff = diff2
                best_c, best_r = r, c
    return best_c, best_r
def get_blocks(w, h, cols, rows):
    blocks = []
    for r in range(rows):
        y1 = int(round(r * h / rows))
        y2 = int(round((r + 1) * h / rows))
        for c in range(cols):
            x1 = int(round(c * w / cols))
            x2 = int(round((c + 1) * w / cols))
            blocks.append((x1, y1, x2, y2))
    return blocks
def get_outer_blocks(cols, rows, out_w, out_h, center_size='1/4'):
    if center_size == '2/4':
        s = 0.7071
    elif center_size == '3/4':
        s = 0.866
    else:
        s = 0.5
    cols_inner = max(1, min(cols - 1, int(cols * s)))
    rows_inner = max(1, min(rows - 1, int(rows * s)))
    c_start = (cols - cols_inner) // 2
    c_end = c_start + cols_inner
    r_start = (rows - rows_inner) // 2
    r_end = r_start + rows_inner
    all_blocks = get_blocks(out_w, out_h, cols, rows)
    idx_top_left = r_start * cols + c_start
    idx_bottom_right = (r_end - 1) * cols + (c_end - 1)
    cx1 = all_blocks[idx_top_left][0]
    cy1 = all_blocks[idx_top_left][1]
    cx2 = all_blocks[idx_bottom_right][2]
    cy2 = all_blocks[idx_bottom_right][3]
    outer_indices = []
    inner_indices = []
    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if c_start <= c < c_end and r_start <= r < r_end:
                inner_indices.append(idx)
            else:
                outer_indices.append(idx)
    return outer_indices, inner_indices, (cx1, cy1, cx2, cy2)
def get_roi_blocks(w, h, roi, cols, rows, invert=False):
    rx1, ry1, rx2, ry2 = roi
    if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
        rx1 = int(round(rx1 * w))
        ry1 = int(round(ry1 * h))
        rx2 = int(round(rx2 * w))
        ry2 = int(round(ry2 * h))
    rx1 = max(0, min(w, int(rx1)))
    rx2 = max(0, min(w, int(rx2)))
    ry1 = max(0, min(h, int(ry1)))
    ry2 = max(0, min(h, int(ry2)))
    if rx1 > rx2: rx1, rx2 = rx2, rx1
    if ry1 > ry2: ry1, ry2 = ry2, ry1
    rw = max(1, rx2 - rx1)
    rh = max(1, ry2 - ry1)
    if not invert:
        sub_blocks = get_blocks(rw, rh, cols, rows)
        roi_blocks = [(rx1 + bx1, ry1 + by1, rx1 + bx2, ry1 + by2) for (bx1, by1, bx2, by2) in sub_blocks]
        return roi_blocks
    else:
        all_blocks = get_blocks(w, h, cols, rows)
        outer_blocks = []
        for (bx1, by1, bx2, by2) in all_blocks:
            cx = (bx1 + bx2) // 2
            cy = (by1 + by2) // 2
            if not (rx1 <= cx < rx2 and ry1 <= cy < ry2):
                outer_blocks.append((bx1, by1, bx2, by2))
        return outer_blocks
