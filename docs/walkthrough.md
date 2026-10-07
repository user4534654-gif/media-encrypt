# Walkthrough — Fixes for Optical Decryption Latency, Marker Geometry, and UI Collapsible Toggles

We have resolved all 3 follow-up issues reported:
1. **Initial ~5-frame zone detection delay upon appearance in Decryptor**.
2. **Crooked / misaligned zone borders and fractional 0.5px edge clipping**.
3. **UI activation toggles**: moved checkboxes ("Modulate Audio" and "Selective Spatial Zones") directly into the collapsible section headers, with grayed-out disabled states preventing expansion when switched off.

---

## 1. Zero Frame Loss & Timeline-Wide Zone Discovery

### Problem
- The initial optical marker probe previously broke early if any zone was found in the first third of the video (`if discovered_zones and cur_idx > (tot_p // 3): break`), causing zones appearing later in the video to be missed during pre-flight.
- When an undiscovered zone appeared, periodic scanning only fired every 30 frames (`frame_count % 30 == 0`), delaying detection by up to 30 frames.
- `check_marker_presence` checked an exact pixel bounding box without search padding. Video compression artifacts and macroblock motion estimation on newly-appearing keyframes caused correlation scores to dip below threshold on the first few frames.

### Solution
- **Full-Duration Probe**: Removed premature break; the probe samples up to 30 evenly-spaced frames spanning 100% of the video duration.
- **Micro-Neighborhood Search**: Added `search_padding=3` in `check_marker_presence` using `cv2.minMaxLoc`. Markers are detected instantly even if shifted 1–3 pixels by H.264/H.265 compression blur.
- **Dynamic Fast Discovery & Temporal Hysteresis**: Main loop uses `scan_interval = 5` when seeking active zones, and maintains `zone_miss_counts` allowing up to 2 dropped frames before releasing lock, eliminating flickering.
- **Verified via automated test**: `scratch/test_burst_appearance.py` demonstrated instant frame-20 decryption with zero dropped frames.

---

## 2. Strict Boundary Geometry & Outward Integer Rounding

### Problem
- In `_group_markers_into_rois`, `outside` placement used `min(tl, bl) + size` and `max(tr, br)` which drifted inward and extended boundaries into the corner fiducial squares, leading to crooked decrypted regions.
- Fractional normalized coordinates without explicit outward pixel rounding caused 0.5px boundary slicing.

### Solution
- **`outside` Placement**: Zone boundaries are strictly derived from inner corner edges:
  ```python
  rx1 = max(0, max(tl[0] + m_size, bl[0] + m_size))  # Innermost left
  ry1 = max(0, max(tl[1] + m_size, tr[1] + m_size))  # Innermost top
  rx2 = min(w, min(tr[0], br[0]))                     # Innermost right
  ry2 = min(h, min(bl[1], br[1]))                     # Innermost bottom
  ```
- **`inside` Placement**: Zone boundaries are strictly derived from outermost corner edges:
  ```python
  rx1 = max(0, min(tl[0], bl[0]))
  ry1 = max(0, min(tl[1], tr[1]))
  rx2 = min(w, max(tr[0] + m_size, br[0] + m_size))
  ry2 = min(h, max(bl[1] + m_size, br[1] + m_size))
  ```
- **Outward Integer Expansion**: Used `math.floor` for `(x1, y1)` and `math.ceil` for `(x2, y2)` when mapping to pixel space, ensuring no half-pixel edge artifacts.
- **Marker Boxes Alignment**: In `_calculate_marker_boxes`, outside corner squares touch `rx1, ry1, rx2, ry2` with zero pixel overlap into the encrypted zone.

---

## 3. Collapsible Header Activation Toggles

### Layout & Behavior
- **Audio Quality & Scrambling Settings** (`#audCollapseHeader`):
  - Checkbox `"Modulate Audio"` (`#encAudio`) positioned on the far right of the header.
  - When unchecked: header turns gray (`opacity: 0.5; cursor: not-allowed`), automatically collapses if open, and prevents opening upon clicking.
- **Selective Spatial Zones & Timeline Patches** (`#spatialZonesCollapseHeader`):
  - Checkbox `"Enable"` (`#enableSpatialZones`) positioned on the far right of the header.
  - When unchecked: header turns gray (`opacity: 0.5; cursor: not-allowed`), automatically collapses if open, and prevents opening upon clicking.
- Redundant toggle rows inside section 1 and within the expanded content were removed.
- Full theme compatibility: `.collapse-trigger.disabled` is styled for both light and dark mode.

---

## 4. Test Verification Results

| Test Suite | Command | Result |
| :--- | :--- | :--- |
| Marker Geometry & Separation | `python scratch/test_marker_fixes.py` | **PASS** (Zero false positives, clean inpaint, 0 overlap) |
| Video Optical Roundtrip | `python scratch/test_video_optical_roundtrip.py` | **PASS** (Both outside and inside modes verified) |
| Instant Burst Appearance | `python scratch/test_burst_appearance.py` | **PASS** (Immediate frame-20 decryption, 0 dropped frames) |
| GitNexus Change Analysis | `detect_changes({scope: "all"})` | **PASS** (0 affected execution flows, risk level LOW) |
