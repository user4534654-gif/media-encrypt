from core.grid_utils import get_blocks, get_outer_blocks, find_best_grid, center_inner_grid
from core.crypto import seeded_shuffle
import base64
import os
_ZONE_COLOR = "green"
_MARKER_FILL = "black"
_MARKER_STROKE = "white"
_GRAD_MAX_SIDE = 640
_GRAD_JPEG_QUALITY = 82
_GRAD_CACHE = {}
def _grad_size(w, h):
    w, h = max(1, int(w)), max(1, int(h))
    m = max(w, h)
    if m <= _GRAD_MAX_SIDE:
        return w, h
    s = _GRAD_MAX_SIDE / m
    return max(1, int(round(w * s))), max(1, int(round(h * s)))
def _grad_data_uri(w, h):
    sw, sh = _grad_size(w, h)
    key = (sw, sh)
    uri = _GRAD_CACHE.get(key)
    if uri is not None:
        return uri, sw, sh
    import cv2
    import numpy as np
    xs = np.linspace(0, 179, sw, dtype=np.float32)
    ys = np.linspace(0, 1, sh, dtype=np.float32)
    hue = np.tile(xs, (sh, 1))
    sat = np.full((sh, sw), 255, dtype=np.float32)
    val = np.tile((255 - 105 * ys)[:, None], (1, sw)).astype(np.float32)
    hsv = np.stack([hue, sat, val], axis=-1).astype(np.uint8)
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), _GRAD_JPEG_QUALITY])
    if not ok:
        raise RuntimeError("gradient JPEG encode failed")
    uri = "data:image/jpeg;base64," + base64.b64encode(bytes(buf)).decode("ascii")
    _GRAD_CACHE[key] = uri
    return uri, sw, sh
def _svg_head(w, h, comment=""):
    lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">',
    ]
    if comment:
        lines.append(f'  <!-- {comment} -->')
    return lines
def _grad_defs(uri, sw, sh):
    return [
        '  <defs>',
        f'    <image id="pxgrad" x="0" y="0" width="{sw}" height="{sh}" '
        f'href="{uri}" xlink:href="{uri}" preserveAspectRatio="none" />',
        '  </defs>',
    ]
def _patch(lines, dx, dy, bw, bh, sx, sy, sw, sh):
    lines.append(
        f'  <svg x="{dx}" y="{dy}" width="{bw}" height="{bh}" '
        f'viewBox="{sx:.2f} {sy:.2f} {sw:.2f} {sh:.2f}" preserveAspectRatio="none">'
        '<use href="#pxgrad" xlink:href="#pxgrad" /></svg>'
    )
def _outline(lines, x1, y1, bw, bh, stroke, stroke_w="1.5"):
    lines.append(
        f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" '
        f'fill="none" stroke="{stroke}" stroke-width="{stroke_w}" />'
    )
def _number(lines, cx, cy, font_size, color, num):
    lines.append(
        f'  <text x="{cx}" y="{cy}" font-family="Arial" font-size="{font_size:.1f}" '
        f'fill="{color}" stroke="white" stroke-width="{max(0.5, font_size / 8.0):.1f}" '
        f'paint-order="stroke" text-anchor="middle" dominant-baseline="central">{num}</text>'
    )
def _frame_to_grad(x, y, w, h, sw, sh):
    return x / w * sw, y / h * sh
def _block_patch(lines, dx1, dy1, dx2, dy2, sx1, sy1, sx2, sy2, w, h, sw, sh):
    bw, bh = dx2 - dx1, dy2 - dy1
    if bw <= 0 or bh <= 0:
        return
    gx, gy = _frame_to_grad(sx1, sy1, w, h, sw, sh)
    gx2, gy2 = _frame_to_grad(sx2, sy2, w, h, sw, sh)
    _patch(lines, dx1, dy1, bw, bh, gx, gy, max(0.01, gx2 - gx), max(0.01, gy2 - gy))
def _write(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines + ['</svg>']))
def _fmt_roi(roi):
    try:
        return "[%s]" % (", ".join(f"{float(v):.3f}" for v in list(roi)[:4]))
    except Exception:
        return "[?]"
def export_grid_to_svg(output_svg_path, w, h, cols, rows, has_center=False, center_size='1/4'):
    uri, sw, sh = _grad_data_uri(w, h)
    svg_lines = _svg_head(w, h, "pixel-gradient debug backdrop (own pixels per cell)")
    svg_lines += _grad_defs(uri, sw, sh)
    if has_center:
        outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, w, h, center_size=center_size)
        all_blocks = get_blocks(w, h, cols, rows)
        svg_lines.append('  <!-- Video 1 (Outer Background) - Blue -->')
        for idx in outer_indices:
            x1, y1, x2, y2 = all_blocks[idx]
            _block_patch(svg_lines, x1, y1, x2, y2, x1, y1, x2, y2, w, h, sw, sh)
        for idx in outer_indices:
            x1, y1, x2, y2 = all_blocks[idx]
            _outline(svg_lines, x1, y1, x2 - x1, y2 - y1, "blue")
        cw, ch = cx2 - cx1, cy2 - cy1
        cols_inner, rows_inner = center_inner_grid(cols, rows, center_size)
        center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
        svg_lines.append('  <!-- Video 2 (Center Overlay) - Red -->')
        for (x1, y1, x2, y2) in center_blocks:
            _block_patch(svg_lines, cx1 + x1, cy1 + y1, cx1 + x2, cy1 + y2,
                         cx1 + x1, cy1 + y1, cx1 + x2, cy1 + y2, w, h, sw, sh)
        svg_lines.append(f'  <rect x="{cx1}" y="{cy1}" width="{cw}" height="{ch}" fill="none" stroke="red" stroke-width="3" />')
        for (x1, y1, x2, y2) in center_blocks:
            _outline(svg_lines, cx1 + x1, cy1 + y1, x2 - x1, y2 - y1, "red")
    else:
        all_blocks = get_blocks(w, h, cols, rows)
        svg_lines.append('  <!-- Video 1 (Full Frame) - Red -->')
        for (x1, y1, x2, y2) in all_blocks:
            _block_patch(svg_lines, x1, y1, x2, y2, x1, y1, x2, y2, w, h, sw, sh)
        for (x1, y1, x2, y2) in all_blocks:
            _outline(svg_lines, x1, y1, x2 - x1, y2 - y1, "red")
    _write(output_svg_path, svg_lines)
def export_scrambled_grid_to_svg(output_svg_path, w, h, cols, rows, seed, has_center=False, center_size='1/4', prefix_original=False):
    uri, sw, sh = _grad_data_uri(w, h)
    svg_lines = _svg_head(w, h, f"pixel-gradient scrambled seed={seed} original={prefix_original}")
    svg_lines += _grad_defs(uri, sw, sh)
    svg_lines.append(f'  <rect width="{w}" height="{h}" fill="white" stroke="black" stroke-width="2" />')
    all_blocks = get_blocks(w, h, cols, rows)
    n_blocks = len(all_blocks)
    if has_center:
        outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, w, h, center_size=center_size)
        N_outer = len(outer_indices)
        C1, R1 = find_best_grid(N_outer, target_ratio=cols / rows)
        src_blocks_outer = get_blocks(w, h, C1, R1)
        shuffled_outer = seeded_shuffle(list(outer_indices), seed)
        cw, ch = cx2 - cx1, cy2 - cy1
        cols_inner, rows_inner = center_inner_grid(cols, rows, center_size)
        center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
        shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)
        cells = []                          
        for j in range(N_outer):
            orig_idx = outer_indices[j]
            if prefix_original:
                x1, y1, x2, y2 = src_blocks_outer[j]
                num = orig_idx + 1
                sx1, sy1, sx2, sy2 = all_blocks[orig_idx]
            else:
                dest_idx = shuffled_outer[j]
                x1, y1, x2, y2 = all_blocks[dest_idx]
                num = orig_idx + 1
                sx1, sy1, sx2, sy2 = all_blocks[orig_idx]
            _block_patch(svg_lines, x1, y1, x2, y2, sx1, sy1, sx2, sy2, w, h, sw, sh)
            cells.append((x1, y1, x2, y2, num))
        for (x1, y1, x2, y2, num) in cells:
            bw, bh = x2 - x1, y2 - y1
            _outline(svg_lines, x1, y1, bw, bh, "blue")
            _number(svg_lines, x1 + bw / 2, y1 + bh / 2, min(bw, bh) * 0.4, "blue", num)
        svg_lines.append('  <!-- Center Bounding Box -->')
        svg_lines.append(f'  <rect x="{cx1}" y="{cy1}" width="{cw}" height="{ch}" fill="none" stroke="red" stroke-width="3" />')
        ccells = []
        for i in range(cols_inner * rows_inner):
            x1, y1, x2, y2 = center_blocks[i]
            bx1, by1, bx2, by2 = cx1 + x1, cy1 + y1, cx1 + x2, cy1 + y2
            src = i if prefix_original else shuffled_center[i]
            sx1, sy1, sx2, sy2 = center_blocks[src]
            _block_patch(svg_lines, bx1, by1, bx2, by2,
                         cx1 + sx1, cy1 + sy1, cx1 + sx2, cy1 + sy2, w, h, sw, sh)
            ccells.append((bx1, by1, bx2, by2, src + 1))
        for (bx1, by1, bx2, by2, num) in ccells:
            bw, bh = bx2 - bx1, by2 - by1
            _outline(svg_lines, bx1, by1, bw, bh, "red")
            _number(svg_lines, bx1 + bw / 2, by1 + bh / 2, min(bw, bh) * 0.4, "red", num)
    else:
        shuffled = seeded_shuffle(list(range(n_blocks)), seed)
        cells = []
        for i in range(n_blocks):
            x1, y1, x2, y2 = all_blocks[i]
            src = i if prefix_original else shuffled[i]
            sx1, sy1, sx2, sy2 = all_blocks[src]
            _block_patch(svg_lines, x1, y1, x2, y2, sx1, sy1, sx2, sy2, w, h, sw, sh)
            cells.append((x1, y1, x2, y2, src + 1))
        for (x1, y1, x2, y2, num) in cells:
            bw, bh = x2 - x1, y2 - y1
            _outline(svg_lines, x1, y1, bw, bh, "black")
            _number(svg_lines, x1 + bw / 2, y1 + bh / 2, min(bw, bh) * 0.4, "black", num)
    _write(output_svg_path, svg_lines)
def _zone_svg_head(w, h, roi, caption):
    return [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">',
        f'  <!-- Encrypt zone roi={_fmt_roi(roi)} {caption} -->',
    ]
def _zone_svg_roi(svg_lines, roi, w, h):
    try:
        rx1, ry1, rx2, ry2 = list(roi)[:4]
        if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
            px1, py1, px2, py2 = rx1 * w, ry1 * h, rx2 * w, ry2 * h
        else:
            px1, py1, px2, py2 = float(rx1), float(ry1), float(rx2), float(ry2)
    except Exception:
        return
    svg_lines.append(f'  <rect x="{px1:.1f}" y="{py1:.1f}" width="{max(0.0, px2 - px1):.1f}" height="{max(0.0, py2 - py1):.1f}" fill="none" stroke="{_ZONE_COLOR}" stroke-width="3" />')
def _zone_svg_markers(svg_lines, marker_boxes):
    if not marker_boxes:
        return
    svg_lines.append('  <!-- Optical markers (black) -->')
    for box in marker_boxes:
        try:
            x1, y1, x2, y2 = box
        except Exception:
            continue
        svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{max(0, x2 - x1)}" height="{max(0, y2 - y1)}" fill="{_MARKER_FILL}" stroke="{_MARKER_STROKE}" stroke-width="1" />')
def _zone_svg_block(svg_lines, x1, y1, x2, y2, num, color, grad, w, h, sw, sh, src_box=None):
    bw, bh = x2 - x1, y2 - y1
    sx1, sy1, sx2, sy2 = src_box if src_box is not None else (x1, y1, x2, y2)
    if grad:
        _block_patch(svg_lines, x1, y1, x2, y2, sx1, sy1, sx2, sy2, w, h, sw, sh)
    _outline(svg_lines, x1, y1, bw, bh, color)
    if num is not None:
        _number(svg_lines, x1 + bw / 2, y1 + bh / 2, min(bw, bh) * 0.4, color, num)
def export_zone_to_svg(output_svg_path, w, h, roi, blocks, marker_boxes=None, caption=""):
    uri, sw, sh = _grad_data_uri(w, h)
    svg_lines = _zone_svg_head(w, h, roi, caption)
    svg_lines += _grad_defs(uri, sw, sh)
    _zone_svg_roi(svg_lines, roi, w, h)
    for (x1, y1, x2, y2) in (blocks or []):
        _zone_svg_block(svg_lines, x1, y1, x2, y2, None, _ZONE_COLOR, True, w, h, sw, sh)
    _zone_svg_markers(svg_lines, marker_boxes)
    _write(output_svg_path, svg_lines)
def export_scrambled_zone_to_svg(output_svg_path, w, h, roi, blocks, seed,
                                 marker_boxes=None, prefix_original=False, caption=""):
    n = len(blocks or [])
    shuffled = seeded_shuffle(list(range(n)), seed) if n else []
    uri, sw, sh = _grad_data_uri(w, h)
    svg_lines = _zone_svg_head(w, h, roi, f"{caption} seed={seed}".strip())
    svg_lines += _grad_defs(uri, sw, sh)
    _zone_svg_roi(svg_lines, roi, w, h)
    cells = []
    for i, (x1, y1, x2, y2) in enumerate(blocks or []):
        if prefix_original:
            num, src, color = i + 1, i, _ZONE_COLOR
        else:
            num, src, color = shuffled[i] + 1, shuffled[i], "blue"
        _zone_svg_block(svg_lines, x1, y1, x2, y2, None, color, True, w, h, sw, sh,
                        src_box=tuple((blocks or [])[src]))
        cells.append((x1, y1, x2, y2, num, color))
    for (x1, y1, x2, y2, num, color) in cells:
        bw, bh = x2 - x1, y2 - y1
        _number(svg_lines, x1 + bw / 2, y1 + bh / 2, min(bw, bh) * 0.4, color, num)
    _zone_svg_markers(svg_lines, marker_boxes)
    _write(output_svg_path, svg_lines)
