# ── Center overlay size handling ──────────────────────────────────────────
# The center overlay size is a slider value N in [1, 3] ("N/4 of the frame
# area"; the UI also accepts the legacy '1/4', '2/4', '3/4' labels). The
# linear block-grid scale is s = sqrt(N/4), so N = 1, 2, 3 give exactly the
# historical 0.5 / 0.7071 / 0.866 factors (kept bit-for-bit identical).
CENTER_SCALE_LEGACY = {'1/4': 0.5, '2/4': 0.7071, '3/4': 0.866}

def normalize_center_value(value):
    """Normalize any center-size representation to slider units N in [1, 3].

    Accepts legacy labels ('1/4', '2/4', '3/4'), plain numbers (1.44),
    'N/4' strings ('1.44/4'), and int/float values. Out-of-range input is
    clamped so geometry can never degenerate.
    """
    if value is None:
        return 1.0
    if isinstance(value, (int, float)):
        n = float(value)
    else:
        s = str(value).strip()
        if '/' in s:
            try:
                a, b = s.split('/', 1)
                n = float(a) / float(b) * 4.0
            except (ValueError, ZeroDivisionError):
                n = 1.0
        else:
            try:
                n = float(s)
            except ValueError:
                n = 1.0
    if n != n:  # NaN guard
        n = 1.0
    return max(0.25, min(3.99, n))

def center_size_to_scale(center_size):
    """Linear grid scale s for a center size (legacy-exact for 1, 2, 3)."""
    if isinstance(center_size, str) and center_size.strip() in CENTER_SCALE_LEGACY:
        return CENTER_SCALE_LEGACY[center_size.strip()]
    n = normalize_center_value(center_size)
    if abs(n - 1.0) < 1e-9:
        return 0.5
    if abs(n - 2.0) < 1e-9:
        return 0.7071
    if abs(n - 3.0) < 1e-9:
        return 0.866
    import math
    return math.sqrt(max(0.0625, min(0.999, n / 4.0)))

def format_center_key(center_size):
    """Canonical key fragment for a center size ('|c', '|c_2/4', '|c_1.44')."""
    n = normalize_center_value(center_size)
    if abs(n - 1.0) < 1e-9:
        return '|c'
    if abs(n - 2.0) < 1e-9:
        return '|c_2/4'
    if abs(n - 3.0) < 1e-9:
        return '|c_3/4'
    return f"|c_{float(f'{n:.2f}'):g}"

def center_inner_grid(cols, rows, center_size):
    """(cols_inner, rows_inner) for a center size (legacy-exact for 1, 2, 3)."""
    s = center_size_to_scale(center_size)
    cols_inner = max(1, min(cols - 1, int(cols * s)))
    rows_inner = max(1, min(rows - 1, int(rows * s)))
    return cols_inner, rows_inner

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
    """
    Build a list of (x1, y1, x2, y2) block coordinates.
    Uses fractional rounding to distribute remainder pixels evenly
    across the entire width and height of the image/video.
    This guarantees:
      - Exactly cols*rows blocks
      - No large remainder blocks at the right/bottom edges
      - No gaps / no pixel bleeding
      - All coordinates are within [0, w) x [0, h)
    """
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
    cols_inner, rows_inner = center_inner_grid(cols, rows, center_size)
    
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
    """
    Returns blocks to shuffle for a specific ROI (rx1, ry1, rx2, ry2).
    Coordinates can be normalized (0.0 - 1.0) or absolute pixels.
    If invert=False:
      Returns list of (bx1, by1, bx2, by2) strictly INSIDE the ROI, partitioned into cols x rows.
    If invert=True:
      Partitions full (w, h) into cols x rows, returns blocks whose centers lie OUTSIDE the ROI.
    """
    rx1, ry1, rx2, ry2 = roi
    # Handle normalized coordinates
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
        # Generate blocks inside the ROI
        sub_blocks = get_blocks(rw, rh, cols, rows)
        roi_blocks = [(rx1 + bx1, ry1 + by1, rx1 + bx2, ry1 + by2) for (bx1, by1, bx2, by2) in sub_blocks]
        return roi_blocks
    else:
        # Full frame partitioned into cols x rows, select blocks outside the ROI
        all_blocks = get_blocks(w, h, cols, rows)
        outer_blocks = []
        for (bx1, by1, bx2, by2) in all_blocks:
            cx = (bx1 + bx2) // 2
            cy = (by1 + by2) // 2
            # If block center is outside ROI, include it in shuffle
            if not (rx1 <= cx < rx2 and ry1 <= cy < ry2):
                outer_blocks.append((bx1, by1, bx2, by2))
        return outer_blocks

