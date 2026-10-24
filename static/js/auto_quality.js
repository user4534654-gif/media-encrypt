// auto_quality.js — Auto Quality: one slider drives the whole encode.
//
// The Auto Quality slider expresses the desired output size as a delta
// against the INPUT file size (0% = same size, +20% = 20% bigger). The
// backend turns that into a bitrate plan (core/auto_quality.py); this file
// owns the UI: the switch, the slider, the live estimate and the conflict
// with the 🌊 wave (an explicit wave replaces the size target).

const AUTO_QUALITY_MIN_PCT = -50;
const AUTO_QUALITY_MAX_PCT = 100;
const AUTO_QUALITY_MIN_KBPS = 100;
const AUTO_QUALITY_MAX_KBPS = 25000;
const AUTO_QUALITY_OVERHEAD_RATIO = 0.02;

let autoQualityLastVideoKbps = 0;

// ── State helpers ────────────────────────────────────────────────────────────

function autoQualityIsEnabled() {
    const el = document.getElementById('autoQualityToggle');
    return el ? el.checked : true;
}

function autoQualityPct() {
    const el = document.getElementById('autoQualityPct');
    let v = el ? parseInt(el.value, 10) : 0;
    if (!isFinite(v)) v = 0;
    return Math.max(AUTO_QUALITY_MIN_PCT, Math.min(AUTO_QUALITY_MAX_PCT, v));
}

function getAutoQualityState() {
    return { enabled: autoQualityIsEnabled(), pct: autoQualityPct() };
}

// ── Mode switching ──────────────────────────────────────────────────────────

// Turning Auto Quality ON clears the wave: a wave carries its own
// bitrate and would silently replace the size target.
function setAutoQualityEnabled(on, skipSave) {
    const toggle = document.getElementById('autoQualityToggle');
    if (toggle && toggle.checked !== !!on) toggle.checked = !!on;

    const body = document.getElementById('autoQualityBody');
    if (body) body.classList.toggle('auto-quality-disabled', !on);

    const sliderBox = document.getElementById('vidBitrateSliderContainer');
    if (sliderBox) sliderBox.style.display = on ? 'none' : 'flex';

    if (on) {
        const env = document.getElementById('vid_bitrate_envelope');
        if (env && env.value) {
            if (typeof clearBitrateWave === 'function') clearBitrateWave();
            else env.value = '';
        }
    } else if (autoQualityLastVideoKbps > 0) {
        // Hand the last computed bitrate over to the manual slider so
        // switching modes does not jump.
        const slider = document.getElementById('v_bit_slider');
        const val = document.getElementById('v_bit_val');
        const label = document.getElementById('v_bit_label_text');
        if (slider) {
            slider.value = String(Math.max(500, Math.min(25000, Math.round(autoQualityLastVideoKbps / 500) * 500)));
            if (val) val.innerText = slider.value + 'k';
            if (label) label.textContent = 'Max Dynamic Bitrate: ' + slider.value + 'k';
        }
    }

    updateAutoQualityWaveState();
    updateAutoQualityReadout();
    if (!skipSave && typeof saveAllSettings === 'function') {
        try { saveAllSettings(); } catch (e) {}
    }
}

function onAutoQualityPct(val, skipSave) {
    const v = parseInt(val, 10);
    const pct = isFinite(v) ? v : 0;
    const el = document.getElementById('autoQualityPctVal');
    if (el) el.textContent = (pct > 0 ? '+' : '') + pct + '%';
    updateAutoQualityReadout();
    if (!skipSave && typeof saveAllSettings === 'function') {
        try { saveAllSettings(); } catch (e) {}
    }
}

// ── Live estimate ───────────────────────────────────────────────────────────

function autoQualityFormatBytes(bytes) {
    if (!bytes || bytes <= 0) return '—';
    const mb = bytes / 1048576;
    if (mb >= 1024) return (mb / 1024).toFixed(2) + ' GB';
    if (mb >= 10) return mb.toFixed(1) + ' MB';
    return mb.toFixed(2) + ' MB';
}

// Input size + duration of the source currently loaded in the video tab.
function autoQualitySource() {
    let sizeBytes = 0;
    let durationSec = 0;
    try {
        const lb = window._lastBitrates || null;
        if (lb) {
            if (lb.sizeBytes) sizeBytes = lb.sizeBytes;
            if (lb.durationSec) durationSec = lb.durationSec;
        }
    } catch (e) {}
    if (!sizeBytes) {
        try { sizeBytes = window._lastVaultMediaSize || 0; } catch (e) {}
    }
    if (!durationSec) {
        try { durationSec = window._lastVaultMediaDuration || 0; } catch (e) {}
    }
    return { sizeBytes: sizeBytes, durationSec: durationSec };
}

// Audio bitrate reserved for the estimate (the backend does the exact
// split; this is the preview shown while the slider moves).
function autoQualityAudioKbps() {
    const auto = document.getElementById('a_bit_auto');
    if (auto && auto.checked) return 192;
    const el = document.getElementById('a_bit_slider');
    const v = el ? parseInt(el.value, 10) : 320;
    return isFinite(v) && v > 0 ? v : 192;
}

function autoQualityComputePlan() {
    const src = autoQualitySource();
    if (!src.sizeBytes || !src.durationSec || src.durationSec <= 0) return null;
    const pct = autoQualityPct();
    const targetBytes = Math.round(src.sizeBytes * (1 + pct / 100));
    const totalKbps = (targetBytes * 8) / src.durationSec / 1000;
    const overhead = totalKbps * AUTO_QUALITY_OVERHEAD_RATIO;
    const audioKbps = autoQualityAudioKbps();
    let videoKbps = totalKbps - overhead - audioKbps;
    let clamped = null;
    if (videoKbps < AUTO_QUALITY_MIN_KBPS) {
        videoKbps = AUTO_QUALITY_MIN_KBPS;
        clamped = 'min';
    } else if (videoKbps > AUTO_QUALITY_MAX_KBPS) {
        videoKbps = AUTO_QUALITY_MAX_KBPS;
        clamped = 'max';
    }
    return {
        inputBytes: src.sizeBytes,
        targetBytes: targetBytes,
        durationSec: src.durationSec,
        audioKbps: audioKbps,
        videoKbps: Math.round(videoKbps),
        clamped: clamped
    };
}

function updateAutoQualityReadout() {
    const readout = document.getElementById('autoQualityReadout');
    const targetVal = document.getElementById('autoQualityTargetVal');
    const label = document.getElementById('v_bit_label_text');
    const plan = autoQualityComputePlan();

    if (!plan) {
        if (readout) {
            readout.innerHTML = 'Select a video to see the size target.';
            readout.classList.remove('auto-quality-warn');
        }
        if (targetVal) targetVal.textContent = '—';
        if (label && autoQualityIsEnabled()) label.textContent = 'Bitrate: set by Auto Quality';
        return;
    }

    autoQualityLastVideoKbps = plan.videoKbps;
    if (targetVal) {
        targetVal.textContent = autoQualityFormatBytes(plan.targetBytes);
    }
    if (readout) {
        let txt = 'Input ' + autoQualityFormatBytes(plan.inputBytes)
            + ' → target ' + autoQualityFormatBytes(plan.targetBytes)
            + ' → ≈' + plan.videoKbps + 'k video + ' + plan.audioKbps + 'k audio';
        if (plan.clamped === 'max') {
            txt += ' · clamped to the 25 Mbps encoder ceiling';
            readout.classList.add('auto-quality-warn');
        } else if (plan.clamped === 'min') {
            txt += ' · clamped to the 100 kbps floor';
            readout.classList.add('auto-quality-warn');
        } else {
            readout.classList.remove('auto-quality-warn');
        }
        readout.textContent = txt;
    }
    if (label) {
        label.textContent = autoQualityIsEnabled()
            ? 'Bitrate: ≈' + plan.videoKbps + 'k (Auto Quality)'
            : 'Max Dynamic Bitrate: ' + (document.getElementById('v_bit_slider') ? document.getElementById('v_bit_slider').value : '3000') + 'k';
    }
}

// ── Wave interaction ────────────────────────────────────────────────────────

// The wave and the size target both own the bitrate, so only one of them
// can be active. The Extended tab shows which one is in charge.
function updateAutoQualityWaveState() {
    const btn = document.getElementById('bitrateWaveBtn');
    const hint = document.getElementById('autoQualityWaveHint');
    const env = document.getElementById('vid_bitrate_envelope');
    const hasWave = !!(env && env.value);
    const auto = autoQualityIsEnabled();
    if (btn) {
        btn.disabled = auto;
        btn.style.opacity = auto ? '0.45' : '1';
        btn.title = auto
            ? 'A wave replaces the Auto Quality size target — turn Auto Quality off to shape a wave.'
            : 'Shape the dynamic bitrate as a wave: drag timeline points, shift everything with the master slider';
    }
    if (hint) {
        if (auto && hasWave) {
            hint.textContent = 'Auto Quality drives the bitrate — the wave is ignored until you turn it off.';
            hint.classList.add('auto-quality-warn');
        } else if (auto) {
            hint.textContent = 'Auto Quality drives the bitrate.';
            hint.classList.remove('auto-quality-warn');
        } else if (hasWave) {
            hint.textContent = 'The wave drives the bitrate.';
            hint.classList.remove('auto-quality-warn');
        } else {
            hint.textContent = '';
            hint.classList.remove('auto-quality-warn');
        }
    }
}

// ── Basic / Extended sub-tabs ───────────────────────────────────────────────

function switchVidQualityTab(which) {
    const extended = (which === 'extended');
    const basicBtn = document.getElementById('vidQualityTabBasic');
    const extBtn = document.getElementById('vidQualityTabExtended');
    const basicPane = document.getElementById('vidQualityPaneBasic');
    const extPane = document.getElementById('vidQualityPaneExtended');
    if (basicBtn) basicBtn.classList.toggle('active', !extended);
    if (extBtn) extBtn.classList.toggle('active', extended);
    if (basicPane) basicPane.classList.toggle('hidden', extended);
    if (extPane) extPane.classList.toggle('hidden', !extended);
    if (extended) updateAutoQualityWaveState();
}

// ── Boot ────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const pctEl = document.getElementById('autoQualityPct');
    if (pctEl) {
        const pct = autoQualityPct();
        pctEl.value = String(pct);
        const label = document.getElementById('autoQualityPctVal');
        if (label) label.textContent = (pct > 0 ? '+' : '') + pct + '%';
    }
    setAutoQualityEnabled(autoQualityIsEnabled());
});
