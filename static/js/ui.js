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
    activeImageFormat = format;
    ['auto', '.png', '.avif', '.jpg', '.webp'].forEach(fmt => {
        const fmtId = fmt.replace('.', '');
        const id = 'imgFmt' + fmtId.charAt(0).toUpperCase() + fmtId.slice(1);
        const btn = document.getElementById(id);
        if (btn) btn.classList.toggle('active', fmt === format);
    });
    saveAllSettings();
}

function setMediaTypeTab(type) {
    activeMediaType = type;
    const vTab = document.getElementById('mediaTabVideo');
    const iTab = document.getElementById('mediaTabImage');
    const aTab = document.getElementById('mediaTabAudio');
    if (vTab) vTab.classList.toggle('active', type === 'video');
    if (iTab) iTab.classList.toggle('active', type === 'image');
    if (aTab) aTab.classList.toggle('active', type === 'audio');
    
    const vStudio = document.getElementById('videoStudio');
    const iStudio = document.getElementById('imageStudio');
    const aStudio = document.getElementById('audioStudio');
    if (vStudio) vStudio.classList.toggle('hidden', type !== 'video');
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
    
    // Check if running inside pywebview wrapper
    if (window.pywebview && window.pywebview.api && window.pywebview.api.toggle_fullscreen) {
        window.pywebview.api.toggle_fullscreen().then(isFullscreen => {
            if (btn) {
                btn.innerText = isFullscreen ? "Exit Fullscreen 🖥️" : "Fullscreen 🖥️";
            }
        }).catch(err => {
            console.error("Webview fullscreen error:", err);
        });
    } else {
        // Fallback to normal browser Fullscreen API
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

// Check Decryption Key to show Badge
const decKeyInput = document.getElementById('decKey');
if (decKeyInput) {
    decKeyInput.addEventListener('input', function() {
        const val = this.value || '';
        const badge = document.getElementById('decKeyModeBadge');
        if (badge) {
            const cleanVal = val.replace(/\s+/g, '');
            if (cleanVal.includes('|c') || cleanVal.includes('|c|')) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
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
        if (!files.length) return;
        
        const url = URL.createObjectURL(files[0]);
        if (files[0].type.startsWith('video/')) {
            const vid = document.createElement('video');
            vid.onloadedmetadata = () => setRatio(vid.videoWidth, vid.videoHeight);
            vid.src = url;
        }
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

    // Normalize emoji mapping to handle standard and variation-selector (\ufe0f) variations
    const normalizedMap = {};
    const escapedPatterns = [];

    // Sort by length descending to match longer multi-character emojis first
    emojis.sort((a, b) => b.length - a.length);

    for (let e of emojis) {
        const base = e.replace(/\ufe0f/g, '');
        normalizedMap[base] = emojiMap[e];
        normalizedMap[base + '\ufe0f'] = emojiMap[e];

        const escapedBase = base.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        // Match the base emoji with an optional variation selector
        escapedPatterns.push(escapedBase + '\\ufe0f?');
    }

    // Use 'gu' flags for correct surrogate pair / unicode parsing
    const regex = new RegExp(`(${escapedPatterns.join('|')})`, 'gu');

    function walk(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.nodeValue;
            // Reset regex state since it's global
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

// Global hotkey to save the debug log (Ctrl+Shift+D)
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

// Background heartbeat to keep the active session registered on the server (run every 5 seconds)
setInterval(() => {
    fetch('/api/heartbeat').catch(() => {});
}, 5000);

// Collapsible UI panels toggler
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
