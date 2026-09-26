
let waveRest = null;    
let waveZone = null;    
let waveCurve = 'rest'; 
let waveGain = 0;       
let waveDragIdx = -1;
const WAVE_MIN = 100;
const WAVE_MAX = 25000;
const WAVE_MAX_PTS = 100;
const WAVE_COLORS = { rest: '#007aff', zone: '#22c55e' };
function waveClamp(v) {
    return Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(v / 10) * 10));
}
function waveActive() {
    return waveCurve === 'zone' ? waveZone : waveRest;
}
function waveActiveColor() {
    return WAVE_COLORS[waveCurve] || WAVE_COLORS.rest;
}
function waveCount() {
    const el = document.getElementById('bitrateWaveCount');
    let n = el ? parseInt(el.value, 10) : 3;
    if (!isFinite(n)) n = 3;
    return Math.max(2, Math.min(WAVE_MAX_PTS, n));
}
function waveResample(pts, n) {
    pts = (pts && pts.length) ? pts.slice() : [3000];
    if (pts.length === 1) pts.push(pts[0]);
    if (n <= 1) return [pts[0]];
    const out = [];
    for (let i = 0; i < n; i++) {
        const t = i * (pts.length - 1) / (n - 1);
        const i0 = Math.floor(t), i1 = Math.min(pts.length - 1, i0 + 1);
        const f = t - i0;
        out.push(waveClamp(pts[i0] * (1 - f) + pts[i1] * f));
    }
    return out;
}
function waveAvg(pts) {
    if (!pts || !pts.length) return 0;
    return Math.round(pts.reduce((a, b) => a + b, 0) / pts.length);
}
function waveSeedDefaults(n) {
    n = n || waveCount();
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
    return waveResample([left, mid, right], n);
}
function switchWaveCurve(which) {
    waveCurve = (which === 'zone') ? 'zone' : 'rest';
    if (waveCurve === 'zone' && !waveZone) {
        waveZone = (waveRest && waveRest.length ? waveRest.slice() : waveSeedDefaults());
    }
    const bR = document.getElementById('waveCurveRest');
    const bZ = document.getElementById('waveCurveZone');
    if (bR) bR.classList.toggle('active', waveCurve === 'rest');
    if (bZ) bZ.classList.toggle('active', waveCurve === 'zone');
    waveDragIdx = -1;
    drawBitrateWave();
}
function openBitrateWave() {
    const modal = document.getElementById('bitrateWaveModal');
    if (!modal) return;
    if (!waveRest) {
        try {
            const raw = document.getElementById('vid_bitrate_envelope').value;
            if (raw) {
                const env = JSON.parse(raw);
                if (env && Array.isArray(env.points) && env.points.length >= 2
                        && env.points.length <= WAVE_MAX_PTS) {
                    waveRest = env.points.map(v => Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(v))));
                    const cnt = document.getElementById('bitrateWaveCount');
                    if (cnt) cnt.value = String(waveRest.length);
                    if (Array.isArray(env.zone_points) && env.zone_points.length >= 2
                            && env.zone_points.length <= WAVE_MAX_PTS) {
                        waveZone = waveResample(
                            env.zone_points.map(v => Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(v)))),
                            waveRest.length);
                    }
                }
            }
        } catch (e) {}
        if (!waveRest) waveRest = waveSeedDefaults();
    } else {
        const n = waveCount();
        waveRest = waveResample(waveRest, n);
        if (waveZone) waveZone = waveResample(waveZone, n);
    }
    waveCurve = 'rest';
    const bR = document.getElementById('waveCurveRest');
    const bZ = document.getElementById('waveCurveZone');
    if (bR) bR.classList.add('active');
    if (bZ) bZ.classList.remove('active');
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
    const n = waveCount();
    waveRest = waveSeedDefaults(n);
    waveZone = null;
    waveCurve = 'rest';
    const bR = document.getElementById('waveCurveRest');
    const bZ = document.getElementById('waveCurveZone');
    if (bR) bR.classList.add('active');
    if (bZ) bZ.classList.remove('active');
    waveGain = 0;
    const gain = document.getElementById('bitrateWaveGain');
    if (gain) gain.value = '0';
    updateWaveGainLabel();
    drawBitrateWave();
}
function onBitrateWaveCount(val) {
    const n = Math.max(2, Math.min(WAVE_MAX_PTS, parseInt(val, 10) || 3));
    const cnt = document.getElementById('bitrateWaveCount');
    if (cnt) cnt.value = String(n);
    waveRest = waveResample(waveRest && waveRest.length ? waveRest : waveSeedDefaults(n), n);
    if (waveZone) waveZone = waveResample(waveZone, n);
    drawBitrateWave();
}
function clearBitrateWave() {
    waveRest = null;
    waveZone = null;
    waveCurve = 'rest';
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
    const pts = waveActive();
    if (pts) {
        const shifted = pts.map(v => Math.max(WAVE_MIN, Math.min(WAVE_MAX, v + delta)));
        if (waveCurve === 'zone') waveZone = shifted;
        else waveRest = shifted;
    }
    updateWaveGainLabel();
    drawBitrateWave();
}
function updateWaveGainLabel() {
    const val = document.getElementById('bitrateWaveGainVal');
    if (val) val.textContent = (waveGain >= 0 ? '+' : '') + waveGain;
    const lab = document.getElementById('bitrateWaveGainLabel');
    if (lab) lab.childNodes[0].textContent = 'Master shift (' + waveCurve + '): ' + (waveGain >= 0 ? '+' : '') + waveGain + ' kbps (whole curve up / down)';
}
function waveDuration() {
    try {
        const lb = window._lastBitrates || null;
        if (lb && isFinite(lb.durationSec) && lb.durationSec > 0) return lb.durationSec;
    } catch (e) {}
    return null;
}
function applyBitrateWave() {
    if (!waveRest) return;
    const avg = waveAvg(waveRest);
    const max = Math.max.apply(null, waveRest);
    const env = { points: waveRest.slice(), avg: avg, max: max };
    const dur = waveDuration();
    if (dur) env.duration = Math.round(dur * 100) / 100;
    let steerNote = '';
    if (waveZone && waveZone.length === waveRest.length) {
        env.zone_points = waveZone.slice();
        const zAvg = waveAvg(waveZone);
        const modeSel = document.getElementById('v_spatial_mode');
        if (modeSel) {
            modeSel.value = 'priority';
            try { toggleZonePriority('priority'); } catch (e) {}
        }
        if (zAvg > avg) {
            const autoS = Math.max(10, Math.min(85, Math.round(70 * (1 - avg / zAvg))));
            const sSlider = document.getElementById('zone_priority_strength');
            if (sSlider) {
                sSlider.value = String(autoS);
                const sVal = document.getElementById('zone_priority_val');
                if (sVal) sVal.innerText = String(autoS);
            }
            steerNote = ` + Zone Priority ON (green avg ${zAvg}k vs blue ${avg}k${dur ? ', dynamic along timeline' : ', static fallback strength ' + autoS} )`;
        } else {
            steerNote = ` (green avg ${zAvg}k ≤ blue — steering stays on fallback strength)`;
        }
    }
    const hidden = document.getElementById('vid_bitrate_envelope');
    if (hidden) hidden.value = JSON.stringify(env);
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
        slider.value = String(Math.max(500, Math.min(25000, Math.round(avg / 500) * 500)));
        if (sval) sval.innerText = slider.value + 'k';
    }
    const label = document.getElementById('v_bit_label');
    if (label) label.innerHTML = `Dynamic avg ${avg}k / peak ${max}k`;
    const info = document.getElementById('vidBitrateWaveInfo');
    if (info) {
        info.style.display = 'block';
        const preview = waveRest.length <= 8
            ? `[${waveRest.join(' · ')}] kbps`
            : `${waveRest.length} pts (${waveRest[0]}k … ${waveRest[waveRest.length - 1]}k)`;
        info.innerHTML = `Wave ${preview} → target ${avg}k, ceiling ${max}k (constrained VBR)${steerNote}`;
    }
}
function waveGeom(pts) {
    const canvas = document.getElementById('bitrateWaveCanvas');
    const W = canvas.width, H = canvas.height;
    const padL = 52, padR = 16, padT = 14, padB = 26;
    const iw = W - padL - padR, ih = H - padT - padB;
    const n = pts.length;
    const peak = Math.max.apply(null, pts.concat(waveZone || [1000]));
    const yMax = Math.min(WAVE_MAX, Math.ceil(peak * 1.25 / 500) * 500);
    const xs = [];
    for (let i = 0; i < n; i++) {
        xs.push(n === 1 ? padL + iw / 2 : padL + iw * (0.06 + 0.88 * i / (n - 1)));
    }
    const yOf = (v) => padT + ih - (Math.min(v, yMax) / yMax) * ih;
    return { W, H, padL, padR, padT, padB, iw, ih, n, yMax, xs, yOf };
}
function drawBitrateWave() {
    const canvas = document.getElementById('bitrateWaveCanvas');
    const readout = document.getElementById('bitrateWaveReadout');
    const pts = waveActive();
    if (!canvas || !pts) return;
    const ctx = canvas.getContext('2d');
    const g = waveGeom(pts);
    const { W, H, padL, padR, padT, xs, yOf, n } = g;
    const color = waveActiveColor();
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = '#e2e8f0';
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px monospace';
    ctx.lineWidth = 1;
    for (let gi = 0; gi <= 4; gi++) {
        const v = Math.round(g.yMax * gi / 4);
        const y = yOf(v);
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(W - padR, y);
        ctx.stroke();
        ctx.fillText(v + 'k', 6, y + 3);
    }
    ctx.fillStyle = '#64748b';
    if (n > 0) {
        ctx.fillText('start', xs[0] - 12, H - 8);
        ctx.fillText('end', xs[n - 1] - 12, H - 8);
        if (n > 2) ctx.fillText('·' + n + ' pts·', xs[Math.floor(n / 2)] - 18, H - 8);
    }
    const other = (waveCurve === 'zone') ? waveRest : waveZone;
    const otherColor = (waveCurve === 'zone') ? WAVE_COLORS.rest : WAVE_COLORS.zone;
    if (other && other.length === n) {
        ctx.beginPath();
        ctx.moveTo(xs[0], yOf(other[0]));
        for (let i = 1; i < n; i++) ctx.lineTo(xs[i], yOf(other[i]));
        ctx.strokeStyle = otherColor;
        ctx.globalAlpha = 0.35;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.globalAlpha = 1.0;
    }
    ctx.beginPath();
    ctx.moveTo(xs[0], yOf(pts[0]));
    for (let i = 1; i < n; i++) ctx.lineTo(xs[i], yOf(pts[i]));
    ctx.lineTo(xs[n - 1], padT + g.ih);
    ctx.lineTo(xs[0], padT + g.ih);
    ctx.closePath();
    ctx.fillStyle = (waveCurve === 'zone') ? 'rgba(34,197,94,0.12)' : 'rgba(0,122,255,0.12)';
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(xs[0], yOf(pts[0]));
    for (let i = 1; i < n; i++) ctx.lineTo(xs[i], yOf(pts[i]));
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    const showVals = n <= 12;
    const r = n > 40 ? 4 : 7;
    for (let i = 0; i < n; i++) {
        const y = yOf(pts[i]);
        ctx.beginPath();
        ctx.arc(xs[i], y, (waveDragIdx === i) ? r + 2 : r, 0, Math.PI * 2);
        ctx.fillStyle = (waveDragIdx === i) ? '#ff9500' : color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#fff';
        ctx.stroke();
        if (showVals) {
            ctx.fillStyle = '#0f172a';
            ctx.font = 'bold 11px monospace';
            ctx.fillText(pts[i] + 'k', xs[i] - 18, y - 14);
        }
    }
    if (readout) {
        const avg = waveAvg(pts);
        let txt = `${waveCurve} ${n} pts (start ${pts[0]}k … end ${pts[n - 1]}k) → avg ${avg}k`;
        if (waveCurve === 'rest' && waveZone) txt += ` · zone avg ${waveAvg(waveZone)}k`;
        if (waveCurve === 'zone' && waveRest) txt += ` · rest avg ${waveAvg(waveRest)}k`;
        readout.textContent = txt;
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
    const pts = waveActive();
    if (!pts) return -1;
    const g = waveGeom(pts);
    const n = pts.length;
    const hitR = Math.max(10, Math.min(22, g.iw / Math.max(1, n)));
    for (let i = 0; i < n; i++) {
        const dx = p.x - g.xs[i], dy = p.y - g.yOf(pts[i]);
        if (dx * dx + dy * dy <= hitR * hitR) return i;
    }
    return -1;
}
function waveValueAtY(y) {
    const pts = waveActive() || [1000];
    const g = waveGeom(pts);
    const frac = (g.padT + g.ih - y) / g.ih;
    return Math.max(WAVE_MIN, Math.min(WAVE_MAX, Math.round(frac * g.yMax / 10) * 10));
}
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('bitrateWaveCanvas');
    if (!canvas) return;
    const move = (ev) => {
        if (waveDragIdx < 0) return;
        const pts = waveActive();
        if (!pts) return;
        if (ev.cancelable) ev.preventDefault();
        pts[waveDragIdx] = waveValueAtY(waveCanvasPos(ev).y);
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
        if (!waveActive()) return;
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
