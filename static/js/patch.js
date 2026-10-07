/**
 * Video Studio - Modern Selective Spatial Zones & Timeline Editor
 * Full Video Editor UX: Draggable clips, trim handles, ruler ticks, playhead scrubbing.
 */

let patchVideoDuration = 0;
let patchSegments = [];
let patchNextId = 1;
let patchBaseFile = null;
let patchInteractionMode = 'move'; // 'move' | 'resize'

// Normalized 0.0 - 1.0 Spatial Coordinates (ROI)
let patchRegion = { x1: 0.20, y1: 0.20, x2: 0.80, y2: 0.80 };
let isInteracting = false;
let interactionType = null; // 'move' | 'resize'
let activeResizeHandle = null;
let startPointer = { x: 0, y: 0 };
let initialRegionState = { x1: 0, y1: 0, x2: 0, y2: 0 };

let activePatchSegmentId = null;

// Timeline Dragging State
let timelineDragMode = null; // 'scrub' | 'clip-move' | 'trim-left' | 'trim-right'
let timelineDragSegId = null;
let timelineDragInitial = { start: 0, end: 0, pointerX: 0 };

function formatTimeMs(sec) {
    if (isNaN(sec) || sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 1000);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

function parseTimeMs(str) {
    if (typeof str === 'number') return str;
    if (!str) return 0;
    str = String(str).trim();
    if (str.includes(':')) {
        const parts = str.split(':');
        const m = parseFloat(parts[0]) || 0;
        const s = parseFloat(parts[1]) || 0;
        return m * 60 + s;
    }
    return parseFloat(str) || 0;
}

// ── Initialization & Event Listeners ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const player = document.getElementById('patchVideoPlayer');
    const box = document.getElementById('patchRegionBox');
    const container = document.getElementById('patchPreviewContainer');

    // Also monitor main video upload to automatically feed into the Spatial Editor
    const mainUpload = document.getElementById('mediaUpload');
    if (mainUpload) {
        mainUpload.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                loadPatchMediaFile(e.target.files[0]);
            }
        });
    }

    if (player) {
        player.addEventListener('loadedmetadata', () => {
            patchVideoDuration = player.duration || 0;
            updateDurationLabels();
            renderVeRulerTicks();
            veBuildFilmstrip();

            if (patchSegments.length === 0 && patchVideoDuration > 0) {
                const segEnd = Math.min(patchVideoDuration, Math.max(2.0, patchVideoDuration * 0.35));
                addPatchSegment(0, segEnd);
            } else {
                renderVeTimelineClips();
            }
        });

        player.addEventListener('timeupdate', () => {
            const cur = player.currentTime || 0;
            const timeOverlay = document.getElementById('patchPlayerOverlay');
            if (timeOverlay) {
                timeOverlay.innerText = `${formatTimeMs(cur)} / ${formatTimeMs(patchVideoDuration)}`;
            }
            updateDurationLabels();

            // Update Playhead position
            const playhead = document.getElementById('vePlayhead');
            if (playhead && patchVideoDuration > 0) {
                const pct = (cur / patchVideoDuration) * 100;
                playhead.style.left = `${Math.min(100, Math.max(0, pct))}%`;
            }

            updateZoneVisibilityAtTime(cur);
        });

        player.addEventListener('play', () => {
            const btn = document.getElementById('vePlayPauseBtn');
            if (btn) btn.innerText = "⏸ Pause";
        });

        player.addEventListener('pause', () => {
            const btn = document.getElementById('vePlayPauseBtn');
            if (btn) btn.innerText = "▶ Play";
        });
    }

    // Interactive Region Box Drag / Resize on Canvas
    if (box && container) {
        box.addEventListener('pointerdown', (e) => {
            if (e.target.classList.contains('patch-resize-handle')) {
                interactionType = 'resize';
                activeResizeHandle = e.target.getAttribute('data-handle');
                box.classList.add('resizing-active');
            } else {
                interactionType = 'move';
                box.classList.add('moving-active');
            }
            isInteracting = true;
            startPointer = { x: e.clientX, y: e.clientY };
            initialRegionState = { ...patchRegion };
            e.stopPropagation();
            box.setPointerCapture(e.pointerId);
        });

        box.addEventListener('pointermove', onRegionPointerMove);
        box.addEventListener('pointerup', onRegionPointerUp);
        box.addEventListener('pointercancel', onRegionPointerUp);
    }

    // Timeline Scrubbing & Interaction
    setupTimelineEvents();

    updateRegionBoxVisuals();
});

function toggleSpatialZonesEditor(enabled) {
    const container = document.getElementById('spatialZonesEditorContainer');
    if (container) {
        container.classList.toggle('hidden', !enabled);
    }

    // Auto-load main uploaded video if present and player is empty
    const mainUpload = document.getElementById('mediaUpload');
    const player = document.getElementById('patchVideoPlayer');
    if (enabled && mainUpload && mainUpload.files && mainUpload.files.length > 0) {
        if (!player || !player.src) {
            loadPatchMediaFile(mainUpload.files[0]);
        }
    }
}

// ── Region Box Manipulation (Canvas Stage) ───────────────────────────────────

function onRegionPointerMove(e) {
    if (!isInteracting) return;
    const container = document.getElementById('patchPreviewContainer');
    if (!container) return;

    const rect = container.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const dx = (e.clientX - startPointer.x) / rect.width;
    const dy = (e.clientY - startPointer.y) / rect.height;

    let { x1, y1, x2, y2 } = initialRegionState;
    const minW = 0.05;
    const minH = 0.05;

    if (interactionType === 'move') {
        const w = x2 - x1;
        const h = y2 - y1;
        let nx1 = Math.max(0, Math.min(1 - w, x1 + dx));
        let ny1 = Math.max(0, Math.min(1 - h, y1 + dy));
        x1 = nx1;
        y1 = ny1;
        x2 = nx1 + w;
        y2 = ny1 + h;
    } else if (interactionType === 'resize' && activeResizeHandle) {
        const h = activeResizeHandle;
        if (h.includes('w')) x1 = Math.max(0, Math.min(x2 - minW, x1 + dx));
        if (h.includes('e')) x2 = Math.min(1, Math.max(x1 + minW, x2 + dx));
        if (h.includes('n')) y1 = Math.max(0, Math.min(y2 - minH, y1 + dy));
        if (h.includes('s')) y2 = Math.min(1, Math.max(y1 + minH, y2 + dy));
    }

    patchRegion = {
        x1: parseFloat(x1.toFixed(4)),
        y1: parseFloat(y1.toFixed(4)),
        x2: parseFloat(x2.toFixed(4)),
        y2: parseFloat(y2.toFixed(4))
    };
    // Outside markers must stay on-screen: shrink the max zone to the margin.
    patchRegion = applyOutsideMarkerLimits(patchRegion, videoOutsideMarkerMargin());

    updateRegionBoxVisuals();
}

function onRegionPointerUp(e) {
    if (!isInteracting) return;
    isInteracting = false;
    interactionType = null;
    activeResizeHandle = null;

    const box = document.getElementById('patchRegionBox');
    if (box) {
        box.classList.remove('moving-active', 'resizing-active');
    }
}

function updateRegionBoxVisuals() {
    const box = document.getElementById('patchRegionBox');
    if (!box) return;

    const { x1, y1, x2, y2 } = patchRegion;
    box.style.left = `${(x1 * 100).toFixed(2)}%`;
    box.style.top = `${(y1 * 100).toFixed(2)}%`;
    box.style.width = `${((x2 - x1) * 100).toFixed(2)}%`;
    box.style.height = `${((y2 - y1) * 100).toFixed(2)}%`;

    // Update coordinate numerical input fields
    const inX1 = document.getElementById('patchCoordX1');
    const inY1 = document.getElementById('patchCoordY1');
    const inX2 = document.getElementById('patchCoordX2');
    const inY2 = document.getElementById('patchCoordY2');

    if (inX1) inX1.value = x1.toFixed(2);
    if (inY1) inY1.value = y1.toFixed(2);
    if (inX2) inX2.value = x2.toFixed(2);
    if (inY2) inY2.value = y2.toFixed(2);

    // Sync to active segment
    syncActiveSegmentRoi();
}

function onManualCoordInput() {
    const inX1 = parseFloat(document.getElementById('patchCoordX1').value) || 0;
    const inY1 = parseFloat(document.getElementById('patchCoordY1').value) || 0;
    const inX2 = parseFloat(document.getElementById('patchCoordX2').value) || 1;
    const inY2 = parseFloat(document.getElementById('patchCoordY2').value) || 1;

    patchRegion = {
        x1: Math.max(0, Math.min(1, Math.min(inX1, inX2))),
        y1: Math.max(0, Math.min(1, Math.min(inY1, inY2))),
        x2: Math.max(0, Math.min(1, Math.max(inX1, inX2))),
        y2: Math.max(0, Math.min(1, Math.max(inY1, inY2)))
    };
    patchRegion = applyOutsideMarkerLimits(patchRegion, videoOutsideMarkerMargin());
    updateRegionBoxVisuals();
}

function setPatchInteractionMode(mode) {
    patchInteractionMode = mode;
    const btnMove = document.getElementById('patchToolMove');
    const btnResize = document.getElementById('patchToolResize');
    if (btnMove) btnMove.classList.toggle('active', mode === 'move');
    if (btnResize) btnResize.classList.toggle('active', mode === 'resize');

    // Scope to the VIDEO stage only so the Image tab handles are unaffected
    const container = document.getElementById('patchPreviewContainer');
    const handles = container ? container.querySelectorAll('.patch-resize-handle') : document.querySelectorAll('#patchRegionBox .patch-resize-handle');
    handles.forEach(h => {
        h.style.display = (mode === 'move') ? 'none' : 'block';
    });
}

function setPatchFullscreen() {
    patchRegion = { x1: 0.0, y1: 0.0, x2: 1.0, y2: 1.0 };
    patchRegion = applyOutsideMarkerLimits(patchRegion, videoOutsideMarkerMargin());
    updateRegionBoxVisuals();
}

function resetPatchBoxToCenter() {
    patchRegion = { x1: 0.25, y1: 0.25, x2: 0.75, y2: 0.75 };
    updateRegionBoxVisuals();
}

function toggleOpticalPlacement(enabled) {
    const row = document.getElementById('patchMarkerPlacementRow');
    if (row) row.classList.toggle('hidden', !enabled);
}

function toggleImgOpticalPlacement(enabled) {
    const row = document.getElementById('imgMarkerPlacementRow');
    if (row) row.classList.toggle('hidden', !enabled);
}

// ── Outside-marker max-zone limiter ──────────────────────────────────────────
// 'Outside' markers are stamped around the zone (one marker size beyond each
// border), so the zone must keep that margin from the frame edges —
// otherwise markers land off-screen and decryption can never find them.
// Margins are normalized by the real media resolution (18px backend default).
var OPTICAL_MARKER_PX = 18;

function videoOutsideMarkerMargin() {
    const optEl = document.getElementById('patchOpticalMarkers');
    const placeEl = document.getElementById('patchMarkerPlacement');
    const optOn = optEl ? optEl.checked : false;
    const placement = placeEl ? placeEl.value : 'outside';
    if (!optOn || placement !== 'outside') return { mx: 0, my: 0 };
    const player = document.getElementById('patchVideoPlayer');
    const imgPrev = document.getElementById('patchImagePreview');
    let w = 0, h = 0;
    if (player && player.videoWidth) { w = player.videoWidth; h = player.videoHeight; }
    else if (imgPrev && imgPrev.naturalWidth) { w = imgPrev.naturalWidth; h = imgPrev.naturalHeight; }
    if (!w || !h) return { mx: 0, my: 0 };
    return { mx: OPTICAL_MARKER_PX / w, my: OPTICAL_MARKER_PX / h };
}

function imgOutsideMarkerMargin() {
    const optEl = document.getElementById('imgOpticalMarkers');
    const placeEl = document.getElementById('imgMarkerPlacement');
    const optOn = optEl ? optEl.checked : false;
    const placement = placeEl ? placeEl.value : 'outside';
    if (!optOn || placement !== 'outside') return { mx: 0, my: 0 };
    const prev = document.getElementById('imgPatchPreview');
    const w = prev ? (prev.naturalWidth || 0) : 0;
    const h = prev ? (prev.naturalHeight || 0) : 0;
    if (!w || !h) return { mx: 0, my: 0 };
    return { mx: OPTICAL_MARKER_PX / w, my: OPTICAL_MARKER_PX / h };
}

// Clamp a normalized box so outside markers stay on-screen. Returns the box
// unchanged when markers are inside/off, the media is too small for a margin,
// or dims are still unknown.
function applyOutsideMarkerLimits(box, m) {
    if (!m || (m.mx <= 0 && m.my <= 0)) return box;
    const minW = 0.05, minH = 0.05;
    if (m.mx * 2 + minW >= 1 || m.my * 2 + minH >= 1) return box;
    let x1 = Math.min(Math.max(box.x1, m.mx), 1 - m.mx - minW);
    let y1 = Math.min(Math.max(box.y1, m.my), 1 - m.my - minH);
    let x2 = Math.max(Math.min(box.x2, 1 - m.mx), m.mx + minW);
    let y2 = Math.max(Math.min(box.y2, 1 - m.my), m.my + minH);
    if (x2 - x1 < minW) { x1 = Math.max(m.mx, x2 - minW); }
    if (y2 - y1 < minH) { y1 = Math.max(m.my, y2 - minH); }
    return { x1: x1, y1: y1, x2: x2, y2: y2 };
}

// ── Media Loading ────────────────────────────────────────────────────────────

// ── Timeline filmstrip preview (video thumbnails behind zone clips) ─────────
// Captures small JPEG thumbnails at even time slices with an offscreen video
// element (the visible player is never disturbed) and tiles them across the
// track, like classic video editors. Purely visual: clips/playhead keep working.

let veFilmstripToken = 0;

function veClearFilmstrip() {
    veFilmstripToken++;
    const strip = document.getElementById('veFilmstrip');
    if (strip) strip.innerHTML = '';
}

function veBuildFilmstrip() {
    const strip = document.getElementById('veFilmstrip');
    const player = document.getElementById('patchVideoPlayer');
    if (!strip || !player) return;
    const src = player.currentSrc || player.src;
    const dur = patchVideoDuration;
    if (!src || !(dur > 0)) return;
    const myToken = ++veFilmstripToken;
    strip.innerHTML = '<div class="ve-filmstrip-empty">loading preview…</div>';

    const count = Math.max(6, Math.min(24, Math.floor(dur / 2) || 6));
    const cap = document.createElement('video');
    cap.muted = true;
    cap.preload = 'auto';
    cap.src = src;

    const canvas = document.createElement('canvas');
    canvas.width = 96;
    canvas.height = 54;
    const ctx = canvas.getContext('2d');

    let idx = 0;
    let started = false;
    let stepTimer = 0;
    function clearStepTimer() { if (stepTimer) { clearTimeout(stepTimer); stepTimer = 0; } }
    function next() {
        clearStepTimer();
        if (myToken !== veFilmstripToken) return;
        if (idx >= count) {
            // Every slice failed: drop the placeholder, keep the plain track.
            if (!strip.querySelector('.ve-filmstrip-thumb')) strip.innerHTML = '';
            return;
        }
        const t = ((idx + 0.5) * dur) / count;
        idx++;
        try {
            // Skip a slice if the seek gets stuck (corrupt timestamps, etc.).
            stepTimer = setTimeout(next, 4000);
            cap.currentTime = Math.min(Math.max(0, t), Math.max(0, dur - 0.05));
        } catch (e) { next(); }
    }
    function capture() {
        if (myToken !== veFilmstripToken) return;
        try {
            const first = strip.querySelector('.ve-filmstrip-empty');
            if (first) first.remove();
            const vw = cap.videoWidth, vh = cap.videoHeight;
            if (vw && vh) {
                const scale = Math.max(vw / 96, vh / 54);
                const sw = 96 * scale, sh = 54 * scale;
                ctx.drawImage(cap, (vw - sw) / 2, (vh - sh) / 2, sw, sh, 0, 0, 96, 54);
            } else {
                ctx.fillStyle = '#000';
                ctx.fillRect(0, 0, 96, 54);
            }
            const img = document.createElement('img');
            img.className = 've-filmstrip-thumb';
            img.alt = '';
            img.src = canvas.toDataURL('image/jpeg', 0.6);
            strip.appendChild(img);
        } catch (e) { /* keep the strip usable, continue with next slice */ }
        next();
    }
    cap.addEventListener('loadedmetadata', () => { started = true; next(); });
    cap.addEventListener('seeked', () => { if (started) capture(); });
    cap.addEventListener('error', () => {
        clearStepTimer();
        if (!started && !strip.querySelector('.ve-filmstrip-thumb')) strip.innerHTML = '';
    });
}

function loadPatchMediaFile(file) {
    patchBaseFile = file;
    veClearFilmstrip();
    // Keep in sync with IMAGE_EXTENSIONS in core/metadata_prober.py.
    const isImage = file.type.startsWith('image/') || /\.(jpe?g|jpe|jfif|jif|jfi|png|webp|avif|bmp|tiff?|gif|ico)$/i.test(file.name);

    const player = document.getElementById('patchVideoPlayer');
    const imagePreview = document.getElementById('patchImagePreview');
    const timelineSection = document.getElementById('veTimelineSection');

    if (isImage) {
        if (player) {
            player.pause();
            player.style.display = 'none';
        }
        if (imagePreview) {
            imagePreview.src = URL.createObjectURL(file);
            imagePreview.style.display = 'block';
        }
        if (timelineSection) timelineSection.style.display = 'none';
        const vFmt = document.getElementById('v_fmt');
        if (vFmt && ['.mp4', '.mkv', '.avi', '.webm', '.mov'].includes(vFmt.value)) {
            vFmt.value = 'auto';
        }
    } else {
        if (imagePreview) imagePreview.style.display = 'none';
        if (player) {
            player.src = URL.createObjectURL(file);
            player.style.display = 'block';
            player.load();
        }
        if (timelineSection) timelineSection.style.display = 'block';
        const vFmt = document.getElementById('v_fmt');
        if (vFmt && ['.png', '.jpg', '.webp', '.avif'].includes(vFmt.value)) {
            vFmt.value = 'auto';
        }
    }
}

// ── Video Editor Timeline Engine (.ve-*) ─────────────────────────────────────

function veTogglePlay() {
    const player = document.getElementById('patchVideoPlayer');
    if (!player) return;
    if (player.paused) player.play();
    else player.pause();
}

function veSeekTo(sec) {
    const player = document.getElementById('patchVideoPlayer');
    if (!player) return;
    sec = Math.max(0, Math.min(patchVideoDuration || 99999, sec));
    player.currentTime = sec;
    updateDurationLabels();

    const playhead = document.getElementById('vePlayhead');
    if (playhead && patchVideoDuration > 0) {
        const pct = (sec / patchVideoDuration) * 100;
        playhead.style.left = `${Math.min(100, Math.max(0, pct))}%`;
    }
    updateZoneVisibilityAtTime(sec);
}

function updateZoneVisibilityAtTime(cur) {
    const box = document.getElementById('patchRegionBox');
    if (!box) return;
    if (isInteracting) return;

    if (patchSegments.length === 0) {
        box.style.display = 'flex';
        return;
    }

    const activeSeg = patchSegments.find(s => cur >= (s.start - 0.04) && cur <= (s.end + 0.04));
    if (activeSeg) {
        box.style.display = 'flex';
        if (activeSeg.roi && activeSeg.roi.length >= 4) {
            patchRegion = {
                x1: activeSeg.roi[0],
                y1: activeSeg.roi[1],
                x2: activeSeg.roi[2],
                y2: activeSeg.roi[3]
            };
            const { x1, y1, x2, y2 } = patchRegion;
            box.style.left = `${(x1 * 100).toFixed(2)}%`;
            box.style.top = `${(y1 * 100).toFixed(2)}%`;
            box.style.width = `${((x2 - x1) * 100).toFixed(2)}%`;
            box.style.height = `${((y2 - y1) * 100).toFixed(2)}%`;

            const inX1 = document.getElementById('patchCoordX1');
            const inY1 = document.getElementById('patchCoordY1');
            const inX2 = document.getElementById('patchCoordX2');
            const inY2 = document.getElementById('patchCoordY2');
            if (inX1) inX1.value = x1.toFixed(2);
            if (inY1) inY1.value = y1.toFixed(2);
            if (inX2) inX2.value = x2.toFixed(2);
            if (inY2) inY2.value = y2.toFixed(2);
        }
        if (activePatchSegmentId !== activeSeg.id) {
            activePatchSegmentId = activeSeg.id;
            updateActiveZoneBar(activeSeg);
            renderVeTimelineClips();
        }
    } else {
        box.style.display = 'none';
    }
}

function updateDurationLabels() {
    const player = document.getElementById('patchVideoPlayer');
    const cur = player ? (player.currentTime || 0) : 0;
    const dur = patchVideoDuration || 0;
    const lbl = document.getElementById('veDurationLabel');
    if (lbl) {
        lbl.innerText = `${formatTimeMs(cur)} / ${formatTimeMs(dur)}`;
    }
}

function renderVeRulerTicks() {
    const ticksContainer = document.getElementById('veRulerTicks');
    const gridLinesContainer = document.getElementById('veGridLines');
    if (!ticksContainer || patchVideoDuration <= 0) return;

    ticksContainer.innerHTML = '';
    if (gridLinesContainer) gridLinesContainer.innerHTML = '';

    // Decide tick step: 1s, 2s, 5s, 10s, 30s, 60s
    let step = 1;
    if (patchVideoDuration > 120) step = 15;
    else if (patchVideoDuration > 60) step = 10;
    else if (patchVideoDuration > 30) step = 5;
    else if (patchVideoDuration > 10) step = 2;

    for (let t = 0; t <= patchVideoDuration; t += step) {
        const pct = (t / patchVideoDuration) * 100;

        const tickMark = document.createElement('div');
        tickMark.className = 've-ruler-tick-mark';
        tickMark.style.left = `${pct}%`;
        ticksContainer.appendChild(tickMark);

        const tickLabel = document.createElement('div');
        tickLabel.className = 've-ruler-tick-label';
        tickLabel.style.left = `${pct}%`;
        tickLabel.innerText = formatTimeMs(t).substring(0, 5);
        ticksContainer.appendChild(tickLabel);

        if (gridLinesContainer && t > 0) {
            const gridLine = document.createElement('div');
            gridLine.className = 've-grid-line';
            gridLine.style.left = `${pct}%`;
            gridLinesContainer.appendChild(gridLine);
        }
    }
}

function addPatchSegment(startSec, endSec) {
    if (patchVideoDuration > 0) {
        startSec = Math.max(0, Math.min(patchVideoDuration, startSec));
        endSec = Math.max(startSec + 0.2, Math.min(patchVideoDuration, endSec));
    }
    const currentRoi = [patchRegion.x1, patchRegion.y1, patchRegion.x2, patchRegion.y2];
    const seg = {
        id: patchNextId++,
        start: parseFloat(startSec.toFixed(3)),
        end: parseFloat(endSec.toFixed(3)),
        roi: [...currentRoi]
    };
    patchSegments.push(seg);
    selectPatchSegment(seg.id);
    renderVeTimelineClips();
}

function veAddZoneAtPlayhead() {
    const player = document.getElementById('patchVideoPlayer');
    const playheadSec = player ? (player.currentTime || 0) : 0;
    const dur = Math.min(2.5, Math.max(1.0, (patchVideoDuration - playheadSec)));
    addPatchSegment(playheadSec, playheadSec + dur);
}

function veDeleteActiveZone() {
    if (!activePatchSegmentId) return;
    removePatchSegment(activePatchSegmentId);
}

function removePatchSegment(id) {
    patchSegments = patchSegments.filter(s => s.id !== id);
    if (activePatchSegmentId === id) {
        activePatchSegmentId = patchSegments.length > 0 ? patchSegments[0].id : null;
    }
    if (activePatchSegmentId) {
        selectPatchSegment(activePatchSegmentId);
    } else {
        updateActiveZoneBar(null);
    }
    renderVeTimelineClips();
}

function selectPatchSegment(id, seekToStart = false) {
    activePatchSegmentId = id;
    const seg = patchSegments.find(s => s.id === id);
    if (seg) {
        if (seg.roi && seg.roi.length >= 4) {
            patchRegion = { x1: seg.roi[0], y1: seg.roi[1], x2: seg.roi[2], y2: seg.roi[3] };
            updateRegionBoxVisuals();
        }
        updateActiveZoneBar(seg);
        renderVeTimelineClips();

        const box = document.getElementById('patchRegionBox');
        if (box) box.style.display = 'flex';

        const player = document.getElementById('patchVideoPlayer');
        if (player && seekToStart) {
            if (player.currentTime < seg.start || player.currentTime > seg.end) {
                veSeekTo(seg.start);
            }
        }
    }
}

function syncActiveSegmentRoi() {
    if (patchSegments.length === 0) return;
    const currentRoi = [patchRegion.x1, patchRegion.y1, patchRegion.x2, patchRegion.y2];
    let targetSeg = patchSegments.find(s => s.id === activePatchSegmentId);
    if (!targetSeg) {
        targetSeg = patchSegments[0];
        activePatchSegmentId = targetSeg.id;
    }
    targetSeg.roi = [...currentRoi];
    updateActiveZoneBar(targetSeg);
}

function updateActiveZoneBar(seg) {
    const bar = document.getElementById('veActiveZoneBar');
    const title = document.getElementById('veActiveZoneTitle');
    const inStart = document.getElementById('veActiveStart');
    const inEnd = document.getElementById('veActiveEnd');
    const durTag = document.getElementById('veActiveDurTag');
    const roiBadge = document.getElementById('veActiveRoiBadge');

    if (!seg) {
        if (title) title.innerText = "No Active Zone";
        if (inStart) inStart.value = "00:00.000";
        if (inEnd) inEnd.value = "00:00.000";
        if (durTag) durTag.innerText = "(0.00s)";
        if (roiBadge) roiBadge.innerText = "ROI: None";
        return;
    }

    const idx = patchSegments.findIndex(s => s.id === seg.id);
    if (title) title.innerText = `Zone ${idx + 1}`;
    if (inStart) inStart.value = formatTimeMs(seg.start);
    if (inEnd) inEnd.value = formatTimeMs(seg.end);
    if (durTag) durTag.innerText = `(${(seg.end - seg.start).toFixed(2)}s)`;

    const roi = seg.roi || [patchRegion.x1, patchRegion.y1, patchRegion.x2, patchRegion.y2];
    if (roiBadge) roiBadge.innerText = `ROI: [${roi.map(v => v.toFixed(2)).join(', ')}]`;
}

function veOnActiveTimeInput(field, val) {
    if (!activePatchSegmentId) return;
    const seg = patchSegments.find(s => s.id === activePatchSegmentId);
    if (!seg) return;

    const parsed = parseTimeMs(val);
    if (field === 'start') {
        seg.start = Math.max(0, Math.min(seg.end - 0.1, parsed));
    } else {
        seg.end = Math.max(seg.start + 0.1, Math.min(patchVideoDuration || 99999, parsed));
    }
    seg.start = parseFloat(seg.start.toFixed(3));
    seg.end = parseFloat(seg.end.toFixed(3));

    updateActiveZoneBar(seg);
    renderVeTimelineClips();
}

function renderVeTimelineClips() {
    const container = document.getElementById('veClipsContainer');
    if (!container || patchVideoDuration <= 0) return;

    container.innerHTML = '';
    patchSegments.sort((a, b) => a.start - b.start);

    patchSegments.forEach((seg, idx) => {
        const isActive = (seg.id === activePatchSegmentId);
        const leftPct = (seg.start / patchVideoDuration) * 100;
        const widthPct = ((seg.end - seg.start) / patchVideoDuration) * 100;

        const clip = document.createElement('div');
        clip.className = `ve-clip ${isActive ? 'active-clip' : ''}`;
        clip.style.left = `${leftPct}%`;
        clip.style.width = `${Math.max(1.2, widthPct)}%`;
        clip.dataset.segId = seg.id;

        // Left Trim Handle
        const trimLeft = document.createElement('div');
        trimLeft.className = 've-trim-handle ve-trim-left';
        trimLeft.title = 'Drag to adjust Start time';

        // Clip Center Body
        const body = document.createElement('div');
        body.className = 've-clip-body';
        const dur = (seg.end - seg.start).toFixed(1);
        body.innerText = `#${idx + 1} (${dur}s)`;
        body.title = `Zone ${idx + 1}: ${formatTimeMs(seg.start)} → ${formatTimeMs(seg.end)}`;

        // Right Trim Handle
        const trimRight = document.createElement('div');
        trimRight.className = 've-trim-handle ve-trim-right';
        trimRight.title = 'Drag to adjust End time';

        clip.appendChild(trimLeft);
        clip.appendChild(body);
        clip.appendChild(trimRight);

        // Clip event handlers
        clip.addEventListener('pointerdown', (e) => {
            selectPatchSegment(seg.id, false);

            const trackRect = document.getElementById('veTimelineTrack').getBoundingClientRect();
            const clickPct = Math.max(0, Math.min(1, (e.clientX - trackRect.left) / trackRect.width));
            const targetSec = clickPct * patchVideoDuration;

            timelineDragInitial = {
                start: seg.start,
                end: seg.end,
                pointerX: e.clientX,
                trackLeft: trackRect.left,
                trackWidth: trackRect.width
            };
            timelineDragSegId = seg.id;

            if (e.target.classList.contains('ve-trim-left')) {
                timelineDragMode = 'trim-left';
                veSeekTo(seg.start);
            } else if (e.target.classList.contains('ve-trim-right')) {
                timelineDragMode = 'trim-right';
                veSeekTo(seg.end);
            } else {
                timelineDragMode = 'clip-press';
                veSeekTo(targetSec);
            }

            e.stopPropagation();
            const timelineBody = document.getElementById('veTimelineBody');
            if (timelineBody) timelineBody.setPointerCapture(e.pointerId);
        });

        container.appendChild(clip);
    });
}

// Setup scrub and dragging events on the timeline
function setupTimelineEvents() {
    const track = document.getElementById('veTimelineTrack');
    const ruler = document.getElementById('veRuler');
    const body = document.getElementById('veTimelineBody');

    function handleScrub(e) {
        if (patchVideoDuration <= 0) return;
        const rect = track.getBoundingClientRect();
        const clientX = e.clientX;
        const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        const targetSec = pct * patchVideoDuration;
        veSeekTo(targetSec);
    }

    if (body) {
        body.addEventListener('pointerdown', (e) => {
            if (!e.target.closest('.ve-clip')) {
                timelineDragMode = 'scrub';
                handleScrub(e);
                body.setPointerCapture(e.pointerId);
            }
        });

        body.addEventListener('pointermove', (e) => {
            if (!timelineDragMode) return;

            if (timelineDragMode === 'scrub') {
                handleScrub(e);
                return;
            }

            if (timelineDragMode === 'clip-press') {
                const deltaX = Math.abs(e.clientX - timelineDragInitial.pointerX);
                if (deltaX > 6) {
                    timelineDragMode = 'clip-move';
                    const curClip = document.querySelector(`.ve-clip[data-seg-id="${timelineDragSegId}"]`);
                    if (curClip) curClip.classList.add('dragging');
                } else {
                    const clickPct = Math.max(0, Math.min(1, (e.clientX - timelineDragInitial.trackLeft) / timelineDragInitial.trackWidth));
                    veSeekTo(clickPct * patchVideoDuration);
                    return;
                }
            }

            const seg = patchSegments.find(s => s.id === timelineDragSegId);
            if (!seg || patchVideoDuration <= 0) return;

            const deltaX = e.clientX - timelineDragInitial.pointerX;
            const deltaSec = (deltaX / timelineDragInitial.trackWidth) * patchVideoDuration;

            if (timelineDragMode === 'clip-move') {
                const dur = timelineDragInitial.end - timelineDragInitial.start;
                let newStart = Math.max(0, Math.min(patchVideoDuration - dur, timelineDragInitial.start + deltaSec));
                let newEnd = newStart + dur;

                seg.start = parseFloat(newStart.toFixed(3));
                seg.end = parseFloat(newEnd.toFixed(3));
                veSeekTo(seg.start);
            } else if (timelineDragMode === 'trim-left') {
                let newStart = Math.max(0, Math.min(seg.end - 0.2, timelineDragInitial.start + deltaSec));
                seg.start = parseFloat(newStart.toFixed(3));
                veSeekTo(seg.start);
            } else if (timelineDragMode === 'trim-right') {
                let newEnd = Math.max(seg.start + 0.2, Math.min(patchVideoDuration, timelineDragInitial.end + deltaSec));
                seg.end = parseFloat(newEnd.toFixed(3));
                veSeekTo(seg.end);
            }

            updateActiveZoneBar(seg);
            renderVeTimelineClips();
        });

        const stopDrag = (e) => {
            if (timelineDragMode) {
                timelineDragMode = null;
                timelineDragSegId = null;
                document.querySelectorAll('.ve-clip.dragging').forEach(c => c.classList.remove('dragging'));
            }
        };

        body.addEventListener('pointerup', stopDrag);
        body.addEventListener('pointercancel', stopDrag);
    }
}

// ── Export Payload for startBatch('scramble') ────────────────────────────────

function getSpatialPatchConfig() {
    const isEnabled = document.getElementById('enableSpatialZones') ? document.getElementById('enableSpatialZones').checked : false;
    if (!isEnabled) {
        return {
            enabled: false,
            patch_roi: null,
            patch_segments: [],
            patch_intervals: [],
            roi_invert: false,
            optical_markers: false,
            marker_placement: 'outside'
        };
    }

    const roiInvert = document.getElementById('patchRoiInvert') ? document.getElementById('patchRoiInvert').checked : false;
    const optMarkers = document.getElementById('patchOpticalMarkers') ? document.getElementById('patchOpticalMarkers').checked : false;
    const optPlacement = document.getElementById('patchMarkerPlacement') ? document.getElementById('patchMarkerPlacement').value : 'outside';

    const globalRoi = [patchRegion.x1, patchRegion.y1, patchRegion.x2, patchRegion.y2];

    const segs = patchSegments.map(s => ({
        start: s.start,
        end: s.end,
        roi: s.roi || globalRoi,
        invert: roiInvert
    }));

    const intervals = patchSegments.map(s => [s.start, s.end]);

    return {
        enabled: true,
        patch_roi: globalRoi,
        patch_segments: segs,
        patch_intervals: intervals,
        roi_invert: roiInvert,
        optical_markers: optMarkers,
        marker_placement: optPlacement
    };
}

// --- Image Tab Zone Preview Controller ---
let imgPatchBoxCoords = { x1: 0.20, y1: 0.20, x2: 0.80, y2: 0.80 };
let imgPatchInteractionMode = 'move'; // 'move' or 'resize'
let imgIsDragging = false;
let imgDragHandle = null;
let imgDragStart = { x: 0, y: 0, box: null };

// 1. Listen for uploads in the image tab
document.addEventListener('DOMContentLoaded', () => {
    const imgUpload = document.getElementById('imageUpload');
    if (imgUpload) {
        imgUpload.addEventListener('change', function(e) {
            if (this.files && this.files.length > 0) {
                loadImgPatchPreview(this.files[0]);
            }
        });
    }

    setupImgPatchBoxInteractions();
});

// 2. Load the uploaded image into the preview container
function loadImgPatchPreview(file) {
    const previewImg = document.getElementById('imgPatchPreview');
    const emptyNotice = document.getElementById('imgPatchEmptyNotice');
    const regionBox = document.getElementById('imgPatchRegionBox');
    if (!previewImg) return;

    const url = URL.createObjectURL(file);
    previewImg.onload = () => {
        emptyNotice.style.display = 'none';
        previewImg.style.display = 'block';
        regionBox.classList.remove('hidden');
        updateImgRegionBoxDOM();
    };
    previewImg.src = url;
}

// 3. UI toggle helper
function onEnableImgSpatialZonesToggle(enabled) {
    const header = document.getElementById('imgSpatialZonesCollapseHeader');
    const content = document.getElementById('imgSpatialZonesCollapseContent');
    if (!enabled) {
        header.classList.add('disabled');
        header.classList.remove('active');
        content.classList.add('hidden');
    } else {
        header.classList.remove('disabled');
        header.classList.add('active');
        content.classList.remove('hidden');
        // Refresh position on expand
        setTimeout(updateImgRegionBoxDOM, 50);
    }
}

// 4. Update the green box DOM coordinates and inputs
function updateImgRegionBoxDOM() {
    const box = document.getElementById('imgPatchRegionBox');
    if (!box) return;

    box.style.left = (imgPatchBoxCoords.x1 * 100) + '%';
    box.style.top = (imgPatchBoxCoords.y1 * 100) + '%';
    box.style.width = ((imgPatchBoxCoords.x2 - imgPatchBoxCoords.x1) * 100) + '%';
    box.style.height = ((imgPatchBoxCoords.y2 - imgPatchBoxCoords.y1) * 100) + '%';

    const inX1 = document.getElementById('imgCoordX1');
    const inY1 = document.getElementById('imgCoordY1');
    const inX2 = document.getElementById('imgCoordX2');
    const inY2 = document.getElementById('imgCoordY2');
    if (inX1) inX1.value = imgPatchBoxCoords.x1.toFixed(2);
    if (inY1) inY1.value = imgPatchBoxCoords.y1.toFixed(2);
    if (inX2) inX2.value = imgPatchBoxCoords.x2.toFixed(2);
    if (inY2) inY2.value = imgPatchBoxCoords.y2.toFixed(2);
}

function onManualImgCoordInput() {
    let x1 = parseFloat(document.getElementById('imgCoordX1').value) || 0;
    let y1 = parseFloat(document.getElementById('imgCoordY1').value) || 0;
    let x2 = parseFloat(document.getElementById('imgCoordX2').value) || 1;
    let y2 = parseFloat(document.getElementById('imgCoordY2').value) || 1;

    imgPatchBoxCoords = {
        x1: Math.max(0, Math.min(x1, x2 - 0.05)),
        y1: Math.max(0, Math.min(y1, y2 - 0.05)),
        x2: Math.min(1, Math.max(x2, x1 + 0.05)),
        y2: Math.min(1, Math.max(y2, y1 + 0.05))
    };
    imgPatchBoxCoords = applyOutsideMarkerLimits(imgPatchBoxCoords, imgOutsideMarkerMargin());
    updateImgRegionBoxDOM();
}

function setImgPatchInteractionMode(mode) {
    imgPatchInteractionMode = mode;
    const btnMove = document.getElementById('imgPatchToolMove');
    const btnResize = document.getElementById('imgPatchToolResize');
    if (btnMove) btnMove.classList.toggle('active', mode === 'move');
    if (btnResize) btnResize.classList.toggle('active', mode === 'resize');

    // Scope to the IMAGE stage only so the Video tab handles are unaffected
    const container = document.getElementById('imgPatchPreviewContainer');
    const handles = container ? container.querySelectorAll('.patch-resize-handle') : document.querySelectorAll('#imgPatchRegionBox .patch-resize-handle');
    handles.forEach(h => {
        h.style.display = (mode === 'move') ? 'none' : 'block';
    });
}

function setImgPatchFullscreen() {
    imgPatchBoxCoords = { x1: 0, y1: 0, x2: 1, y2: 1 };
    imgPatchBoxCoords = applyOutsideMarkerLimits(imgPatchBoxCoords, imgOutsideMarkerMargin());
    updateImgRegionBoxDOM();
}

function resetImgPatchBoxToCenter() {
    imgPatchBoxCoords = { x1: 0.20, y1: 0.20, x2: 0.80, y2: 0.80 };
    updateImgRegionBoxDOM();
}

// 5. Setup pointer dragging and resizing.
// Uses the same pointer-event + pointer-capture engine as the Video tab
// (patchRegionBox): press on the box moves it, press on a corner/edge
// handle resizes it. mousedown-only tracking was unreliable here because
// the preview <img> and overlay badge steal mouse capture on some browsers.
let imgInteractionType = null; // 'move' | 'resize'
function setupImgPatchBoxInteractions() {
    const container = document.getElementById('imgPatchPreviewContainer');
    const box = document.getElementById('imgPatchRegionBox');
    if (!container || !box) return;

    box.addEventListener('pointerdown', function(e) {
        const target = e.target && e.target.getAttribute ? e.target : null;
        const handle = target ? target.getAttribute('data-handle') : null;
        if (handle) {
            imgInteractionType = 'resize';
            imgDragHandle = handle;
            box.classList.add('resizing-active');
        } else {
            imgInteractionType = 'move';
            imgDragHandle = null;
            box.classList.add('moving-active');
        }
        imgIsDragging = true;
        imgDragStart = {
            x: e.clientX,
            y: e.clientY,
            box: { ...imgPatchBoxCoords }
        };
        e.stopPropagation();
        e.preventDefault();
        try { box.setPointerCapture(e.pointerId); } catch (err) {}
    });

    box.addEventListener('pointermove', function(e) {
        if (!imgIsDragging) return;
        const rect = container.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;

        const dx = (e.clientX - imgDragStart.x) / rect.width;
        const dy = (e.clientY - imgDragStart.y) / rect.height;
        const b = imgDragStart.box;

        if (imgInteractionType === 'resize' && imgDragHandle) {
            // Resizing via handle
            if (imgDragHandle.includes('w')) imgPatchBoxCoords.x1 = Math.max(0, Math.min(b.x1 + dx, b.x2 - 0.05));
            if (imgDragHandle.includes('e')) imgPatchBoxCoords.x2 = Math.min(1, Math.max(b.x2 + dx, b.x1 + 0.05));
            if (imgDragHandle.includes('n')) imgPatchBoxCoords.y1 = Math.max(0, Math.min(b.y1 + dy, b.y2 - 0.05));
            if (imgDragHandle.includes('s')) imgPatchBoxCoords.y2 = Math.min(1, Math.max(b.y2 + dy, b.y1 + 0.05));
        } else {
            // Moving the entire box
            const w = b.x2 - b.x1;
            const h = b.y2 - b.y1;
            let nx1 = Math.max(0, Math.min(b.x1 + dx, 1 - w));
            let ny1 = Math.max(0, Math.min(b.y1 + dy, 1 - h));
            imgPatchBoxCoords.x1 = nx1;
            imgPatchBoxCoords.y1 = ny1;
            imgPatchBoxCoords.x2 = nx1 + w;
            imgPatchBoxCoords.y2 = ny1 + h;
        }

        imgPatchBoxCoords = applyOutsideMarkerLimits(imgPatchBoxCoords, imgOutsideMarkerMargin());

        updateImgRegionBoxDOM();
    });

    const endImgInteraction = function() {
        if (!imgIsDragging) return;
        imgIsDragging = false;
        imgDragHandle = null;
        imgInteractionType = null;
        box.classList.remove('moving-active', 'resizing-active');
    };

    box.addEventListener('pointerup', endImgInteraction);
    box.addEventListener('pointercancel', endImgInteraction);
}
