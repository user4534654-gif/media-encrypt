
let activePreviewTarget = 'external'; 
let durBg = 10;      
let durCenter = 3;   
function initVisualPreview() {
    const centerSizeSelect = document.getElementById('center_size') || document.getElementById('img_center_size');
    if (centerSizeSelect) {
        centerSizeSelect.addEventListener('change', function() {
            updateCenterOverlaySize(this.value);
        });
    }
    const videoEncModeSelect = document.getElementById('video_encrypt_mode') || document.getElementById('img_video_encrypt_mode');
    if (videoEncModeSelect) {
        videoEncModeSelect.addEventListener('change', function() {
            syncEncBadgesFromMode(this.value);
        });
    }
    const outerEndSelect = document.getElementById('outer_end_action');
    if (outerEndSelect) {
        outerEndSelect.addEventListener('change', function() {
            updateTimelineVisualization();
        });
    }
    const centerEndSelect = document.getElementById('center_end_action');
    if (centerEndSelect) {
        centerEndSelect.addEventListener('change', function() {
            updateTimelineVisualization();
        });
    }
    const audMethodSelect = document.getElementById('v_aud_method') || document.getElementById('aud_method');
    if (audMethodSelect) {
        audMethodSelect.addEventListener('change', function() {
            updateTimelineVisualization();
        });
    }
    const mediaUpload = document.getElementById('mediaUpload');
    if (mediaUpload) {
        mediaUpload.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                probeFileDuration(e.target.files[0], function(d) {
                    if (d > 0) durBg = Math.round(d);
                    updateTimelineVisualization();
                });
            }
        });
    }
    const centerVideoUpload = document.getElementById('centerVideoUpload');
    if (centerVideoUpload) {
        centerVideoUpload.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                probeFileDuration(e.target.files[0], function(d) {
                    if (d > 0) durCenter = Math.round(d);
                    updateTimelineVisualization();
                });
            }
        });
    }
    updateTimelineVisualization();
}
function selectPreviewTarget(target, event) {
    if (event) event.stopPropagation();
    activePreviewTarget = target;
    const bgBox = document.getElementById('previewBgBox');
    const centerBox = document.getElementById('previewCenterBox');
    const badge = document.getElementById('previewTargetBadge');
    const modeSelect = document.getElementById('video_encrypt_mode') || document.getElementById('img_video_encrypt_mode');
    if (target === 'center') {
        if (centerBox) centerBox.classList.add('active-selection');
        if (bgBox) bgBox.classList.remove('active-selection');
        if (badge) {
            badge.innerText = 'Target: Center Overlay (Red)';
            badge.style.background = 'rgba(255, 59, 48, 0.12)';
            badge.style.color = '#ff3b30';
            badge.style.borderColor = 'rgba(255, 59, 48, 0.3)';
        }
        if (modeSelect && modeSelect.value === 'external') {
            modeSelect.value = 'center';
            syncEncBadgesFromMode('center');
        }
    } else {
        if (bgBox) bgBox.classList.add('active-selection');
        if (centerBox) centerBox.classList.remove('active-selection');
        if (badge) {
            badge.innerText = 'Target: Background (Blue)';
            badge.style.background = 'rgba(0, 122, 255, 0.12)';
            badge.style.color = '#007aff';
            badge.style.borderColor = 'rgba(0, 122, 255, 0.3)';
        }
        if (modeSelect && modeSelect.value === 'center') {
            modeSelect.value = 'external';
            syncEncBadgesFromMode('external');
        }
    }
}
function updateCenterOverlaySize(val) {
    const centerBox = document.getElementById('previewCenterBox');
    if (!centerBox) return;
    centerBox.classList.remove('size-1-4', 'size-2-4', 'size-3-4');
    if (val === '2/4') {
        centerBox.classList.add('size-2-4');
    } else if (val === '3/4') {
        centerBox.classList.add('size-3-4');
    } else {
        centerBox.classList.add('size-1-4');
    }
}
function syncEncBadgesFromMode(mode) {
    const bgBadge = document.getElementById('bgEncStatusBadge');
    const centerBadge = document.getElementById('centerEncStatusBadge');
    if (!bgBadge || !centerBadge) return;
    if (mode === 'center') {
        bgBadge.innerText = '🔓 Untouched';
        bgBadge.style.color = '#333';
        centerBadge.innerText = '🔒 Encrypted';
        centerBadge.style.color = '#d70015';
    } else if (mode === 'both') {
        bgBadge.innerText = '🔒 Encrypted';
        bgBadge.style.color = '#0056b3';
        centerBadge.innerText = '🔒 Encrypted';
        centerBadge.style.color = '#d70015';
    } else {
        bgBadge.innerText = '🔒 Encrypted';
        bgBadge.style.color = '#0056b3';
        centerBadge.innerText = '🔓 Untouched';
        centerBadge.style.color = '#333';
    }
}
function updateTrackRouting(channel, source) {
    const selectElem = document.getElementById(`track${channel}SourceSelect`);
    const badgeElem = document.getElementById(`badge${channel}`);
    if (selectElem && badgeElem) {
        if (source === 'center') {
            selectElem.className = 'track-source-select red-source';
            badgeElem.className = 'channel-badge red-badge';
        } else {
            selectElem.className = 'track-source-select blue-source';
            badgeElem.className = 'channel-badge blue-badge';
        }
    }
    const sourceL = document.getElementById('trackLSourceSelect') ? document.getElementById('trackLSourceSelect').value : 'background';
    const sourceR = document.getElementById('trackRSourceSelect') ? document.getElementById('trackRSourceSelect').value : 'center';
    const dualTrackElem = document.getElementById('dual_track');
    if (dualTrackElem) {
        dualTrackElem.checked = (sourceL !== sourceR);
    }
    updateTimelineVisualization();
}
function updateTrackEncState(channel, isEncrypted) {
    updateTimelineVisualization();
}
function probeFileDuration(file, callback) {
    const url = URL.createObjectURL(file);
    const media = document.createElement(file.type.startsWith('audio') ? 'audio' : 'video');
    media.preload = 'metadata';
    media.onloadedmetadata = function() {
        URL.revokeObjectURL(url);
        callback(media.duration);
    };
    media.onerror = function() {
        URL.revokeObjectURL(url);
        callback(10);
    };
    media.src = url;
}
function updateTimelineVisualization() {
    const audioWrapper = document.getElementById('audioTimelineWrapper');
    if (typeof activeMediaType !== 'undefined' && activeMediaType === 'image') {
        if (audioWrapper) audioWrapper.style.display = 'none';
        return;
    } else {
        if (audioWrapper) audioWrapper.style.display = 'block';
    }
    const centerEndSelect = document.getElementById('center_end_action');
    const centerEndAction = centerEndSelect ? centerEndSelect.value : 'loop'; 
    const outerEndSelect = document.getElementById('outer_end_action');
    const outerEndAction = outerEndSelect ? outerEndSelect.value : 'stop'; 
    const maxDuration = Math.max(durBg, durCenter, 1);
    renderTrackBar('L', 'background', durBg, durCenter, maxDuration, outerEndAction, centerEndAction);
    renderTrackBar('R', 'center', durBg, durCenter, maxDuration, outerEndAction, centerEndAction);
}
function renderTrackBar(chName, source, durBgVal, durCenterVal, totalMaxDur, outerEndAction, centerEndAction) {
    const activeSeg = document.getElementById(`track${chName}ActiveSeg`);
    const activeLabel = document.getElementById(`track${chName}ActiveLabel`);
    const endSeg = document.getElementById(`track${chName}EndSeg`);
    const endLabel = document.getElementById(`track${chName}EndLabel`);
    const ticks = document.getElementById(`track${chName}Ticks`);
    if (!activeSeg || !activeLabel || !endSeg || !endLabel || !ticks) return;
    ticks.innerHTML = '';
    const trackDur = (source === 'center') ? durCenterVal : durBgVal;
    const trackEndAction = (source === 'center') ? centerEndAction : outerEndAction;
    const remDur = totalMaxDur - trackDur;
    const isCenter = (source === 'center');
    activeSeg.className = 'track-active-segment';
    if (isCenter) {
        activeSeg.classList.add('red-segment');
    } else {
        activeSeg.classList.add('blue-segment');
    }
    const titleText = isCenter ? 'Center Overlay Video' : 'Background Video';
    if (remDur <= 0) {
        activeSeg.classList.add('full-width');
        activeSeg.style.width = '100%';
        activeLabel.innerText = `${titleText} (${trackDur}s)`;
        endSeg.classList.add('hidden');
        endSeg.style.width = '0%';
    } else {
        const activePct = Math.max(10, Math.min(90, Math.round((trackDur / totalMaxDur) * 100)));
        const endPct = 100 - activePct;
        activeSeg.style.width = activePct + '%';
        activeLabel.innerText = `${titleText} (${trackDur}s)`;
        endSeg.classList.remove('hidden');
        endSeg.style.width = endPct + '%';
        endSeg.className = 'track-end-segment';
        if (trackEndAction === 'loop') {
            endSeg.classList.add('loop-end');
            endLabel.innerText = `Looped (+${remDur}s)`;
        } else if (trackEndAction === 'freeze') {
            if (isCenter) {
                endSeg.classList.add('pale-red-end');
            } else {
                endSeg.classList.add('pale-blue-end');
            }
            endLabel.innerText = `Frozen (+${remDur}s)`;
        } else if (trackEndAction === 'black') {
            endSeg.classList.add('black-end');
            endLabel.innerText = `Black Screen (+${remDur}s)`;
        } else { 
            endSeg.classList.add('stop-end');
            endLabel.innerText = `Ended (+${remDur}s)`;
        }
    }
    const stepCount = Math.min(totalMaxDur, 10);
    for (let i = 1; i <= stepCount; i++) {
        const tick = document.createElement('div');
        tick.className = 'timeline-tick-mark';
        ticks.appendChild(tick);
    }
}
function updateVolBgLabel(val) {
    const valElem = document.getElementById('vol_factor_bg_val');
    if (valElem) valElem.innerText = val + '%';
    const mainVolSlider = document.getElementById('vol_factor_slider');
    const mainVolVal = document.getElementById('vol_factor_val');
    if (mainVolSlider) mainVolSlider.value = val;
    if (mainVolVal) mainVolVal.innerText = val + '%';
}
function updateVolCenterLabel(val) {
    const valElem = document.getElementById('vol_factor_center_val');
    if (valElem) valElem.innerText = val + '%';
}
document.addEventListener('DOMContentLoaded', function() {
    initVisualPreview();
});
