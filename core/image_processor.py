import cv2
import numpy as np
import os
from core.crypto import seeded_shuffle
from core.grid_utils import find_best_grid, get_outer_blocks, get_blocks

def save_image(path, img):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.avif':
        try:
            from PIL import Image
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            pil_img.save(path)
            return
        except Exception as e:
            raise RuntimeError(f"Failed to save as AVIF: {e}. Ensure 'pillow' and a suitable writer plugin are installed.")
    cv2.imwrite(path, img)

def process_image_file(input_path, output_path, options, progress_dict, task_id):
    proc_vid = options.get('process_video')
    reverse = options.get('reverse')
    cols, rows, seed = options.get('cols', 1), options.get('rows', 1), options.get('seed', 0)
    target_w, target_h = options.get('target_w'), options.get('target_h')
    no_scale = options.get('no_scale', False)
    video_encrypt_mode = options.get('video_encrypt_mode', 'external') # 'external', 'center', 'both'

    img = cv2.imread(input_path)
    if img is None:
        from PIL import Image
        pil_img = Image.open(input_path).convert('RGB')
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    if target_w and target_h:
        if no_scale:
            canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            orig_h, orig_w = img.shape[:2]
            copy_w, copy_h = min(target_w, orig_w), min(target_h, orig_h)
            cx, cy = (target_w - copy_w) // 2, (target_h - copy_h) // 2
            fx, fy = (orig_w - copy_w) // 2, (orig_h - copy_h) // 2
            canvas[cy:cy+copy_h, cx:cx+copy_w] = img[fy:fy+copy_h, fx:fx+copy_w]
            img = canvas
        else:
            img = cv2.resize(img, (target_w, target_h))
    
    h, w, _ = img.shape

    # ── Block grid (lossless: last block absorbs edge pixels) ──────────
    all_blocks = get_blocks(w, h, cols, rows)   # exactly cols*rows entries
    n_blocks = len(all_blocks)                   # == cols * rows

    if not reverse and options.get('export_svg', True):
        try:
            from core.svg_generator import export_grid_to_svg, export_scrambled_grid_to_svg
            base, _ = os.path.splitext(output_path)
            export_grid_to_svg(f"{base}_grid.svg", w, h, cols, rows, has_center=options.get('center', False), center_size=options.get('center_size', '1/4'))
            export_scrambled_grid_to_svg(f"{base}_grid_original.svg", w, h, cols, rows, seed, has_center=options.get('center', False), center_size=options.get('center_size', '1/4'), prefix_original=True)
            export_scrambled_grid_to_svg(f"{base}_grid_scrambled.svg", w, h, cols, rows, seed, has_center=options.get('center', False), center_size=options.get('center_size', '1/4'), prefix_original=False)
        except Exception as e:
            print("Failed to export SVG grids:", e)

    if proc_vid:
        if options.get('center'):
            center_size = options.get('center_size', '1/4')
            outer_indices, inner_indices, (cx1, cy1, cx2, cy2) = get_outer_blocks(cols, rows, w, h, center_size=center_size)
            N_outer = len(outer_indices)
            C1, R1 = find_best_grid(N_outer, target_ratio=cols/rows)

            # Source layout blocks for the outer region
            src_blocks_outer = get_blocks(w, h, C1, R1)

            shuffled_outer = seeded_shuffle(list(outer_indices), seed)

            # Precise gapless dimensions for central image
            cw = cx2 - cx1
            ch = cy2 - cy1

            # Calculate inner columns/rows for central image scrambling
            if center_size == '2/4':
                s = 0.7071
            elif center_size == '3/4':
                s = 0.866
            else:
                s = 0.5
            cols_inner = max(1, min(cols - 1, int(cols * s)))
            rows_inner = max(1, min(rows - 1, int(rows * s)))
            center_blocks = get_blocks(cw, ch, cols_inner, rows_inner)

            # Setup central image tile scrambling
            dest_to_src_center = {idx: idx for idx in range(cols_inner * rows_inner)}
            shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)
            if reverse:
                for i, v in enumerate(shuffled_center):
                    dest_to_src_center[v] = i
            else:
                for i, v in enumerate(shuffled_center):
                    dest_to_src_center[i] = v

            if reverse:
                # Restore Image 1 (Background)
                restored_img = np.zeros((h, w, 3), dtype=np.uint8)
                if video_encrypt_mode in ['external', 'both']:
                    # Unscramble outer background blocks
                    for j in range(N_outer):
                        # Destination block in the original layout (by flat index)
                        idx = shuffled_outer[j]
                        dx1, dy1, dx2, dy2 = all_blocks[idx]
                        tile = img[dy1:dy2, dx1:dx2]

                        # Source position in the packed source grid
                        x1, y1, x2, y2 = src_blocks_outer[j]
                        tile_resized = cv2.resize(tile, (x2 - x1, y2 - y1))
                        restored_img[y1:y2, x1:x2] = tile_resized
                else:
                    # Background is untouched, copy directly
                    restored_img = img.copy()

                # Extract Image 2 (Center)
                center_img = img[cy1:cy2, cx1:cx2]
                if video_encrypt_mode in ['center', 'both']:
                    # Unscramble center image using per-block coords
                    unscrambled_c = np.zeros((ch, cw, 3), dtype=np.uint8)
                    for i in range(cols_inner * rows_inner):
                        t_idx = dest_to_src_center[i]
                        sx1, sy1, sx2, sy2 = center_blocks[t_idx]
                        dx1, dy1, dx2, dy2 = center_blocks[i]
                        tile = center_img[sy1:sy2, sx1:sx2]
                        dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                        if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                            tile = cv2.resize(tile, (dw_blk, dh_blk))
                        unscrambled_c[dy1:dy2, dx1:dx2] = tile
                    center_img_to_write = unscrambled_c
                else:
                    center_img_to_write = center_img

                save_image(output_path, restored_img)
                base, ext = os.path.splitext(output_path)
                save_image(f"{base}_center{ext}", center_img_to_write)
            else:
                # Encrypt (Scramble Background into outer blocks)
                new_img = np.zeros((h, w, 3), dtype=np.uint8)
                if video_encrypt_mode in ['external', 'both']:
                    for j in range(N_outer):
                        # Read from source packed grid
                        x1, y1, x2, y2 = src_blocks_outer[j]
                        tile = img[y1:y2, x1:x2]

                        # Write to destination block in the shuffled outer layout
                        idx = shuffled_outer[j]
                        dx1, dy1, dx2, dy2 = all_blocks[idx]
                        tile_resized = cv2.resize(tile, (dx2 - dx1, dy2 - dy1))
                        new_img[dy1:dy2, dx1:dx2] = tile_resized
                else:
                    # Background is untouched, copy directly
                    for idx in outer_indices:
                        dx1, dy1, dx2, dy2 = all_blocks[idx]
                        new_img[dy1:dy2, dx1:dx2] = img[dy1:dy2, dx1:dx2]

                # Write center media
                if options.get('center_path') and os.path.exists(options['center_path']):
                    center_img = cv2.imread(options['center_path'])
                    if center_img is not None:
                        center_resized = cv2.resize(center_img, (cw, ch))

                        if video_encrypt_mode in ['center', 'both']:
                            # Scramble center image frame using per-block coords
                            scrambled_c = np.zeros((ch, cw, 3), dtype=np.uint8)
                            for i in range(cols_inner * rows_inner):
                                t_idx = dest_to_src_center[i]
                                sx1, sy1, sx2, sy2 = center_blocks[t_idx]
                                dx1, dy1, dx2, dy2 = center_blocks[i]
                                tile = center_resized[sy1:sy2, sx1:sx2]
                                dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                                if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                                    tile = cv2.resize(tile, (dw_blk, dh_blk))
                                scrambled_c[dy1:dy2, dx1:dx2] = tile
                            center_resized = scrambled_c

                        new_img[cy1:cy2, cx1:cx2] = center_resized
                save_image(output_path, new_img)
        else:
            # Simple full-frame scramble
            dest_to_src = {}
            if reverse:
                fwd = seeded_shuffle(list(range(n_blocks)), seed)
                for i, v in enumerate(fwd):
                    dest_to_src[v] = i
            else:
                shuffled = seeded_shuffle(list(range(n_blocks)), seed)
                for i, v in enumerate(shuffled):
                    dest_to_src[i] = v

            new_img = img.copy()
            for i in range(n_blocks):
                t_idx = dest_to_src[i]
                sx1, sy1, sx2, sy2 = all_blocks[t_idx]
                dx1, dy1, dx2, dy2 = all_blocks[i]
                tile = img[sy1:sy2, sx1:sx2]
                dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                    tile = cv2.resize(tile, (dw_blk, dh_blk))
                new_img[dy1:dy2, dx1:dx2] = tile
            save_image(output_path, new_img)
    else:
        save_image(output_path, img)
        
    progress_dict[task_id] = 100
