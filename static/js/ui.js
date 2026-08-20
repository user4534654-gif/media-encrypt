const upload = document.getElementById('mediaUpload');
const centerUpload = document.getElementById('centerVideoUpload');
const imageUpload = document.getElementById('imageUpload');
const centerImageUpload = document.getElementById('centerImageUpload');
const audioUpload = document.getElementById('audioUpload');
const decryptUpload = document.getElementById('decryptUpload');
const encVideo = document.getElementById('encVideo');
const encAudio = document.getElementById('encAudio');
const vidSettings = document.getElementById('vidSettings');
const audSettings = document.getElementById('audSettings');
const encParams = document.getElementById('encryptionParams');
const exportSection = document.getElementById('exportSettings');
function updateVisibility() {
    if (encVideo) {
        encVideo.checked ? (vidSettings.classList.remove('hidden'), encParams.classList.remove('hidden')) : (vidSettings.classList.add('hidden'), encParams.classList.add('hidden'));
    }
    if (encAudio) {
        encAudio.checked ? audSettings.classList.remove('hidden') : audSettings.classList.add('hidden');
    }
    if (encVideo && encAudio && exportSection) {
        (!encVideo.checked && !encAudio.checked) ? exportSection.classList.add('hidden') : exportSection.classList.remove('hidden');
    }
}
if (encVideo) encVideo.addEventListener('change', updateVisibility);
if (encAudio) encAudio.addEventListener('change', updateVisibility);
function setRatio(w, h) {
    origRatio = w / h;
    const resWEl = document.getElementById('resW');
    const resHEl = document.getElementById('resH');
    if (resWEl) resWEl.placeholder = w + " (Orig)";
    if (resHEl) resHEl.placeholder = h + " (Orig)";
}
const resWInput = document.getElementById('resW');
const resHInput = document.getElementById('resH');
if (resWInput) {
    resWInput.addEventListener('input', function() {
        if (document.getElementById('aspectLock').checked && this.value) {
            const hInput = document.getElementById('resH');
            if (hInput) hInput.value = Math.round(this.value / origRatio);
        }
    });
}
if (resHInput) {
    resHInput.addEventListener('input', function() {
        if (document.getElementById('aspectLock').checked && this.value) {
            const wInput = document.getElementById('resW');
            if (wInput) wInput.value = Math.round(this.value * origRatio);
        }
    });
}
function setEncryptionMode(mode) {
    encryptionMode = mode;
    const normBtn = document.getElementById('modeNormal');
    const centBtn = document.getElementById('modeCenter');
    if (normBtn) normBtn.classList.toggle('active', mode === 'normal');
    if (centBtn) centBtn.classList.toggle('active', mode === 'center');
    const centerSection = document.getElementById('centerVideoSection');
    if (centerSection) {
        if (mode === 'center') centerSection.classList.remove('hidden');
        else centerSection.classList.add('hidden');
    }
    const dualTrackRow = document.getElementById('dualTrackRow');
    if (dualTrackRow) {
        if (mode === 'center') dualTrackRow.classList.remove('hidden');
        else {
            dualTrackRow.classList.add('hidden');
            const dualTrackCheck = document.getElementById('dual_track');
            if (dualTrackCheck) dualTrackCheck.checked = false;
        }
    }
    saveAllSettings();
}
function setImageEncryptionMode(mode) {
    imgEncryptionMode = mode;
    const normBtn = document.getElementById('imgModeNormal');
    const centBtn = document.getElementById('imgModeCenter');
    if (normBtn) normBtn.classList.toggle('active', mode === 'normal');
    if (centBtn) centBtn.classList.toggle('active', mode === 'center');
    const centerSection = document.getElementById('centerImageSection');
    if (centerSection) {
        if (mode === 'center') centerSection.classList.remove('hidden');
        else centerSection.classList.add('hidden');
    }
    saveAllSettings();
}
function setImageFormat(format) {
    if (format === '.jpeg') format = '.jpg';
    activeImageFormat = format;
    const fmtButtons = {
        'auto': 'imgFmtAuto',
        '.png': 'imgFmtPng',
        '.avif': 'imgFmtAvif',
        '.jpg': 'imgFmtJpeg',
        '.webp': 'imgFmtWebp'
    };
    Object.entries(fmtButtons).forEach(([fmt, id]) => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.toggle('active', fmt === format);
    });
    saveAllSettings();
}
function setMediaTypeTab(type) {
    activeMediaType = type;
    const vTab = document.getElementById('mediaTabVideo');
    const pTab = document.getElementById('mediaTabPatch');
    const iTab = document.getElementById('mediaTabImage');
    const aTab = document.getElementById('mediaTabAudio');
    if (vTab) vTab.classList.toggle('active', type === 'video');
    if (pTab) pTab.classList.toggle('active', type === 'patch');
    if (iTab) iTab.classList.toggle('active', type === 'image');
    if (aTab) aTab.classList.toggle('active', type === 'audio');
    const vStudio = document.getElementById('videoStudio');
    const pStudio = document.getElementById('patchStudio');
    const iStudio = document.getElementById('imageStudio');
    const aStudio = document.getElementById('audioStudio');
    if (vStudio) vStudio.classList.toggle('hidden', type !== 'video');
    if (pStudio) pStudio.classList.toggle('hidden', type !== 'patch');
    if (iStudio) iStudio.classList.toggle('hidden', type !== 'image');
    if (aStudio) aStudio.classList.toggle('hidden', type !== 'audio');
    saveAllSettings();
}
function switchMainTab(tab) {
    activeMainTab = tab;
    const encBtn = document.getElementById('tabBtnEncrypt');
    const decBtn = document.getElementById('tabBtnDecrypt');
    const vltBtn = document.getElementById('tabBtnVault');
    if (encBtn) encBtn.classList.toggle('active', tab === 'encrypt');
    if (decBtn) decBtn.classList.toggle('active', tab === 'decrypt');
    if (vltBtn) vltBtn.classList.toggle('active', tab === 'vault');
    const encCont = document.getElementById('tabContentEncrypt');
    const decCont = document.getElementById('tabContentDecrypt');
    const vltCont = document.getElementById('tabContentVault');
    if (encCont) encCont.classList.toggle('hidden', tab !== 'encrypt');
    if (decCont) decCont.classList.toggle('hidden', tab !== 'decrypt');
    if (vltCont) vltCont.classList.toggle('hidden', tab !== 'vault');
    if (tab === 'vault') {
        loadVault();
    }
}
function toggleTheme(isDark) {
    document.body.classList.toggle('ios-dark-theme', isDark);
    localStorage.setItem('ios-dark-theme', isDark ? 'true' : 'false');
    saveAllSettings();
}
function toggleFullscreen() {
    const btn = document.getElementById('fullscreenBtn');
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) {
        window.pywebview.api.toggle_fullscreen().then(isFullscreen => {
            if (btn) {
                btn.innerText = isFullscreen ? "Exit Fullscreen 🖥️" : "Fullscreen 🖥️";
            }
        }).catch(err => {
            console.error("Webview fullscreen error:", err);
        });
    } else {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen().then(() => {
                if (btn) btn.innerText = "Exit Fullscreen 🖥️";
            }).catch(err => {
                console.error("Error enabling fullscreen:", err);
            });
        } else {
            document.exitFullscreen().then(() => {
                if (btn) btn.innerText = "Fullscreen 🖥️";
            });
        }
    }
}
const decKeyInput = document.getElementById('decKey');
if (decKeyInput) {
    decKeyInput.addEventListener('input', function() {
        const val = this.value || '';
        const badge = document.getElementById('decKeyModeBadge');
        const patchBadge = document.getElementById('decKeyPatchBadge');
        const cleanVal = val.replace(/\s+/g, '');
        if (badge) {
            if (cleanVal.includes('|c') || cleanVal.includes('|c|')) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
        if (patchBadge) {
            if (cleanVal.includes('|patch:') || cleanVal.includes('|p:')) {
                patchBadge.classList.remove('hidden');
            } else {
                patchBadge.classList.add('hidden');
            }
        }
    });
}
function switchFolder(folder) {
    activeFolder = folder;
    const inTab = document.getElementById('folderTabInput');
    const encTab = document.getElementById('folderTabEncrypted');
    const decTab = document.getElementById('folderTabDecrypted');
    if (inTab) inTab.classList.toggle('active', folder === 'input');
    if (encTab) encTab.classList.toggle('active', folder === 'encrypted');
    if (decTab) decTab.classList.toggle('active', folder === 'decrypted');
    loadVault();
}
async function openActiveFolder() {
    await fetch('/api/open_folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder: activeFolder })
    });
}
if (upload) {
    upload.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const list = document.getElementById('fileList');
        if (list) list.innerText = files.map(f => f.name).join(', ');
        displayUploadVideoBitrate(files);
        if (!files.length) return;
        const url = URL.createObjectURL(files[0]);
        if (files[0].type.startsWith('video/')) {
            const vid = document.createElement('video');
            vid.onloadedmetadata = () => setRatio(vid.videoWidth, vid.videoHeight);
            vid.src = url;
        }
    });
}
function displayUploadVideoBitrate(files) {
    const infoEl = document.getElementById('uploadVideoBitrateInfo');
    if (!infoEl) return;
    const videoFiles = files.filter(f => f.type.startsWith('video/'));
    if (!videoFiles.length) {
        infoEl.style.display = 'none';
        infoEl.innerHTML = '';
        return;
    }
    infoEl.style.display = 'block';
    infoEl.innerHTML = 'Computing upload bitrate…';
    let pending = videoFiles.length;
    let rowsHtml = '';
    videoFiles.forEach(file => {
        const url = URL.createObjectURL(file);
        const vid = document.createElement('video');
        vid.preload = 'metadata';
        vid.onloadedmetadata = () => {
            if (vid.duration > 0 && file.size > 0) {
                const kbps = Math.max(1, Math.round((file.size * 8) / vid.duration / 1000));
                rowsHtml += `<div style="font-size: 12px; color: #007aff;">📊 ${file.name} — upload bitrate: ${kbps} kbps</div>`;
            }
            URL.revokeObjectURL(url);
            pending--;
            if (pending === 0) infoEl.innerHTML = rowsHtml;
        };
        vid.onerror = () => {
            URL.revokeObjectURL(url);
            pending--;
            if (pending === 0) infoEl.innerHTML = rowsHtml;
        };
        vid.src = url;
    });
}
if (centerUpload) {
    centerUpload.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const list = document.getElementById('centerFileList');
        if (list) list.innerText = files.map(f => f.name).join(', ');
    });
}
if (imageUpload) {
    imageUpload.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const list = document.getElementById('imageList');
        if (list) list.innerText = files.map(f => f.name).join(', ');
    });
}
if (centerImageUpload) {
    centerImageUpload.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const list = document.getElementById('centerImageList');
        if (list) list.innerText = files.map(f => f.name).join(', ');
    });
}
if (audioUpload) {
    audioUpload.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const list = document.getElementById('audioList');
        if (list) list.innerText = files.map(f => f.name).join(', ');
    });
}
if (decryptUpload) {
    decryptUpload.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        const list = document.getElementById('decryptFileList');
        if (list) list.innerText = files.map(f => f.name).join(', ');
    });
}
const bitSlider = document.getElementById('v_bit_slider');
const bitVal = document.getElementById('v_bit_val');
const bitLabel = document.getElementById('v_bit_label');
if (bitSlider && bitVal && bitLabel) {
    bitSlider.addEventListener('input', function() {
        bitVal.innerText = this.value + 'k';
        bitLabel.innerText = 'Video Bitrate: ' + this.value + 'k';
    });
}
const freqSlider = document.getElementById('carrier_freq_slider');
const freqVal = document.getElementById('carrier_freq_val');
const freqLabel = document.getElementById('carrier_freq_label');
if (freqSlider && freqVal && freqLabel) {
    freqSlider.addEventListener('input', function() {
        freqVal.innerText = this.value + ' Hz';
        freqLabel.innerText = 'Carrier Frequency: ' + this.value + ' Hz';
    });
}
function syncAudioSrLabel(which) {
    const slider = which === 'video' ? document.getElementById('a_sr_slider') : document.getElementById('audio_sr_slider');
    const val = which === 'video' ? document.getElementById('a_sr_val') : document.getElementById('audio_sr_val');
    if (slider && val) val.innerText = slider.value + ' Hz';
}
function toggleAudioSrAuto(isAuto, which) {
    const container = which === 'video' ? document.getElementById('aSrSliderContainer') : document.getElementById('audioSrSliderContainer');
    if (container) container.style.display = isAuto ? 'none' : 'flex';
    if (typeof saveAllSettings === 'function') saveAllSettings();
}
function getCodecBitrateConfig(codec) {
    const c = (codec || '').toLowerCase();
    if (c === 'libopus') {
        return { min: 32, max: 512, step: 32, def: 512, lossless: false };
    } else if (c === 'libmp3lame') {
        return { min: 32, max: 320, step: 32, def: 320, lossless: false };
    } else if (c === 'aac') {
        return { min: 32, max: 320, step: 32, def: 320, lossless: false };
    } else if (c === 'flac' || c === 'pcm_s16le') {
        return { min: 0, max: 0, step: 0, def: 0, lossless: true };
    } else {
        return { min: 32, max: 320, step: 32, def: 320, lossless: false };
    }
}
function onAudioCodecChanged(which) {
    const codecSelect = which === 'video' ? document.getElementById('a_codec') : document.getElementById('audio_codec');
    const slider = which === 'video' ? document.getElementById('a_bit_slider') : document.getElementById('audio_bit_slider');
    const valSpan = which === 'video' ? document.getElementById('a_bit_val') : document.getElementById('audio_bit_val');
    const label = which === 'video' ? document.getElementById('a_bit_label') : document.getElementById('audio_bit_label');
    const autoCheck = which === 'video' ? document.getElementById('a_bit_auto') : document.getElementById('audio_bit_auto');
    if (!codecSelect || !slider) return;
    const config = getCodecBitrateConfig(codecSelect.value);
    if (config.lossless) {
        slider.disabled = true;
        if (valSpan) valSpan.innerText = 'Lossless';
        if (label) label.innerHTML = 'Audio Bitrate: Lossless<span class="help-tip">❔<span class="tooltip-text">Selected codec is lossless/uncompressed (bitrate is N/A).</span></span>';
        if (autoCheck) autoCheck.disabled = true;
    } else {
        slider.disabled = false;
        slider.min = config.min;
        slider.max = config.max;
        slider.step = config.step;
        if (parseInt(slider.value) > config.max || parseInt(slider.value) < config.min || slider.value === '0') {
            slider.value = config.def;
        }
        if (valSpan) valSpan.innerText = slider.value + 'k';
        const isMax = parseInt(slider.value) === config.max;
        if (label) label.innerHTML = `Audio Bitrate: ${slider.value}k${isMax ? ' (Max)' : ''}<span class="help-tip">❔<span class="tooltip-text">Higher audio bitrate improves sound quality. Defaults to codec maximum.</span></span>`;
        if (autoCheck) autoCheck.disabled = false;
    }
    if (typeof saveAllSettings === 'function') saveAllSettings();
}
function syncAudioBitLabel(which) {
    const codecSelect = which === 'video' ? document.getElementById('a_codec') : document.getElementById('audio_codec');
    const slider = which === 'video' ? document.getElementById('a_bit_slider') : document.getElementById('audio_bit_slider');
    const valSpan = which === 'video' ? document.getElementById('a_bit_val') : document.getElementById('audio_bit_val');
    const label = which === 'video' ? document.getElementById('a_bit_label') : document.getElementById('audio_bit_label');
    if (!slider || !valSpan) return;
    valSpan.innerText = slider.value + 'k';
    const config = getCodecBitrateConfig(codecSelect ? codecSelect.value : 'auto');
    const isMax = parseInt(slider.value) === config.max;
    if (label) {
        label.innerHTML = `Audio Bitrate: ${slider.value}k${isMax ? ' (Max)' : ''}<span class="help-tip">❔<span class="tooltip-text">Higher audio bitrate improves sound quality. Defaults to codec maximum.</span></span>`;
    }
}
function toggleAudioBitAuto(isAuto, which) {
    const container = which === 'video' ? document.getElementById('aBitSliderContainer') : document.getElementById('audioBitSliderContainer');
    const label = which === 'video' ? document.getElementById('a_bit_label') : document.getElementById('audio_bit_label');
    if (container) container.style.display = isAuto ? 'none' : 'flex';
    if (label && isAuto) {
        label.innerHTML = `Audio Bitrate: Auto (Match Input)<span class="help-tip">❔<span class="tooltip-text">Preserves input audio bitrate or uses safe format defaults.</span></span>`;
    } else if (label) {
        syncAudioBitLabel(which);
    }
    if (typeof saveAllSettings === 'function') saveAllSettings();
}
const aBitSlider = document.getElementById('a_bit_slider');
if (aBitSlider) {
    aBitSlider.addEventListener('input', function() {
        syncAudioBitLabel('video');
    });
}
const audioBitSlider = document.getElementById('audio_bit_slider');
if (audioBitSlider) {
    audioBitSlider.addEventListener('input', function() {
        syncAudioBitLabel('audio');
    });
}
const aSrSlider = document.getElementById('a_sr_slider');
if (aSrSlider) {
    aSrSlider.addEventListener('input', function() {
        syncAudioSrLabel('video');
    });
}
const audioSrSlider = document.getElementById('audio_sr_slider');
if (audioSrSlider) {
    audioSrSlider.addEventListener('input', function() {
        syncAudioSrLabel('audio');
    });
}
const volSlider = document.getElementById('vol_factor_slider');
const volVal = document.getElementById('vol_factor_val');
const volLabel = document.getElementById('vol_factor_label');
if (volSlider && volVal && volLabel) {
    volSlider.addEventListener('input', function() {
        volVal.innerText = this.value + '%';
        volLabel.innerText = 'Encrypted Audio Volume: ' + this.value + '%';
    });
}
const audVolSlider = document.getElementById('aud_vol_factor_slider');
const audVolVal = document.getElementById('aud_vol_factor_val');
const audVolLabel = document.getElementById('aud_vol_factor_label');
if (audVolSlider && audVolVal && audVolLabel) {
    audVolSlider.addEventListener('input', function() {
        audVolVal.innerText = this.value + '%';
        audVolLabel.innerText = 'Encrypted Audio Volume: ' + this.value + '%';
    });
}
function toggleAudioMethodFields() {
    const method = document.getElementById('aud_method').value;
    const splitsRow = document.getElementById('aud_splits_row');
    const seedRow = document.getElementById('aud_seed_row');
    const carrierRow = document.getElementById('carrier_freq_row');
    if (method === 'band_scramble') {
        if (splitsRow) splitsRow.style.display = 'block';
        if (seedRow) seedRow.style.display = 'block';
        if (carrierRow) carrierRow.style.display = 'none';
    } else if (method === 'combined') {
        if (splitsRow) splitsRow.style.display = 'block';
        if (seedRow) seedRow.style.display = 'block';
        if (carrierRow) carrierRow.style.display = 'block';
    } else {
        if (splitsRow) splitsRow.style.display = 'none';
        if (seedRow) seedRow.style.display = 'none';
        if (carrierRow) carrierRow.style.display = 'block';
    }
}
function toggleVideoAudioMethodFields() {
    const method = document.getElementById('v_aud_method').value;
    const splitsRow = document.getElementById('v_aud_splits_row');
    if (method === 'band_scramble' || method === 'combined') {
        if (splitsRow) splitsRow.style.display = 'block';
    } else {
        if (splitsRow) splitsRow.style.display = 'none';
    }
}
function replaceEmojisInDOM(emojiMap) {
    const emojis = Object.keys(emojiMap);
    if (emojis.length === 0) return;
    const normalizedMap = {};
    const escapedPatterns = [];
    emojis.sort((a, b) => b.length - a.length);
    for (let e of emojis) {
        const base = e.replace(/\ufe0f/g, '');
        normalizedMap[base] = emojiMap[e];
        normalizedMap[base + '\ufe0f'] = emojiMap[e];
        const escapedBase = base.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        escapedPatterns.push(escapedBase + '\\ufe0f?');
    }
    const regex = new RegExp(`(${escapedPatterns.join('|')})`, 'gu');
    function walk(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.nodeValue;
            regex.lastIndex = 0;
            if (regex.test(text)) {
                const parent = node.parentNode;
                if (!parent || ['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT'].includes(parent.tagName)) return;
                regex.lastIndex = 0;
                const parts = text.split(regex);
                const fragment = document.createDocumentFragment();
                for (let part of parts) {
                    if (normalizedMap[part]) {
                        const img = document.createElement('img');
                        img.src = `/static/icons/${normalizedMap[part]}`;
                        img.className = 'custom-emoji-icon';
                        img.alt = part;
                        fragment.appendChild(img);
                    } else if (part) {
                        fragment.appendChild(document.createTextNode(part));
                    }
                }
                parent.replaceChild(fragment, node);
            }
        } else {
            const children = Array.from(node.childNodes);
            for (let child of children) {
                walk(child);
            }
        }
    }
    walk(document.body);
}
async function loadCustomIcons() {
    try {
        const response = await fetch('/api/icons');
        if (!response.ok) return;
        const emojiMap = await response.json();
        if (emojiMap && Object.keys(emojiMap).length > 0) {
            replaceEmojisInDOM(emojiMap);
            const observer = new MutationObserver((mutations) => {
                let check = false;
                for (let mutation of mutations) {
                    if (mutation.addedNodes.length > 0) {
                        check = true;
                        break;
                    }
                }
                if (check) {
                    replaceEmojisInDOM(emojiMap);
                }
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }
    } catch (e) {
        console.error("Error loading custom icons:", e);
    }
}
window.addEventListener('DOMContentLoaded', () => {
    loadAllSettings();
    initAutoSave();
    loadCustomIcons();
    switchMainTab('encrypt');
    switchFolder('input');
});
document.addEventListener('keydown', function(event) {
    if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === 'd') {
        event.preventDefault();
        fetch('/api/save_debug_log', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('Debug log saved successfully to: ' + data.path);
                } else {
                    alert('Failed to save debug log: ' + data.error);
                }
            })
            .catch(err => {
                console.error('Error saving debug log:', err);
                alert('Error sending request to save debug log: ' + err);
            });
    }
});
setInterval(() => {
    fetch('/api/heartbeat').catch(() => {});
}, 5000);
function toggleSection(triggerId, contentId) {
    const trigger = document.getElementById(triggerId);
    const content = document.getElementById(contentId);
    if (!trigger || !content) return;
    const isActive = trigger.classList.contains('active');
    if (isActive) {
        trigger.classList.remove('active');
        content.classList.add('hidden');
    } else {
        trigger.classList.add('active');
        content.classList.remove('hidden');
    }
    saveAllSettings();
}
let activeDownloadEventSources = {};
function closeTerminal(terminalId) {
    const term = document.getElementById(terminalId);
    if (term) term.classList.add('hidden');
    if (activeDownloadEventSources[terminalId]) {
        try { activeDownloadEventSources[terminalId].close(); } catch(e) {}
        delete activeDownloadEventSources[terminalId];
    }
}
function triggerUrlDownload(mediaType, isCenter = false) {
    let inputId = 'videoUrlInput';
    let termId = 'videoTerminal';
    let logId = 'videoTerminalLog';
    let defaultTool = 'yt-dlp';
    if (mediaType === 'video') {
        inputId = isCenter ? 'centerVideoUrlInput' : 'videoUrlInput';
        termId = isCenter ? 'centerVideoTerminal' : 'videoTerminal';
        logId = isCenter ? 'centerVideoTerminalLog' : 'videoTerminalLog';
        defaultTool = 'yt-dlp';
    } else if (mediaType === 'image') {
        inputId = isCenter ? 'centerImageUrlInput' : 'imageUrlInput';
        termId = isCenter ? 'centerImageTerminal' : 'imageTerminal';
        logId = isCenter ? 'centerImageTerminalLog' : 'imageTerminalLog';
        defaultTool = 'requests';
    } else if (mediaType === 'audio') {
        inputId = 'audioUrlInput';
        termId = 'audioTerminal';
        logId = 'audioTerminalLog';
        defaultTool = 'yt-dlp';
    }
    const inputEl = document.getElementById(inputId);
    const termEl = document.getElementById(termId);
    const logEl = document.getElementById(logId);
    if (!inputEl || !inputEl.value.trim()) {
        alert("Please enter a URL or command arguments.");
        return;
    }
    const rawCmd = inputEl.value.trim();
    if (termEl) termEl.classList.remove('hidden');
    if (logEl) {
        logEl.textContent = `[Connecting to download stream for ${mediaType} (${isCenter ? 'Center' : 'Primary'})...]\n`;
    }
    if (activeDownloadEventSources[termId]) {
        try { activeDownloadEventSources[termId].close(); } catch(e) {}
    }
    const streamUrl = `/api/download/stream?cmd=${encodeURIComponent(rawCmd)}&tool=${defaultTool}&media_type=${mediaType}&is_center=${isCenter}`;
    const es = new EventSource(streamUrl);
    activeDownloadEventSources[termId] = es;
    es.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'stdout' || data.type === 'stderr') {
                if (logEl) {
                    logEl.textContent += data.line;
                    logEl.scrollTop = logEl.scrollHeight;
                }
            } else if (data.type === 'completed') {
                es.close();
                delete activeDownloadEventSources[termId];
                if (data.status === 'success' && data.files && data.files.length > 0) {
                    const firstFile = data.files[0];
                    if (logEl) {
                        logEl.textContent += `\n>> Auto-selected '${firstFile}' for encryption.\n`;
                        logEl.scrollTop = logEl.scrollHeight;
                    }
                    inputEl.value = '';
                    selectVaultFileDirectly(firstFile, mediaType, isCenter);
                }
                if (typeof loadVault === 'function' && activeFolder === 'input') {
                    loadVault();
                }
            }
        } catch (err) {
            console.error("Error parsing download stream message:", err);
        }
    };
    es.onerror = function(err) {
        if (logEl) {
            logEl.textContent += "\n[Stream disconnected]\n";
            logEl.scrollTop = logEl.scrollHeight;
        }
        es.close();
        delete activeDownloadEventSources[termId];
    };
}
