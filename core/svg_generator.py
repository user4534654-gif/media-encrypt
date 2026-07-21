from core.grid_utils import get_blocks, get_outer_blocks, find_best_grid
from core.crypto import seeded_shuffle
import os

def export_grid_to_svg(output_svg_path, w, h, cols, rows, has_center=False, center_size='1/4'):
    """
    Generates an SVG file representing the exact grid used for encryption.
    If has_center is False (Normal Mode):
        Draws all grid blocks with a red stroke.
    If has_center is True (Center Mode):
        Draws outer/background blocks (Video 1) with a blue stroke.
        Draws center overlay blocks (Video 2) with a red stroke.
    """
    svg_lines = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">',
        '  <!-- Background -->',
        f'  <rect width="{w}" height="{h}" fill="none" />'
    ]

    if has_center:
        # Get outer indices and center rectangle coords
        outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, w, h, center_size=center_size)
        all_blocks = get_blocks(w, h, cols, rows)
        
        # 1. Background blocks (Video 1) - Blue
        svg_lines.append('  <!-- Video 1 (Outer Background) - Blue -->')
        for idx in outer_indices:
            x1, y1, x2, y2 = all_blocks[idx]
            bw = x2 - x1
            bh = y2 - y1
            svg_lines.append(f'  <rect x="{x1}" y="{y1}" width="{bw}" height="{bh}" fill="none" stroke="blue" stroke-width="1.5" />')
            
        # 2. Central overlay blocks (Video 2) - Red
        cw = cx2 - cx1
        ch = cy2 - cy1
        if center_size == '2/4':
            s = 0.7071
        elif center_size == '3/4':
            s = 0.866
        else:
            s = 0.5
        cols_inner = max(1, min(cols - 1, int(cols * s)))
        rows_inner = max(1, min(rows - 1, int(rows * s)))
        center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
        
        svg_lines.append('  <!-- Video 2 (Center Overlay) - Red -->')
        # Center bounding box
        svg_lines.append(f'  <rect x="{cx1}" y="{cy1}" width="{cw}" height="{ch}" fill="none" stroke="red" stroke-width="3" />')
        # Center blocks
        for x1, y1, x2, y2 in center_blocks:
            bx1 = cx1 + x1
            by1 = cy1 + y1
            bw = x2 - x1
            bh = y2 - y1
            svg_lines.append(f'  <rect x="{bx1}" y="{by1}" width="{bw}" height="{bh}" fill="none" stroke="red" stroke-width="1.5" />')
    else:
        # Normal Full Frame Scramble - Red
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
    """
    Generates an SVG file representing the grid with numbered blocks showing the scrambling sequence.
    If prefix_original is True:
        Draws the original layout with numbers 1..N.
    If prefix_original is False:
        Draws the scrambled layout where each cell shows the source block index that is placed there.
    """
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
        if center_size == '2/4':
            s = 0.7071
        elif center_size == '3/4':
            s = 0.866
        else:
            s = 0.5
        cols_inner = max(1, min(cols - 1, int(cols * s)))
        rows_inner = max(1, min(rows - 1, int(rows * s)))
        center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)
        shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)

        # 1. Background outer blocks
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

        # 2. Central blocks
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
        # Full frame scrambling
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
