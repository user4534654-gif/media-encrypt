
let patchVideoDuration = 0;
let patchSegments = [];
let patchNextId = 1;
let patchBaseFile = null;
let patchCenterFile = null;
let patchMode = 'normal'; 
let isDraggingHandle = false;
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
document.addEventListener('DOMContentLoaded', () => {
    const videoUpload = document.getElementById('patchVideoUpload');
    const centerUpload = document.getElementById('patchCenterUpload');
    const player = document.getElementById('patchVideoPlayer');
    const track = document.getElementById('patchTimelineTrack');
    if (videoUpload) {
        videoUpload.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                loadPatchVideoFile(e.target.files[0]);
            }
        });
    }
    if (centerUpload) {
        centerUpload.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                patchCenterFile = e.target.files[0];
                renderPatchFileList('patchCenterFileList', [patchCenterFile.name]);
            }
        });
    }
    if (player) {
        player.addEventListener('loadedmetadata', () => {
            patchVideoDuration = player.duration || 0;
            const durLabel = document.getElementById('patchDurationLabel');
            if (durLabel) durLabel.innerText = formatTimeMs(patchVideoDuration);
            if (patchSegments.length === 0 && patchVideoDuration > 0) {
                const segEnd = Math.min(patchVideoDuration, Math.max(3.0, patchVideoDuration * 0.3));
                addPatchSegment(0, segEnd);
            } else {
                renderPatchTimeline();
            }
        });
        player.addEventListener('timeupdate', () => {
            if (isDraggingHandle) return;
            const cur = player.currentTime || 0;
            const overlay = document.getElementById('patchPlayerOverlay');
            if (overlay) {
                overlay.innerText = `${formatTimeMs(cur)} / ${formatTimeMs(patchVideoDuration)}`;
            }
            const playhead = document.getElementById('patchPlayhead');
            if (playhead && patchVideoDuration > 0) {
                const pct = (cur / patchVideoDuration) * 100;
                playhead.style.left = `${Math.min(100, Math.max(0, pct))}%`;
            }
        });
        player.addEventListener('play', () => {
            const btn = document.getElementById('patchPlayPauseBtn');
            if (btn) btn.innerText = "⏸ Pause";
        });
        player.addEventListener('pause', () => {
            const btn = document.getElementById('patchPlayPauseBtn');
            if (btn) btn.innerText = "▶ Play";
        });
    }
    if (track) {
        track.addEventListener('click', (e) => {
            if (isDraggingHandle || patchVideoDuration <= 0) return;
            const rect = track.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const pct = Math.max(0, Math.min(1, clickX / rect.width));
            const targetSec = pct * patchVideoDuration;
            if (player) player.currentTime = targetSec;
        });
    }
});
function loadPatchVideoFile(file) {
    patchBaseFile = file;
    renderPatchFileList('patchFileList', [file.name]);
    const player = document.getElementById('patchVideoPlayer');
    const editorGroup = document.getElementById('patchEditorGroup');
    if (player) {
        player.src = URL.createObjectURL(file);
        player.load();
    }
    if (editorGroup) {
        editorGroup.style.display = 'block';
    }
}
function renderPatchFileList(containerId, filenames) {
    const list = document.getElementById(containerId);
    if (!list) return;
    list.innerHTML = '';
    filenames.forEach(fn => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `<span>📹 <strong>${fn}</strong></span>`;
        list.appendChild(item);
    });
}
function setPatchMode(mode) {
    patchMode = mode;
    const normBtn = document.getElementById('patchModeNormal');
    const centBtn = document.getElementById('patchModeCenter');
    const centSec = document.getElementById('patchCenterSection');
    if (normBtn) normBtn.classList.toggle('active', mode === 'normal');
    if (centBtn) centBtn.classList.toggle('active', mode === 'center');
    if (centSec) centSec.classList.toggle('hidden', mode !== 'center');
}
function patchTogglePlay() {
    const player = document.getElementById('patchVideoPlayer');
    if (!player) return;
    if (player.paused) player.play();
    else player.pause();
}
function patchSeekRelative(delta) {
    const player = document.getElementById('patchVideoPlayer');
    if (!player) return;
    player.currentTime = Math.max(0, Math.min(patchVideoDuration, player.currentTime + delta));
}
function addPatchSegment(startSec, endSec) {
    if (patchVideoDuration > 0) {
        startSec = Math.max(0, Math.min(patchVideoDuration, startSec));
        endSec = Math.max(startSec + 0.05, Math.min(patchVideoDuration, endSec));
    }
    const seg = {
        id: patchNextId++,
        start: parseFloat(startSec.toFixed(3)),
        end: parseFloat(endSec.toFixed(3))
    };
    patchSegments.push(seg);
    renderPatchTimeline();
}
function addPatchSegmentAtCurrent() {
    const player = document.getElementById('patchVideoPlayer');
    const cur = player ? player.currentTime : 0;
    const dur = patchVideoDuration || (cur + 5);
    const end = Math.min(dur, cur + 3.0);
    addPatchSegment(cur, end);
}
function addPatchSegmentCustom() {
    const lastSeg = patchSegments[patchSegments.length - 1];
    let start = lastSeg ? lastSeg.end + 1.0 : 0;
    if (patchVideoDuration > 0 && start >= patchVideoDuration) {
        start = Math.max(0, patchVideoDuration - 3.0);
    }
    const end = patchVideoDuration > 0 ? Math.min(patchVideoDuration, start + 3.0) : start + 3.0;
    addPatchSegment(start, end);
}
function removePatchSegment(id) {
    patchSegments = patchSegments.filter(s => s.id !== id);
    renderPatchTimeline();
}
function updatePatchSegmentTime(id, field, value) {
    const seg = patchSegments.find(s => s.id === id);
    if (!seg) return;
    const parsed = parseTimeMs(value);
    seg[field] = Math.max(0, Math.min(patchVideoDuration || 99999, parsed));
    if (seg.start > seg.end) {
        if (field === 'start') seg.end = seg.start + 0.1;
        else seg.start = Math.max(0, seg.end - 0.1);
    }
    seg.start = parseFloat(seg.start.toFixed(3));
    seg.end = parseFloat(seg.end.toFixed(3));
    renderPatchTimeline();
}
function previewPatchSegment(id) {
    const seg = patchSegments.find(s => s.id === id);
    const player = document.getElementById('patchVideoPlayer');
    if (!seg || !player) return;
    player.currentTime = seg.start;
    player.play();
    const checkStop = () => {
        if (player.currentTime >= seg.end || player.paused) {
            player.pause();
            player.removeEventListener('timeupdate', checkStop);
        }
    };
    player.addEventListener('timeupdate', checkStop);
}
function renderPatchTimeline() {
    const visualContainer = document.getElementById('patchSegmentsVisualContainer');
    const listContainer = document.getElementById('patchSegmentsList');
    if (!visualContainer || !listContainer) return;
    visualContainer.innerHTML = '';
    listContainer.innerHTML = '';
    patchSegments.sort((a, b) => a.start - b.start);
    patchSegments.forEach((seg, idx) => {
        if (patchVideoDuration > 0) {
            const leftPct = (seg.start / patchVideoDuration) * 100;
            const widthPct = ((seg.end - seg.start) / patchVideoDuration) * 100;
            const block = document.createElement('div');
            block.className = 'patch-segment-visual';
            block.style.position = 'absolute';
            block.style.left = `${leftPct}%`;
            block.style.width = `${Math.max(0.5, widthPct)}%`;
            block.style.top = '0';
            block.style.height = '100%';
            block.style.background = 'rgba(255, 59, 48, 0.45)';
            block.style.borderLeft = '2px solid #ff3b30';
            block.style.borderRight = '2px solid #ff3b30';
            block.style.boxSizing = 'border-box';
            block.title = `Segment #${idx + 1}: ${formatTimeMs(seg.start)} - ${formatTimeMs(seg.end)}`;
            const handleL = document.createElement('div');
            handleL.style.position = 'absolute';
            handleL.style.left = '-4px';
            handleL.style.top = '0';
            handleL.style.width = '8px';
            handleL.style.height = '100%';
            handleL.style.cursor = 'ew-resize';
            handleL.style.zIndex = '5';
            attachHandleDrag(handleL, seg.id, 'start');
            block.appendChild(handleL);
            const handleR = document.createElement('div');
            handleR.style.position = 'absolute';
            handleR.style.right = '-4px';
            handleR.style.top = '0';
            handleR.style.width = '8px';
            handleR.style.height = '100%';
            handleR.style.cursor = 'ew-resize';
            handleR.style.zIndex = '5';
            attachHandleDrag(handleR, seg.id, 'end');
            block.appendChild(handleR);
            visualContainer.appendChild(block);
        }
        const card = document.createElement('div');
        card.style.background = '#fff';
        card.style.border = '1px solid #e1e4e8';
        card.style.borderRadius = '8px';
        card.style.padding = '10px 12px';
        card.style.display = 'flex';
        card.style.justifyContent = 'space-between';
        card.style.alignItems = 'center';
        card.style.gap = '8px';
        card.style.flexWrap = 'wrap';
        const dur = (seg.end - seg.start).toFixed(3);
        card.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span class="channel-badge red-badge" style="background: #ff3b30; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 11px;">#${idx + 1}</span>
                <div style="display: flex; align-items: center; gap: 4px; font-family: monospace;">
                    <input type="text" value="${formatTimeMs(seg.start)}" onchange="updatePatchSegmentTime(${seg.id}, 'start', this.value)" class="ios-input" style="width: 95px; padding: 4px 6px; font-size: 12px; text-align: center;">
                    <span>→</span>
                    <input type="text" value="${formatTimeMs(seg.end)}" onchange="updatePatchSegmentTime(${seg.id}, 'end', this.value)" class="ios-input" style="width: 95px; padding: 4px 6px; font-size: 12px; text-align: center;">
                    <span style="font-size: 11px; color: #888;">(${dur}s)</span>
                </div>
            </div>
            <div style="display: flex; gap: 6px;">
                <button type="button" class="ios-btn-small" onclick="previewPatchSegment(${seg.id})" title="Preview this segment in player">▶ Preview</button>
                <button type="button" class="ios-btn-small" style="background: #ff3b30; color: #fff; border-color: #ff3b30;" onclick="removePatchSegment(${seg.id})" title="Delete segment">🗑️</button>
            </div>
        `;
        listContainer.appendChild(card);
    });
    if (patchSegments.length === 0) {
        listContainer.innerHTML = `<div style="text-align: center; color: #888; padding: 12px; font-size: 13px;">No patch segments added yet. Click <strong>"➕ Add Segment"</strong> to define encrypted regions.</div>`;
    }
}
function attachHandleDrag(handleEl, segId, handleType) {
    handleEl.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        e.preventDefault();
        isDraggingHandle = true;
        const track = document.getElementById('patchTimelineTrack');
        const rect = track.getBoundingClientRect();
        const onMouseMove = (moveEvent) => {
            const clientX = moveEvent.clientX;
            const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            const newSec = parseFloat((pct * patchVideoDuration).toFixed(3));
            const seg = patchSegments.find(s => s.id === segId);
            if (!seg) return;
            if (handleType === 'start') {
                seg.start = Math.min(newSec, Math.max(0, seg.end - 0.05));
            } else {
                seg.end = Math.max(newSec, Math.min(patchVideoDuration, seg.start + 0.05));
            }
            renderPatchTimeline();
        };
        const onMouseUp = () => {
            isDraggingHandle = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}
function startPatchEncryption() {
    if (!patchBaseFile) {
        alert("Please select a base video file first.");
        return;
    }
    if (patchSegments.length === 0) {
        alert("Please add at least one patch time segment to encrypt.");
        return;
    }
    if (patchMode === 'center' && !patchCenterFile) {
        alert("Please select a Center Video file or pick one from the Vault.");
        return;
    }
    const intervals = patchSegments.map(s => [s.start, s.end]);
    const formData = new FormData();
    formData.append('files', patchBaseFile);
    formData.append('action', 'scramble');
    formData.append('enc_video', 'true');
    formData.append('enc_audio', document.getElementById('patchEncAudio').checked ? 'true' : 'false');
    formData.append('cols', document.getElementById('patchCols').value || '10');
    formData.append('rows', document.getElementById('patchRows').value || '10');
    formData.append('sid', document.getElementById('patchSeed').value || '');
    formData.append('patch_intervals', JSON.stringify(intervals));
    formData.append('patch_engine', document.getElementById('patchEngine').value || 'seamless');
    if (patchMode === 'center') {
        formData.append('center_mode', 'true');
        if (patchCenterFile) {
            formData.append('center_file', patchCenterFile);
        }
        formData.append('center_size', document.getElementById('patchCenterSize').value || '1/4');
        formData.append('video_encrypt_mode', document.getElementById('patchVideoEncryptMode').value || 'external');
    }
    startBatchWithFormData(formData, 'scramble');
}
