from core.grid_utils import get_blocks, get_outer_blocks, find_best_grid, center_inner_grid
from core.crypto import seeded_shuffle
import os
_ZONE_COLOR = "green"
_MARKER_FILL = "black"
_MARKER_STROKE = "white"
def _fmt_roi(roi):
    try:
        return "[%s]" % (", ".join(f"{float(v):.3f}" for v in list(roi)[:4]))
    except Exception:
        return "[?]"
def export_grid_to_svg(output_svg_path, w, h, cols, rows, has_center=False, center_size='1/4'):
    svg_lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">',
        '  <!-- Background -->',
        f'  <rect width="{w}" height="{h}" fill="none" />'
    ]
    if has_center:
        outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, w, h, center_size=center_size)
        all_blocks = get_blocks(w, h, cols, rows)
        svg_lines.append('  <!-- Video 1 (Outer Background) - Blue -->')
        for idx in outer_indices:
            x1, y1, x2, y2 = all_blocks[idx]
            bw = x2 - x1
            bh = y2 - y1
            svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" fill="none" stroke="blue" stroke-width="1.5" />')
        cw = cx2 - cx1
        ch = cy2 - cy1
        cols_inner, rows_inner = center_inner_grid(cols, rows, center_size)
        center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
        svg_lines.append('  <!-- Video 2 (Center Overlay) - Red -->')
        svg_lines.append(f'  <rect x="{cx1}" y="{cy1}" width="{cw}" height="{ch}" fill="none" stroke="red" stroke-width="3" />')
        for x1, y1, x2, y2 in center_blocks:
            bx1 = cx1 + x1
            by1 = cy1 + y1
            bw = x2 - x1
            bh = y2 - y1
            svg_lines.append(f'  <rect x="{bx1}" y="{by1}" width="{bw}" height="{bh}" fill="none" stroke="red" stroke-width="1.5" />')
    else:
        all_blocks = get_blocks(w, h, cols, rows)
        svg_lines.append('  <!-- Video 1 (Full Frame Scramble) - Red -->')
        for x1, y1, x2, y2 in all_blocks:
            bw = x2 - x1
            bh = y2 - y1
            svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" fill="none" stroke="red" stroke-width="1.5" />')
    svg_lines.append('</svg>')
    with open(output_svg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))
def export_scrambled_grid_to_svg(output_svg_path, w, h, cols, rows, seed, has_center=False, center_size='1/4', prefix_original=False):
    stroke_color = "red" if not has_center else "black"
    svg_lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">',
        '  <!-- Background -->',
        f'  <rect width="{w}" height="{h}" fill="white" stroke="black" stroke-width="2" />'
    ]
    all_blocks = get_blocks(w, h, cols, rows)
    n_blocks = len(all_blocks)
    if has_center:
        outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, w, h, center_size=center_size)
        N_outer = len(outer_indices)
        C1, R1 = find_best_grid(N_outer, target_ratio=cols/rows)
        src_blocks_outer = get_blocks(w, h, C1, R1)
        shuffled_outer = seeded_shuffle(list(outer_indices), seed)
        cw = cx2 - cx1
        ch = cy2 - cy1
        cols_inner, rows_inner = center_inner_grid(cols, rows, center_size)
        center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
        shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)
        for j in range(N_outer):
            orig_idx = outer_indices[j]
            if prefix_original:
                x1, y1, x2, y2 = src_blocks_outer[j]
                num = orig_idx + 1
                color = "blue"
            else:
                dest_idx = shuffled_outer[j]
                x1, y1, x2, y2 = all_blocks[dest_idx]
                num = orig_idx + 1
                color = "blue"
            bw = x2 - x1
            bh = y2 - y1
            cx = x1 + bw / 2
            cy = y1 + bh / 2
            font_size = min(bw, bh) * 0.4
            svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" fill="none" stroke="{color}" stroke-width="1.5" />')
            svg_lines.append(f'  <text x="{cx}" y="{cy}" font-family="Arial" font-size="{font_size:.1f}" fill="{color}" text-anchor="middle" dominant-baseline="central">{num}</text>')
        svg_lines.append(f'  <!-- Center Bounding Box -->')
        svg_lines.append(f'  <rect x="{cx1}" y="{cy1}" width="{cw}" height="{ch}" fill="none" stroke="red" stroke-width="3" />')
        for i in range(cols_inner * rows_inner):
            if prefix_original:
                x1, y1, x2, y2 = center_blocks[i]
                bx1 = cx1 + x1
                by1 = cy1 + y1
                num = i + 1
                color = "red"
            else:
                t_idx = shuffled_center[i]
                x1, y1, x2, y2 = center_blocks[i]
                bx1 = cx1 + x1
                by1 = cy1 + y1
                num = t_idx + 1
                color = "red"
            bw = x2 - x1
            bh = y2 - y1
            cx = bx1 + bw / 2
            cy = by1 + bh / 2
            font_size = min(bw, bh) * 0.4
            svg_lines.append(f'  <rect x="{bx1}" y="{by1}" width="{bw}" height="{bh}" fill="none" stroke="{color}" stroke-width="1.5" />')
            svg_lines.append(f'  <text x="{cx}" y="{cy}" font-family="Arial" font-size="{font_size:.1f}" fill="{color}" text-anchor="middle" dominant-baseline="central">{num}</text>')
    else:
        shuffled = seeded_shuffle(list(range(n_blocks)), seed)
        for i in range(n_blocks):
            x1, y1, x2, y2 = all_blocks[i]
            bw = x2 - x1
            bh = y2 - y1
            cx = x1 + bw / 2
            cy = y1 + bh / 2
            font_size = min(bw, bh) * 0.4
            if prefix_original:
                num = i + 1
            else:
                num = shuffled[i] + 1
            svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" fill="none" stroke="black" stroke-width="1.5" />')
            svg_lines.append(f'  <text x="{cx}" y="{cy}" font-family="Arial" font-size="{font_size:.1f}" fill="black" text-anchor="middle" dominant-baseline="central">{num}</text>')
    svg_lines.append('</svg>')
    with open(output_svg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))
def _zone_svg_head(w, h, roi, caption):
    return [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">',
        '  <!-- Background -->',
        f'  <rect width="{w}" height="{h}" fill="white" stroke="black" stroke-width="2" />',
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
def _zone_svg_block(svg_lines, x1, y1, x2, y2, num, color):
    bw = x2 - x1
    bh = y2 - y1
    cx = x1 + bw / 2
    cy = y1 + bh / 2
    font_size = min(bw, bh) * 0.4
    svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" fill="none" stroke="{color}" stroke-width="1.5" />')
    if num is not None:
        svg_lines.append(f'  <text x="{cx}" y="{cy}" font-family="Arial" font-size="{font_size:.1f}" fill="{color}" text-anchor="middle" dominant-baseline="central">{num}</text>')
def export_zone_to_svg(output_svg_path, w, h, roi, blocks, marker_boxes=None, caption=""):
    svg_lines = _zone_svg_head(w, h, roi, caption)
    _zone_svg_roi(svg_lines, roi, w, h)
    for (x1, y1, x2, y2) in (blocks or []):
        _zone_svg_block(svg_lines, x1, y1, x2, y2, None, _ZONE_COLOR)
    _zone_svg_markers(svg_lines, marker_boxes)
    svg_lines.append('</svg>')
    with open(output_svg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))
def export_scrambled_zone_to_svg(output_svg_path, w, h, roi, blocks, seed,
                                 marker_boxes=None, prefix_original=False, caption=""):
    n = len(blocks or [])
    shuffled = seeded_shuffle(list(range(n)), seed) if n else []
    svg_lines = _zone_svg_head(w, h, roi, f"{caption} seed={seed}".strip())
    _zone_svg_roi(svg_lines, roi, w, h)
    for i, (x1, y1, x2, y2) in enumerate(blocks or []):
        num = (i + 1) if prefix_original else (shuffled[i] + 1)
        color = _ZONE_COLOR if prefix_original else "blue"
        _zone_svg_block(svg_lines, x1, y1, x2, y2, num, color)
    _zone_svg_markers(svg_lines, marker_boxes)
    svg_lines.append('</svg>')
    with open(output_svg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg_lines))
