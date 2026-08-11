
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
    const centerEndSelect = document.getElementById('center_end_action');
    const centerEndAction = centerEndSelect ? centerEndSelect.value : 'loop'; 
    const outerEndSelect = document.getElementById('outer_end_action');
    const outerEndAction = outerEndSelect ? outerEndSelect.value : 'stop'; 
    const trackLSelect = document.getElementById('trackLSourceSelect');
    const trackRSelect = document.getElementById('trackRSourceSelect');
    const sourceL = trackLSelect ? trackLSelect.value : 'background';
    const sourceR = trackRSelect ? trackRSelect.value : 'center';
    const encL = document.getElementById('trackLEncCheckbox') ? document.getElementById('trackLEncCheckbox').checked : true;
    const encR = document.getElementById('trackREncCheckbox') ? document.getElementById('trackREncCheckbox').checked : true;
    const audMethodSelect = document.getElementById('v_aud_method') || document.getElementById('aud_method');
    const activeMethod = audMethodSelect ? audMethodSelect.value : 'inversion';
    const maxDuration = Math.max(durBg, durCenter, 1);
    renderTrackBar('trackLBar', 'trackLLabel', 'trackLTicks', 'trackLMethodBadge', 'L', sourceL, encL, activeMethod, durBg, durCenter, maxDuration, outerEndAction, centerEndAction);
    renderTrackBar('trackRBar', 'trackRLabel', 'trackRTicks', 'trackRMethodBadge', 'R', sourceR, encR, activeMethod, durBg, durCenter, maxDuration, outerEndAction, centerEndAction);
}
function renderTrackBar(barId, labelId, ticksId, methodBadgeId, chName, source, isEncrypted, activeMethod, durBgVal, durCenterVal, totalMaxDur, outerEndAction, centerEndAction) {
    const bar = document.getElementById(barId);
    const label = document.getElementById(labelId);
    const ticks = document.getElementById(ticksId);
    const methodBadge = document.getElementById(methodBadgeId);
    if (!bar || !label || !ticks) return;
    if (methodBadge) {
        if (isEncrypted) {
            methodBadge.innerText = `[${activeMethod}]`;
            methodBadge.style.background = '#e0e0e0';
            methodBadge.style.color = '#333';
        } else {
            methodBadge.innerText = `[Clear]`;
            methodBadge.style.background = '#d4edda';
            methodBadge.style.color = '#155724';
        }
    }
    bar.className = 'track-timeline-bar';
    ticks.innerHTML = '';
    const trackDur = (source === 'center') ? durCenterVal : durBgVal;
    const trackEndAction = (source === 'center') ? centerEndAction : outerEndAction;
    if (source === 'center') {
        bar.classList.add('red-bar');
    } else {
        bar.classList.add('blue-bar');
    }
    let widthPct = Math.min(100, Math.round((trackDur / totalMaxDur) * 100));
    let statusText = `${chName} Track (${source === 'center' ? 'Center' : 'Background'}: ${trackDur}s)`;
    if (trackDur < totalMaxDur) {
        if (trackEndAction === 'loop') {
            widthPct = 100;
            bar.classList.add('loop-bar');
            statusText = `${chName} Track (${source === 'center' ? 'Center' : 'Background'}: ${trackDur}s Looped to ${totalMaxDur}s)`;
        } else if (trackEndAction === 'freeze') {
            widthPct = 100;
            if (source === 'center') {
                bar.classList.add('pale-red-bar');
            } else {
                bar.classList.add('pale-blue-bar');
            }
            statusText = `${chName} Track (${source === 'center' ? 'Center' : 'Background'}: ${trackDur}s -> Frozen Frame to ${totalMaxDur}s)`;
        } else if (trackEndAction === 'black') {
            widthPct = 100;
            bar.classList.add('black-bar');
            statusText = `${chName} Track (${source === 'center' ? 'Center' : 'Background'}: ${trackDur}s -> Black Screen to ${totalMaxDur}s)`;
        } else { 
            statusText = `${chName} Track (${source === 'center' ? 'Center' : 'Background'}: ${trackDur}s Ended)`;
        }
    }
    bar.style.width = widthPct + '%';
    label.innerText = statusText;
    const stepCount = Math.min(totalMaxDur, 10);
    for (let i = 1; i <= stepCount; i++) {
        const tick = document.createElement('div');
        tick.className = 'timeline-tick-mark';
        ticks.appendChild(tick);
    }
}
document.addEventListener('DOMContentLoaded', function() {
    initVisualPreview();
});
