
let wavePts = null;   
let waveGain = 0;     
let waveDragIdx = -1;
const WAVE_MIN = 100;
const WAVE_MAX = 25000;
function waveSeedDefaults() {
    const slider = document.getElementById('v_bit_slider');
    const base = slider ? (parseInt(slider.value, 10) || 3000) : 3000;
    let left = base, right = base;
    try {
        const lb = window._lastBitrates || null;
        if (lb && (lb.bg > 0 || lb.center > 0)) {
            if (lb.bg > 0) left = lb.bg;
            if (lb.center > 0) right = lb.center;
        }
    } catch (e) {}
    const mid = Math.max(WAVE_MIN, Math.round(Math.min(left, right) * 0.4 / 10) * 10);
    const clamp = (v) => Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(v / 10) * 10));
    return [clamp(left), clamp(mid), clamp(right)];
}
function openBitrateWave() {
    const modal = document.getElementById('bitrateWaveModal');
    if (!modal) return;
    if (!wavePts) {
        try {
            const raw = document.getElementById('vid_bitrate_envelope').value;
            if (raw) {
                const env = JSON.parse(raw);
                if (env && Array.isArray(env.points) && env.points.length === 3) {
                    wavePts = env.points.map(v => Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(v))));
                }
            }
        } catch (e) {}
        if (!wavePts) wavePts = waveSeedDefaults();
    }
    waveGain = 0;
    const gain = document.getElementById('bitrateWaveGain');
    if (gain) gain.value = '0';
    updateWaveGainLabel();
    modal.style.display = 'flex';
    drawBitrateWave();
}
function closeBitrateWave() {
    const modal = document.getElementById('bitrateWaveModal');
    if (modal) modal.style.display = 'none';
    applyBitrateWave();
}
function resetBitrateWave() {
    wavePts = waveSeedDefaults();
    waveGain = 0;
    const gain = document.getElementById('bitrateWaveGain');
    if (gain) gain.value = '0';
    updateWaveGainLabel();
    drawBitrateWave();
}
function clearBitrateWave() {
    wavePts = null;
    waveGain = 0;
    const hidden = document.getElementById('vid_bitrate_envelope');
    if (hidden) hidden.value = '';
    const info = document.getElementById('vidBitrateWaveInfo');
    if (info) { info.style.display = 'none'; info.innerHTML = ''; }
    const label = document.getElementById('v_bit_label');
    const slider = document.getElementById('v_bit_slider');
    if (label && slider) label.innerHTML = 'Max Dynamic Bitrate: ' + slider.value + 'k';
    closeBitrateWaveModalOnly();
}
function closeBitrateWaveModalOnly() {
    const modal = document.getElementById('bitrateWaveModal');
    if (modal) modal.style.display = 'none';
}
function onBitrateWaveGain(val) {
    const g = parseInt(val, 10) || 0;
    const delta = g - waveGain;
    waveGain = g;
    if (wavePts) {
        wavePts = wavePts.map(v => Math.max(WAVE_MIN, Math.min(WAVE_MAX, v + delta)));
    }
    updateWaveGainLabel();
    drawBitrateWave();
}
function updateWaveGainLabel() {
    const val = document.getElementById('bitrateWaveGainVal');
    if (val) val.textContent = (waveGain >= 0 ? '+' : '') + waveGain;
    const lab = document.getElementById('bitrateWaveGainLabel');
    if (lab) lab.childNodes[0].textContent = 'Master shift: ' + (waveGain >= 0 ? '+' : '') + waveGain + ' kbps (whole wave up / down)';
}
function waveStats() {
    if (!wavePts) return null;
    const avg = Math.round(wavePts.reduce((a, b) => a + b, 0) / wavePts.length);
    const max = Math.max.apply(null, wavePts);
    return { avg, max };
}
function applyBitrateWave() {
    if (!wavePts) return;
    const st = waveStats();
    const hidden = document.getElementById('vid_bitrate_envelope');
    if (hidden) hidden.value = JSON.stringify({ points: wavePts.slice(), avg: st.avg, max: st.max });
    const auto = document.getElementById('autoVidBitrate');
    if (auto && auto.checked) {
        auto.checked = false;
        try { toggleVidBitrateAuto(false); } catch (e) {
            const c = document.getElementById('vidBitrateSliderContainer');
            if (c) c.style.display = 'flex';
        }
    }
    const slider = document.getElementById('v_bit_slider');
    const sval = document.getElementById('v_bit_val');
    if (slider) {
        slider.value = String(Math.max(500, Math.min(25000, Math.round(st.avg / 500) * 500)));
        if (sval) sval.innerText = slider.value + 'k';
    }
    const label = document.getElementById('v_bit_label');
    if (label) label.innerHTML = `🌊 Dynamic avg ${st.avg}k / peak ${st.max}k`;
    const info = document.getElementById('vidBitrateWaveInfo');
    if (info) {
        info.style.display = 'block';
        info.innerHTML = `🌊 Wave [${wavePts.join(' · ')}] kbps → target ${st.avg}k, ceiling ${st.max}k (constrained VBR)`;
    }
}
function drawBitrateWave() {
    const canvas = document.getElementById('bitrateWaveCanvas');
    const readout = document.getElementById('bitrateWaveReadout');
    if (!canvas || !wavePts) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const padL = 52, padR = 16, padT = 14, padB = 26;
    const iw = W - padL - padR, ih = H - padT - padB;
    const peak = Math.max.apply(null, wavePts.concat([1000]));
    const yMax = Math.min(WAVE_MAX, Math.ceil(peak * 1.25 / 500) * 500);
    const xs = [padL + iw * 0.06, padL + iw * 0.5, padL + iw * 0.94];
    const yOf = (v) => padT + ih - (Math.min(v, yMax) / yMax) * ih;
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = '#e2e8f0';
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px monospace';
    ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
        const v = Math.round(yMax * g / 4);
        const y = yOf(v);
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(W - padR, y);
        ctx.stroke();
        ctx.fillText(v + 'k', 6, y + 3);
    }
    const names = ['start', 'mid', 'end'];
    ctx.fillStyle = '#64748b';
    xs.forEach((x, i) => ctx.fillText(names[i], x - 12, H - 8));
    ctx.beginPath();
    ctx.moveTo(xs[0], yOf(wavePts[0]));
    ctx.lineTo(xs[1], yOf(wavePts[1]));
    ctx.lineTo(xs[2], yOf(wavePts[2]));
    ctx.lineTo(xs[2], padT + ih);
    ctx.lineTo(xs[0], padT + ih);
    ctx.closePath();
    ctx.fillStyle = 'rgba(0,122,255,0.12)';
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(xs[0], yOf(wavePts[0]));
    ctx.lineTo(xs[1], yOf(wavePts[1]));
    ctx.lineTo(xs[2], yOf(wavePts[2]));
    ctx.strokeStyle = '#007aff';
    ctx.lineWidth = 3;
    ctx.stroke();
    xs.forEach((x, i) => {
        const y = yOf(wavePts[i]);
        ctx.beginPath();
        ctx.arc(x, y, 9, 0, Math.PI * 2);
        ctx.fillStyle = (waveDragIdx === i) ? '#ff9500' : '#007aff';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#fff';
        ctx.stroke();
        ctx.fillStyle = '#0f172a';
        ctx.font = 'bold 11px monospace';
        ctx.fillText(wavePts[i] + 'k', x - 18, y - 14);
    });
    if (readout) {
        const st = waveStats();
        readout.textContent = `start ${wavePts[0]} · mid ${wavePts[1]} · end ${wavePts[2]} kbps  →  avg ${st.avg}k · peak ${st.max}k`;
    }
}
function waveCanvasPos(ev) {
    const canvas = document.getElementById('bitrateWaveCanvas');
    const r = canvas.getBoundingClientRect();
    const cx = (ev.touches && ev.touches[0]) ? ev.touches[0].clientX : ev.clientX;
    const cy = (ev.touches && ev.touches[0]) ? ev.touches[0].clientY : ev.clientY;
    return {
        x: (cx - r.left) * (canvas.width / r.width),
        y: (cy - r.top) * (canvas.height / r.height)
    };
}
function waveHitTest(p) {
    const canvas = document.getElementById('bitrateWaveCanvas');
    const W = canvas.width, H = canvas.height;
    const padL = 52, padR = 16, padT = 14, padB = 26;
    const iw = W - padL - padR, ih = H - padT - padB;
    const peak = Math.max.apply(null, wavePts.concat([1000]));
    const yMax = Math.min(WAVE_MAX, Math.ceil(peak * 1.25 / 500) * 500);
    const xs = [padL + iw * 0.06, padL + iw * 0.5, padL + iw * 0.94];
    const yOf = (v) => padT + ih - (Math.min(v, yMax) / yMax) * ih;
    for (let i = 0; i < 3; i++) {
        const dx = p.x - xs[i], dy = p.y - yOf(wavePts[i]);
        if (dx * dx + dy * dy <= 22 * 22) return i;
    }
    return -1;
}
function waveValueAtY(y) {
    const canvas = document.getElementById('bitrateWaveCanvas');
    const H = canvas.height;
    const padT = 14, padB = 26;
    const ih = H - padT - padB;
    const peak = Math.max.apply(null, wavePts.concat([1000]));
    const yMax = Math.min(WAVE_MAX, Math.ceil(peak * 1.25 / 500) * 500);
    const frac = (padT + ih - y) / ih;
    return Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(frac * yMax / 10) * 10));
}
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('bitrateWaveCanvas');
    if (!canvas) return;
    const move = (ev) => {
        if (waveDragIdx < 0 || !wavePts) return;
        if (ev.cancelable) ev.preventDefault();
        wavePts[waveDragIdx] = waveValueAtY(waveCanvasPos(ev).y);
        drawBitrateWave();
    };
    const up = () => {
        if (waveDragIdx >= 0) {
            waveDragIdx = -1;
            canvas.style.cursor = 'grab';
            drawBitrateWave();
        }
    };
    canvas.addEventListener('pointerdown', (ev) => {
        if (!wavePts) return;
        const idx = waveHitTest(waveCanvasPos(ev));
        if (idx >= 0) {
            waveDragIdx = idx;
            canvas.style.cursor = 'grabbing';
            try { canvas.setPointerCapture(ev.pointerId); } catch (e) {}
            drawBitrateWave();
        }
    });
    canvas.addEventListener('pointermove', move);
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', up);
    const modal = document.getElementById('bitrateWaveModal');
    if (modal) {
        modal.addEventListener('click', (ev) => {
            if (ev.target === modal) closeBitrateWave();
        });
    }
});
