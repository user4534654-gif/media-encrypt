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
