import cv2
import numpy as np
import os
from core.crypto import seeded_shuffle, stamp_optical_markers, restore_optical_markers, detect_optical_markers, inpaint_optical_markers
from core.grid_utils import find_best_grid, get_outer_blocks, get_blocks, get_roi_blocks
from core.logger import LiveDebugger
def save_image(path, img):
    base_p, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm', ''):
        path = base_p + '.png'
        ext = '.png'
    if ext in ('.jpg', '.jpeg'):
        try:
            from PIL import Image
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            Image.fromarray(img_rgb).save(path, 'JPEG', quality=95, optimize=True)
            return
        except Exception as e:
            raise RuntimeError(f"Failed to save as JPEG: {e}. Ensure 'pillow' is installed.")
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
@LiveDebugger.trace(module_name="IMAGE")
def process_image_file(input_path, output_path, options, progress_dict, task_id):
    is_cancelled_cb = options.get('is_cancelled')
    if is_cancelled_cb and is_cancelled_cb():
        LiveDebugger.log("CANCEL", f"Image processing cancelled for task {task_id}", level="WARNING", module="IMAGE")
        raise RuntimeError("Processing cancelled by user")
    proc_vid = options.get('process_video', True)
    reverse = options.get('reverse') or (options.get('action') == 'unscramble')
    cols, rows, seed = options.get('cols', 1), options.get('rows', 1), options.get('seed', 0)
    target_w, target_h = options.get('target_w'), options.get('target_h')
    no_scale = options.get('no_scale', False)
    video_encrypt_mode = options.get('video_encrypt_mode', 'external')                               
    LiveDebugger.log("LOAD_IMAGE", f"Loading '{os.path.basename(input_path)}' | grid={cols}x{rows}, seed={seed}, reverse={reverse}", level="DEBUG", module="IMAGE")
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
    all_blocks = get_blocks(w, h, cols, rows)                              
    n_blocks = len(all_blocks)                                   
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
        _center_path = options.get('center_path')
        _zone_roi = options.get('patch_roi')
        _img_combine_enc = (not reverse and options.get('center') and _center_path
                            and os.path.exists(_center_path) and bool(_zone_roi))
        _img_combine_dec = (reverse and options.get('center')
                            and (bool(_zone_roi) or bool(options.get('optical_markers'))))
        if _img_combine_enc or _img_combine_dec:
            from core.video_processor import _encrypt_zone_nested, _decrypt_zone_nested
            placement = options.get('marker_placement', 'outside')
            if options.get('optical_markers') and placement == 'inside':
                LiveDebugger.log("MARKER_PLACEMENT", "Image Zone+Center mode: 'inside' corner markers would be overwritten by the pasted center content. Coercing marker_placement to 'outside'.", level="WARNING", module="IMAGE")
                placement = 'outside'
                options['marker_placement'] = 'outside'
            roi = list(_zone_roi) if _zone_roi else None
            if _img_combine_dec and options.get('optical_markers') and not roi:
                d_roi = detect_optical_markers(img, placement=placement)
                if d_roi:
                    roi = list(d_roi)
                    options['patch_roi'] = roi
                    LiveDebugger.log("MARKER_DETECT", f"Auto-detected optical markers in image! Reconstructed ROI: {roi}", level="SUCCESS", module="IMAGE")
                else:
                    LiveDebugger.log("MARKER_DETECT", "Warning: Optical markers specified in key, but could not be detected in image.", level="WARNING", module="IMAGE")
            if not roi:
                roi = [0.0, 0.0, 1.0, 1.0]
            rx1, ry1, rx2, ry2 = roi
            if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
                px1, py1 = int(round(rx1 * w)), int(round(ry1 * h))
                px2, py2 = int(round(rx2 * w)), int(round(ry2 * h))
            else:
                px1, py1, px2, py2 = int(rx1), int(ry1), int(rx2), int(ry2)
            px1, py1 = max(0, min(w, px1)), max(0, min(h, py1))
            px2, py2 = max(0, min(w, px2)), max(0, min(h, py2))
            zw, zh = max(2, px2 - px1), max(2, py2 - py1)
            if _img_combine_enc:
                center_img = cv2.imread(_center_path)
                if center_img is None:
                    from PIL import Image as _PILImage
                    center_img = cv2.cvtColor(np.array(_PILImage.open(_center_path).convert('RGB')), cv2.COLOR_RGB2BGR)
                zone_bg = img[py1:py2, px1:px2]
                if zone_bg.shape[1] != zw or zone_bg.shape[0] != zh:
                    zone_bg = cv2.resize(zone_bg, (zw, zh))
                new_zone = _encrypt_zone_nested(
                    zone_bg, center_img, cols, rows,
                    options.get('center_size', '1/4'), seed, video_encrypt_mode)
                new_img = img.copy()
                new_img[py1:py2, px1:px2] = new_zone
                if options.get('optical_markers'):
                    new_img, optical_payload = stamp_optical_markers(new_img, px1, py1, px2, py2, placement=placement)
                    options['optical_payload'] = optical_payload
                save_image(output_path, new_img)
            else:
                patch = img[py1:py2, px1:px2]
                if patch.shape[1] != zw or patch.shape[0] != zh:
                    patch = cv2.resize(patch, (zw, zh))
                restored_zone, clean_center = _decrypt_zone_nested(
                    patch, cols, rows, options.get('center_size', '1/4'), seed, video_encrypt_mode)
                new_img = img.copy()
                new_img[py1:py2, px1:px2] = restored_zone
                if options.get('optical_markers'):
                    if options.get('optical_payload'):
                        new_img = restore_optical_markers(new_img, options['optical_payload'])
                    else:
                        new_img = inpaint_optical_markers(new_img, px1, py1, px2, py2, placement=placement)
                save_image(output_path, new_img)
                base, ext = os.path.splitext(output_path)
                save_image(f"{base}_center{ext}", clean_center)
        elif options.get('center'):
            center_size = options.get('center_size', '1/4')
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
            dest_to_src_center = {idx: idx for idx in range(cols_inner * rows_inner)}
            shuffled_center = seeded_shuffle(list(range(cols_inner * rows_inner)), seed)
            if reverse:
                for i, v in enumerate(shuffled_center):
                    dest_to_src_center[v] = i
            else:
                for i, v in enumerate(shuffled_center):
                    dest_to_src_center[i] = v
            if reverse:
                restored_img = np.zeros((h, w, 3), dtype=np.uint8)
                if video_encrypt_mode in ['external', 'both']:
                    for j in range(N_outer):
                        idx = shuffled_outer[j]
                        dx1, dy1, dx2, dy2 = all_blocks[idx]
                        tile = img[dy1:dy2, dx1:dx2]
                        x1, y1, x2, y2 = src_blocks_outer[j]
                        tile_resized = cv2.resize(tile, (x2 - x1, y2 - y1))
                        restored_img[y1:y2, x1:x2] = tile_resized
                else:
                    restored_img = img.copy()
                center_img = img[cy1:cy2, cx1:cx2]
                if video_encrypt_mode in ['center', 'both']:
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
                new_img = np.zeros((h, w, 3), dtype=np.uint8)
                if video_encrypt_mode in ['external', 'both']:
                    for j in range(N_outer):
                        x1, y1, x2, y2 = src_blocks_outer[j]
                        tile = img[y1:y2, x1:x2]
                        idx = shuffled_outer[j]
                        dx1, dy1, dx2, dy2 = all_blocks[idx]
                        tile_resized = cv2.resize(tile, (dx2 - dx1, dy2 - dy1))
                        new_img[dy1:dy2, dx1:dx2] = tile_resized
                else:
                    for idx in outer_indices:
                        dx1, dy1, dx2, dy2 = all_blocks[idx]
                        new_img[dy1:dy2, dx1:dx2] = img[dy1:dy2, dx1:dx2]
                if options.get('center_path') and os.path.exists(options['center_path']):
                    center_img = cv2.imread(options['center_path'])
                    if center_img is not None:
                        center_resized = cv2.resize(center_img, (cw, ch))
                        if video_encrypt_mode in ['center', 'both']:
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
        elif options.get('patch_roi') or (reverse and options.get('optical_markers')):
            roi = options.get('patch_roi')
            if reverse and options.get('optical_markers') and not roi:
                placement = options.get('marker_placement', 'outside')
                d_roi = detect_optical_markers(img, placement=placement)
                if d_roi:
                    roi = list(d_roi)
                    options['patch_roi'] = roi
                    LiveDebugger.log("MARKER_DETECT", f"Auto-detected optical markers in image! Reconstructed ROI: {roi}", level="SUCCESS", module="IMAGE")
                else:
                    LiveDebugger.log("MARKER_DETECT", "Warning: Optical markers specified in key, but could not be detected in image.", level="WARNING", module="IMAGE")
            if not roi:
                roi = [0.0, 0.0, 1.0, 1.0]
            roi_invert = options.get('roi_invert', False)
            roi_blocks = get_roi_blocks(w, h, roi, cols, rows, invert=roi_invert)
            n_roi_blocks = len(roi_blocks)
            dest_to_src = {}
            if reverse:
                fwd = seeded_shuffle(list(range(n_roi_blocks)), seed)
                for i, v in enumerate(fwd):
                    dest_to_src[v] = i
            else:
                shuffled = seeded_shuffle(list(range(n_roi_blocks)), seed)
                for i, v in enumerate(shuffled):
                    dest_to_src[i] = v
            new_img = img.copy()
            for i in range(n_roi_blocks):
                t_idx = dest_to_src[i]
                sx1, sy1, sx2, sy2 = roi_blocks[t_idx]
                dx1, dy1, dx2, dy2 = roi_blocks[i]
                tile = img[sy1:sy2, sx1:sx2]
                dw_blk, dh_blk = dx2 - dx1, dy2 - dy1
                if tile.shape[1] != dw_blk or tile.shape[0] != dh_blk:
                    tile = cv2.resize(tile, (dw_blk, dh_blk))
                new_img[dy1:dy2, dx1:dx2] = tile
            if not reverse and options.get('optical_markers'):
                rx1, ry1, rx2, ry2 = roi
                if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
                    rx1, ry1, rx2, ry2 = int(rx1 * w), int(ry1 * h), int(rx2 * w), int(ry2 * h)
                placement = options.get('marker_placement', 'outside')
                new_img, optical_payload = stamp_optical_markers(new_img, rx1, ry1, rx2, ry2, placement=placement)
                options['optical_payload'] = optical_payload
            elif reverse and options.get('optical_markers'):
                if options.get('optical_payload'):
                    new_img = restore_optical_markers(new_img, options['optical_payload'])
                elif roi:
                    rx1, ry1, rx2, ry2 = roi
                    if rx1 <= 1.0 and ry1 <= 1.0 and rx2 <= 1.0 and ry2 <= 1.0:
                        rx1, ry1, rx2, ry2 = int(rx1 * w), int(ry1 * h), int(rx2 * w), int(ry2 * h)
                    placement = options.get('marker_placement', 'outside')
                    new_img = inpaint_optical_markers(new_img, rx1, ry1, rx2, ry2, placement=placement)
            save_image(output_path, new_img)
        else:
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
