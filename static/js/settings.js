const SETTINGS_KEY = 'media_encrypt_settings_v20';
let origRatio = 1;
let activeFolder = 'input';
let encryptionMode = 'normal';
let imgEncryptionMode = 'normal';
let activeMainTab = 'encrypt';
let activeMediaType = 'video';
let activeImageFormat = 'auto';
function saveAllSettings() {
    const bitSlider = document.getElementById('v_bit_slider');
    const freqSlider = document.getElementById('carrier_freq_slider');
    const encVideo = document.getElementById('encVideo');
    const encAudio = document.getElementById('encAudio');
    const settings = {
        encryptionMode: encryptionMode,
        imgEncryptionMode: imgEncryptionMode,
        activeMediaType: activeMediaType,
        activeImageFormat: activeImageFormat,
        theme: document.getElementById('themeToggle') ? document.getElementById('themeToggle').checked : false,
        encVideo: encVideo ? encVideo.checked : true,
        encAudio: encAudio ? encAudio.checked : true,
        v_fmt: document.getElementById('v_fmt') ? document.getElementById('v_fmt').value : 'auto',
        v_codec: document.getElementById('v_codec') ? document.getElementById('v_codec').value : 'auto',
        v_preset: document.getElementById('v_preset') ? document.getElementById('v_preset').value : 'auto',
        v_bit: bitSlider ? bitSlider.value : '3000',
        autoVidBitrate: document.getElementById('autoVidBitrate') ? document.getElementById('autoVidBitrate').checked : true,
        a_sr: document.getElementById('a_sr') ? document.getElementById('a_sr').value : 'auto',
        a_codec: document.getElementById('a_codec') ? document.getElementById('a_codec').value : 'auto',
        a_bit: document.getElementById('a_bit') ? document.getElementById('a_bit').value : 'auto',
        cols: document.getElementById('cols') ? document.getElementById('cols').value : '10',
        rows: document.getElementById('rows') ? document.getElementById('rows').value : '10',
        sid: document.getElementById('sid') ? document.getElementById('sid').value : '',
        aspectLock: document.getElementById('aspectLock') ? document.getElementById('aspectLock').checked : true,
        noScale: document.getElementById('noScale') ? document.getElementById('noScale').checked : false,
        resW: document.getElementById('resW') ? document.getElementById('resW').value : '',
        resH: document.getElementById('resH') ? document.getElementById('resH').value : '',
        img_cols: document.getElementById('img_cols') ? document.getElementById('img_cols').value : '10',
        img_rows: document.getElementById('img_rows') ? document.getElementById('img_rows').value : '10',
        img_sid: document.getElementById('img_sid') ? document.getElementById('img_sid').value : '',
        carrier_freq: freqSlider ? freqSlider.value : '8000',
        audio_sr: document.getElementById('audio_sr') ? document.getElementById('audio_sr').value : 'auto',
        audio_codec: document.getElementById('audio_codec') ? document.getElementById('audio_codec').value : 'auto',
        audio_bit: document.getElementById('audio_bit') ? document.getElementById('audio_bit').value : 'auto',
        audio_fmt: document.getElementById('audio_fmt') ? document.getElementById('audio_fmt').value : 'auto',
        decKey: document.getElementById('decKey') ? document.getElementById('decKey').value : '',
        aud_method: document.getElementById('aud_method') ? document.getElementById('aud_method').value : 'inversion',
        aud_splits: document.getElementById('aud_splits') ? document.getElementById('aud_splits').value : '10',
        aud_seed: document.getElementById('aud_seed') ? document.getElementById('aud_seed').value : '',
        aud_vol_factor: document.getElementById('aud_vol_factor_slider') ? document.getElementById('aud_vol_factor_slider').value : '100',
        v_aud_method: document.getElementById('v_aud_method') ? document.getElementById('v_aud_method').value : 'inversion',
        v_aud_splits: document.getElementById('v_aud_splits') ? document.getElementById('v_aud_splits').value : '10',
        vol_factor: document.getElementById('vol_factor_slider') ? document.getElementById('vol_factor_slider').value : '100',
        dual_track: document.getElementById('dual_track') ? document.getElementById('dual_track').checked : false,
        center_size: document.getElementById('center_size') ? document.getElementById('center_size').value : '1/4',
        img_center_size: document.getElementById('img_center_size') ? document.getElementById('img_center_size').value : '1/4',
        outer_end_action: document.getElementById('outer_end_action') ? document.getElementById('outer_end_action').value : 'stop',
        center_end_action: document.getElementById('center_end_action') ? document.getElementById('center_end_action').value : 'loop',
        center_aud_action: document.getElementById('center_aud_action') ? document.getElementById('center_aud_action').value : 'silence'
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}
function loadAllSettings() {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    try {
        const settings = JSON.parse(raw);
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
        const bitSlider = document.getElementById('v_bit_slider');
        const bitVal = document.getElementById('v_bit_val');
        const bitLabel = document.getElementById('v_bit_label');
        if (settings.v_bit && bitSlider) {
            bitSlider.value = settings.v_bit;
            if (bitVal) bitVal.innerText = settings.v_bit + 'k';
            if (bitLabel) bitLabel.innerText = 'Video Bitrate: ' + settings.v_bit + 'k';
        }
        if (settings.autoVidBitrate !== undefined) {
            setChecked('autoVidBitrate', settings.autoVidBitrate);
            toggleVidBitrateAuto(settings.autoVidBitrate);
        }
        setVal('a_sr', settings.a_sr);
        setVal('a_codec', settings.a_codec);
        setVal('a_bit', settings.a_bit);
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
        setVal('audio_sr', settings.audio_sr);
        setVal('audio_codec', settings.audio_codec);
        setVal('audio_bit', settings.audio_bit);
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
        setVal('v_aud_method', settings.v_aud_method || 'inversion');
        setVal('v_aud_splits', settings.v_aud_splits || '10');
        const volSlider = document.getElementById('vol_factor_slider');
        const volVal = document.getElementById('vol_factor_val');
        const volLabel = document.getElementById('vol_factor_label');
        if (settings.vol_factor && volSlider) {
            volSlider.value = settings.vol_factor;
            if (volVal) volVal.innerText = settings.vol_factor + '%';
            if (volLabel) volLabel.innerText = 'Encrypted Audio Volume: ' + settings.vol_factor + '%';
        }
        setChecked('dual_track', settings.dual_track || false);
        setVal('center_size', settings.center_size || '1/4');
        setVal('img_center_size', settings.img_center_size || '1/4');
        setVal('outer_end_action', settings.outer_end_action || 'stop');
        setVal('center_end_action', settings.center_end_action || 'loop');
        setVal('center_aud_action', settings.center_aud_action || 'silence');
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
        'a_sr', 'a_codec', 'a_bit', 'cols', 'rows', 'sid', 'aspectLock', 'noScale', 'resW', 'resH',
        'img_cols', 'img_rows', 'img_sid', 'carrier_freq_slider', 'audio_sr', 'audio_codec',
        'audio_bit', 'audio_fmt', 'decKey', 'aud_method', 'aud_splits', 'aud_seed', 'aud_vol_factor_slider',
        'v_aud_method', 'v_aud_splits', 'vol_factor_slider', 'dual_track', 'center_size', 'img_center_size',
        'outer_end_action', 'center_end_action', 'center_aud_action'
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
