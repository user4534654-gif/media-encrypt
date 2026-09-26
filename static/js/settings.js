const SETTINGS_KEY = 'media_encrypt_settings_v20';
let origRatio = 1;
let activeFolder = 'input';
let encryptionMode = 'normal';
let imgEncryptionMode = 'normal';
let activeMainTab = 'encrypt';
let activeMediaType = 'video';
let activeImageFormat = 'auto';
function collectSettings() {
    const bitSlider = document.getElementById('v_bit_slider');
    const freqSlider = document.getElementById('carrier_freq_slider');
    const encVideo = document.getElementById('encVideo');
    const encAudio = document.getElementById('encAudio');
    const val = (id, def) => { const el = document.getElementById(id); return el ? el.value : def; };
    const chk = (id, def) => { const el = document.getElementById(id); return el ? el.checked : def; };
    return {
        _preset: 'media-encrypt-settings',
        _version: 1,
        _savedAt: new Date().toISOString(),
        encryptionMode: encryptionMode,
        imgEncryptionMode: imgEncryptionMode,
        activeMediaType: activeMediaType,
        activeImageFormat: activeImageFormat,
        theme: chk('themeToggle', false),
        encVideo: encVideo ? encVideo.checked : true,
        encAudio: encAudio ? encAudio.checked : true,
        v_fmt: val('v_fmt', 'auto'),
        v_codec: val('v_codec', 'auto'),
        v_preset: val('v_preset', 'auto'),
        v_bit: bitSlider ? bitSlider.value : '3000',
        v_spatial_mode: val('v_spatial_mode', 'off'),
        zone_priority_strength: val('zone_priority_strength', '40'),
        autoVidBitrate: chk('autoVidBitrate', true),
        a_sr_auto: chk('a_sr_auto', true),
        a_sr_slider: val('a_sr_slider', '48000'),
        a_codec: val('a_codec', 'auto'),
        a_bit_slider: val('a_bit_slider', '320'),
        a_bit_auto: chk('a_bit_auto', false),
        cols: val('cols', '10'),
        rows: val('rows', '10'),
        sid: val('sid', ''),
        aspectLock: chk('aspectLock', true),
        noScale: chk('noScale', false),
        resW: val('resW', ''),
        resH: val('resH', ''),
        img_cols: val('img_cols', '10'),
        img_rows: val('img_rows', '10'),
        img_sid: val('img_sid', ''),
        carrier_freq: freqSlider ? freqSlider.value : '8000',
        audio_sr_auto: chk('audio_sr_auto', true),
        audio_sr_slider: val('audio_sr_slider', '48000'),
        audio_codec: val('audio_codec', 'auto'),
        audio_bit_slider: val('audio_bit_slider', '320'),
        audio_bit_auto: chk('audio_bit_auto', false),
        audio_fmt: val('audio_fmt', 'auto'),
        decKey: val('decKey', ''),
        aud_method: val('aud_method', 'inversion'),
        aud_splits: val('aud_splits', '10'),
        aud_seed: val('aud_seed', ''),
        aud_vol_factor: val('aud_vol_factor_slider', '100'),
        v_aud_method: val('v_aud_method', 'inversion'),
        v_aud_splits: val('v_aud_splits', '10'),
        vol_factor: val('vol_factor_slider', '100'),
        dual_track: chk('dual_track', false),
        track_l_source: val('trackLSourceSelect', 'background'),
        track_r_source: val('trackRSourceSelect', 'center'),
        track_l_enc: chk('trackLEncCheckbox', true),
        track_r_enc: chk('trackREncCheckbox', true),
        center_size: val('center_size', '1/4'),
        img_center_size: val('img_center_size', '1/4'),
        outer_end_action: val('outer_end_action', 'stop'),
        center_end_action: val('center_end_action', 'loop'),
        center_aud_action: val('center_aud_action', 'silence'),
        exportSvg: chk('exportSvg', true),
        imgExportSvg: chk('imgExportSvg', true),
        useGpu: chk('useGpu', false),
        saveKeyFile: chk('saveKeyFile', true),
        imgSaveKeyFile: chk('imgSaveKeyFile', true),
        audSaveKeyFile: chk('audSaveKeyFile', true),
        enableSpatialZones: chk('enableSpatialZones', false),
        patchRoiInvert: chk('patchRoiInvert', false),
        patchOpticalMarkers: chk('patchOpticalMarkers', false),
        patchMarkerPlacement: val('patchMarkerPlacement', 'outside'),
        patchCoordX1: val('patchCoordX1', ''),
        patchCoordY1: val('patchCoordY1', ''),
        patchCoordX2: val('patchCoordX2', ''),
        patchCoordY2: val('patchCoordY2', ''),
        imgEnableSpatialZones: chk('imgEnableSpatialZones', false),
        imgRoiInvert: chk('imgRoiInvert', false),
        imgOpticalMarkers: chk('imgOpticalMarkers', false),
        imgMarkerPlacement: val('imgMarkerPlacement', 'outside'),
        imgCoordX1: val('imgCoordX1', ''),
        imgCoordY1: val('imgCoordY1', ''),
        imgCoordX2: val('imgCoordX2', ''),
        imgCoordY2: val('imgCoordY2', '')
    };
}
function saveAllSettings() {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(collectSettings()));
}
function loadAllSettings() {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    try {
        applySettingsObject(JSON.parse(raw));
    } catch (e) {
        console.error("Error loading settings:", e);
    }
}
function exportSettingsToJson() {
    try {
        const settings = collectSettings();
        const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
        const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `media-encrypt-settings-${stamp}.json`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    } catch (e) {
        console.error('Error exporting settings:', e);
        alert('Could not export settings: ' + e.message);
    }
}
function importSettingsFromJsonFile(file) {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        try {
            const settings = JSON.parse(reader.result);
            if (!settings || typeof settings !== 'object' || Array.isArray(settings)) {
                throw new Error('not a settings object');
            }
            applySettingsObject(settings);
            saveAllSettings();
            alert('Settings preset applied.');
        } catch (e) {
            console.error('Error importing settings:', e);
            alert('Could not load settings preset: invalid .json file.');
        }
    };
    reader.readAsText(file);
}
function applySettingsObject(settings) {
    try {
        if (settings.theme !== undefined) {
            const toggle = document.getElementById('themeToggle');
            if (toggle) toggle.checked = settings.theme;
            toggleTheme(settings.theme);
        }
        if (settings.encryptionMode) setEncryptionMode(settings.encryptionMode);
        if (settings.imgEncryptionMode) setImageEncryptionMode(settings.imgEncryptionMode);
        if (settings.activeImageFormat) setImageFormat(settings.activeImageFormat);
        if (settings.activeMediaType) setMediaTypeTab(settings.activeMediaType);
        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
        const setChecked = (id, checked) => { const el = document.getElementById(id); if (el) el.checked = checked; };
        setChecked('encVideo', settings.encVideo);
        setChecked('encAudio', settings.encAudio);
        setVal('v_fmt', settings.v_fmt);
        setVal('v_codec', settings.v_codec);
        setVal('v_preset', settings.v_preset);
        let _sm = settings.v_spatial_mode || 'off';
        if (_sm === 'zone') _sm = 'priority';
        else if (_sm !== 'priority') _sm = 'off';
        setVal('v_spatial_mode', _sm);
        if (typeof toggleZonePriority === 'function') toggleZonePriority(_sm);
        if (settings.zone_priority_strength !== undefined) {
            setVal('zone_priority_strength', settings.zone_priority_strength);
            const _zpv = document.getElementById('zone_priority_val');
            if (_zpv) _zpv.innerText = settings.zone_priority_strength;
        }
        const bitSlider = document.getElementById('v_bit_slider');
        const bitVal = document.getElementById('v_bit_val');
        const bitLabel = document.getElementById('v_bit_label');
        if (settings.v_bit && bitSlider) {
            bitSlider.value = settings.v_bit;
            if (bitVal) bitVal.innerText = settings.v_bit + 'k';
            if (bitLabel) bitLabel.innerText = 'Max Dynamic Bitrate: ' + settings.v_bit + 'k';
        }
        if (settings.autoVidBitrate !== undefined) {
            setChecked('autoVidBitrate', settings.autoVidBitrate);
            toggleVidBitrateAuto(settings.autoVidBitrate);
        }
        const aSrSliderEl = document.getElementById('a_sr_slider');
        if (aSrSliderEl) {
            aSrSliderEl.value = settings.a_sr_slider || (settings.a_sr && settings.a_sr !== 'auto' ? settings.a_sr : '48000');
        }
        if (settings.a_sr_auto !== undefined) setChecked('a_sr_auto', settings.a_sr_auto);
        syncAudioSrLabel('video');
        if (typeof toggleAudioSrAuto === 'function') toggleAudioSrAuto(document.getElementById('a_sr_auto') ? document.getElementById('a_sr_auto').checked : true, 'video');
        setVal('a_codec', settings.a_codec);
        if (typeof onAudioCodecChanged === 'function') onAudioCodecChanged('video');
        const aBitSliderEl = document.getElementById('a_bit_slider');
        if (aBitSliderEl && settings.a_bit_slider) {
            aBitSliderEl.value = settings.a_bit_slider;
        }
        if (settings.a_bit_auto !== undefined) {
            setChecked('a_bit_auto', settings.a_bit_auto);
            if (typeof toggleAudioBitAuto === 'function') toggleAudioBitAuto(settings.a_bit_auto, 'video');
        } else {
            if (typeof syncAudioBitLabel === 'function') syncAudioBitLabel('video');
        }
        setVal('cols', settings.cols);
        setVal('rows', settings.rows);
        setVal('sid', settings.sid);
        setChecked('aspectLock', settings.aspectLock);
        setChecked('noScale', settings.noScale);
        setVal('resW', settings.resW);
        setVal('resH', settings.resH);
        setVal('img_cols', settings.img_cols);
        setVal('img_rows', settings.img_rows);
        setVal('img_sid', settings.img_sid);
        const freqSlider = document.getElementById('carrier_freq_slider');
        const freqVal = document.getElementById('carrier_freq_val');
        const freqLabel = document.getElementById('carrier_freq_label');
        if (settings.carrier_freq && freqSlider) {
            freqSlider.value = settings.carrier_freq;
            if (freqVal) freqVal.innerText = settings.carrier_freq + ' Hz';
            if (freqLabel) freqLabel.innerText = 'Carrier Frequency: ' + settings.carrier_freq + ' Hz';
        }
        const audioSrSliderEl = document.getElementById('audio_sr_slider');
        if (audioSrSliderEl) {
            audioSrSliderEl.value = settings.audio_sr_slider || (settings.audio_sr && settings.audio_sr !== 'auto' ? settings.audio_sr : '48000');
        }
        if (settings.audio_sr_auto !== undefined) setChecked('audio_sr_auto', settings.audio_sr_auto);
        syncAudioSrLabel('audio');
        if (typeof toggleAudioSrAuto === 'function') toggleAudioSrAuto(document.getElementById('audio_sr_auto') ? document.getElementById('audio_sr_auto').checked : true, 'audio');
        setVal('audio_codec', settings.audio_codec);
        if (typeof onAudioCodecChanged === 'function') onAudioCodecChanged('audio');
        const audioBitSliderEl = document.getElementById('audio_bit_slider');
        if (audioBitSliderEl && settings.audio_bit_slider) {
            audioBitSliderEl.value = settings.audio_bit_slider;
        }
        if (settings.audio_bit_auto !== undefined) {
            setChecked('audio_bit_auto', settings.audio_bit_auto);
            if (typeof toggleAudioBitAuto === 'function') toggleAudioBitAuto(settings.audio_bit_auto, 'audio');
        } else {
            if (typeof syncAudioBitLabel === 'function') syncAudioBitLabel('audio');
        }
        setVal('audio_fmt', settings.audio_fmt);
        setVal('decKey', settings.decKey);
        setVal('aud_method', settings.aud_method || 'inversion');
        setVal('aud_splits', settings.aud_splits || '10');
        setVal('aud_seed', settings.aud_seed || '');
        const audVolSlider = document.getElementById('aud_vol_factor_slider');
        const audVolVal = document.getElementById('aud_vol_factor_val');
        const audVolLabel = document.getElementById('aud_vol_factor_label');
        if (settings.aud_vol_factor && audVolSlider) {
            audVolSlider.value = settings.aud_vol_factor;
            if (audVolVal) audVolVal.innerText = settings.aud_vol_factor + '%';
            if (audVolLabel) audVolLabel.innerText = 'Encrypted Audio Volume: ' + settings.aud_vol_factor + '%';
        }
        const vAudMethod = document.getElementById('v_aud_method');
        if (vAudMethod && settings.v_aud_method) vAudMethod.value = settings.v_aud_method;
        setVal('v_aud_splits', settings.v_aud_splits || '10');
        const volSlider = document.getElementById('vol_factor_slider');
        const volVal = document.getElementById('vol_factor_val');
        const volLabel = document.getElementById('vol_factor_label');
        if (settings.vol_factor && volSlider) {
            volSlider.value = settings.vol_factor;
            if (volVal) volVal.innerText = settings.vol_factor + '%';
            if (volLabel) volLabel.innerText = 'Volume Factor: ' + settings.vol_factor + '%';
        }
        setChecked('dual_track', settings.dual_track || false);
        if (settings.track_l_source) setVal('trackLSourceSelect', settings.track_l_source);
        if (settings.track_r_source) setVal('trackRSourceSelect', settings.track_r_source);
        if (settings.track_l_enc !== undefined) setChecked('trackLEncCheckbox', settings.track_l_enc);
        if (settings.track_r_enc !== undefined) setChecked('trackREncCheckbox', settings.track_r_enc);
        if (typeof updateTrackRouting === 'function') {
            const _sl = document.getElementById('trackLSourceSelect');
            const _sr = document.getElementById('trackRSourceSelect');
            if (_sl) updateTrackRouting('L', _sl.value);
            if (_sr) updateTrackRouting('R', _sr.value);
        }
        setVal('center_size', settings.center_size || '1/4');
        setVal('img_center_size', settings.img_center_size || '1/4');
        if (typeof syncCenterSizeControls === 'function') syncCenterSizeControls();
        setVal('outer_end_action', settings.outer_end_action || 'stop');
        setVal('center_end_action', settings.center_end_action || 'loop');
        setVal('center_aud_action', settings.center_aud_action || 'silence');
        setChecked('exportSvg', settings.exportSvg !== false);
        setChecked('imgExportSvg', settings.imgExportSvg !== false);
        setChecked('useGpu', settings.useGpu === true);
        setChecked('saveKeyFile', settings.saveKeyFile !== false);
        setChecked('imgSaveKeyFile', settings.imgSaveKeyFile !== false);
        setChecked('audSaveKeyFile', settings.audSaveKeyFile !== false);
        if (settings.enableSpatialZones !== undefined) {
            setChecked('enableSpatialZones', settings.enableSpatialZones);
            if (typeof onEnableSpatialZonesToggle === 'function') onEnableSpatialZonesToggle(!!settings.enableSpatialZones);
        }
        if (settings.patchRoiInvert !== undefined) setChecked('patchRoiInvert', settings.patchRoiInvert);
        if (settings.patchOpticalMarkers !== undefined) {
            setChecked('patchOpticalMarkers', settings.patchOpticalMarkers);
            if (typeof toggleOpticalPlacement === 'function') toggleOpticalPlacement(!!settings.patchOpticalMarkers);
        }
        if (settings.patchMarkerPlacement) setVal('patchMarkerPlacement', settings.patchMarkerPlacement);
        if (settings.patchCoordX1 !== undefined && settings.patchCoordX1 !== '') {
            setVal('patchCoordX1', settings.patchCoordX1);
            setVal('patchCoordY1', settings.patchCoordY1);
            setVal('patchCoordX2', settings.patchCoordX2);
            setVal('patchCoordY2', settings.patchCoordY2);
            if (typeof onManualCoordInput === 'function') onManualCoordInput();
        }
        if (settings.imgEnableSpatialZones !== undefined) {
            setChecked('imgEnableSpatialZones', settings.imgEnableSpatialZones);
            if (typeof onEnableImgSpatialZonesToggle === 'function') onEnableImgSpatialZonesToggle(!!settings.imgEnableSpatialZones);
        }
        if (settings.imgRoiInvert !== undefined) setChecked('imgRoiInvert', settings.imgRoiInvert);
        if (settings.imgOpticalMarkers !== undefined) {
            setChecked('imgOpticalMarkers', settings.imgOpticalMarkers);
            if (typeof toggleImgOpticalPlacement === 'function') toggleImgOpticalPlacement(!!settings.imgOpticalMarkers);
        }
        if (settings.imgMarkerPlacement) setVal('imgMarkerPlacement', settings.imgMarkerPlacement);
        if (settings.imgCoordX1 !== undefined && settings.imgCoordX1 !== '') {
            setVal('imgCoordX1', settings.imgCoordX1);
            setVal('imgCoordY1', settings.imgCoordY1);
            setVal('imgCoordX2', settings.imgCoordX2);
            setVal('imgCoordY2', settings.imgCoordY2);
            if (typeof onManualImgCoordInput === 'function') onManualImgCoordInput();
        }
        updateVisibility();
        if (typeof toggleAudioMethodFields === 'function') toggleAudioMethodFields();
        if (typeof toggleVideoAudioMethodFields === 'function') toggleVideoAudioMethodFields();
    } catch (e) {
        console.error("Error loading settings:", e);
    }
}
function initAutoSave() {
    const inputs = [
        'themeToggle', 'encVideo', 'encAudio', 'v_fmt', 'v_codec', 'v_preset', 'v_bit_slider', 'autoVidBitrate',
        'a_sr_slider', 'a_sr_auto', 'a_codec', 'a_bit_slider', 'a_bit_auto', 'cols', 'rows', 'sid', 'aspectLock', 'noScale', 'resW', 'resH',
        'img_cols', 'img_rows', 'img_sid', 'carrier_freq_slider', 'audio_sr_slider', 'audio_sr_auto', 'audio_codec',
        'audio_bit_slider', 'audio_bit_auto', 'audio_fmt', 'decKey', 'aud_method', 'aud_splits', 'aud_seed', 'aud_vol_factor_slider',
        'v_aud_method', 'v_aud_splits', 'vol_factor_slider', 'dual_track', 'trackLSourceSelect', 'trackRSourceSelect', 'trackLEncCheckbox', 'trackREncCheckbox', 'center_size', 'img_center_size',
        'outer_end_action', 'center_end_action', 'center_aud_action', 'exportSvg', 'imgExportSvg', 'useGpu', 'saveKeyFile', 'imgSaveKeyFile', 'audSaveKeyFile',
        'enableSpatialZones', 'patchRoiInvert', 'patchOpticalMarkers', 'patchMarkerPlacement', 'patchCoordX1', 'patchCoordY1', 'patchCoordX2', 'patchCoordY2',
        'imgEnableSpatialZones', 'imgRoiInvert', 'imgOpticalMarkers', 'imgMarkerPlacement', 'imgCoordX1', 'imgCoordY1', 'imgCoordX2', 'imgCoordY2',
        'v_spatial_mode', 'zone_priority_strength'
    ];
    inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', saveAllSettings);
            el.addEventListener('input', saveAllSettings);
        }
    });
}
function toggleVidBitrateAuto(isAuto) {
    const sliderContainer = document.getElementById('vidBitrateSliderContainer');
    if (sliderContainer) {
        sliderContainer.style.display = isAuto ? 'none' : 'flex';
    }
    saveAllSettings();
}
function toggleZonePriority(mode) {
    const row = document.getElementById('zonePriorityRow');
    if (row) {
        row.style.display = (mode === 'priority') ? 'block' : 'none';
    }
    if (typeof saveAllSettings === 'function') {
        try { saveAllSettings(); } catch (e) {}
    }
}
