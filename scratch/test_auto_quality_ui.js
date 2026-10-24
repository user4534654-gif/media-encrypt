// Headless smoke test for static/js/auto_quality.js (no DOM library needed).
// Usage: node scratch/test_auto_quality_ui.js
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');

function makeEl(id, props) {
    return Object.assign({
        id: id,
        value: '',
        checked: false,
        textContent: '',
        innerText: '',
        innerHTML: '',
        style: {},
        classList: {
            _s: new Set(),
            add(c) { this._s.add(c); },
            remove(c) { this._s.delete(c); },
            toggle(c, on) { if (on === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); } else if (on) this._s.add(c); else this._s.delete(c); },
            contains(c) { return this._s.has(c); }
        },
        addEventListener() {}
    }, props || {});
}

const els = {};
function el(id, props) { els[id] = makeEl(id, props); return els[id]; }

// DOM stubs
el('autoQualityToggle', { checked: true });
el('autoQualityPct', { value: '20' });
el('autoQualityPctVal');
el('autoQualityTargetVal');
el('autoQualityReadout');
el('autoQualityBody');
el('autoQualityWaveHint');
el('vidBitrateSliderContainer', { style: { display: 'none' } });
el('v_bit_slider', { value: '3000' });
el('v_bit_val');
el('v_bit_label_text');
el('vid_bitrate_envelope', { value: '' });
el('vidBitrateWaveInfo');
el('bitrateWaveBtn');
el('a_bit_auto', { checked: true });
el('a_bit_slider', { value: '320' });
el('vidQualityTabBasic');
el('vidQualityTabExtended');
el('vidQualityPaneBasic');
el('vidQualityPaneExtended');

const sandbox = {
    document: {
        getElementById: (id) => els[id] || null,
        addEventListener: () => {}
    },
    window: {
        _lastBitrates: { bg: 600, center: 0, max: 600, durationSec: 600, sizeBytes: 100 * 1024 * 1024 },
        _lastVaultMediaSize: 0,
        _lastVaultMediaDuration: 0
    },
    console: console,
    Math: Math,
    parseInt: parseInt,
    parseFloat: parseFloat,
    isFinite: isFinite,
    JSON: JSON,
    String: String,
    Number: Number,
    Object: Object,
    Array: Array,
    setTimeout: setTimeout
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'static/js/auto_quality.js'), 'utf8'), sandbox);

let failures = 0;
function check(name, cond, extra) {
    if (cond) { console.log('  OK   ' + name); }
    else { console.log('  FAIL ' + name + (extra !== undefined ? ' -> ' + extra : '')); failures++; }
}

// 1. State
const st = sandbox.getAutoQualityState();
check('state enabled', st.enabled === true, JSON.stringify(st));
check('state pct = 20', st.pct === 20, st.pct);

// 2. Readout math: 100 MB input, 600 s, +20%, 192k audio
sandbox.updateAutoQualityReadout();
const target = els['autoQualityTargetVal'].textContent;
const readout = els['autoQualityReadout'].textContent;
check('target shows 120.0 MB', target === '120.0 MB', target);
check('readout mentions input + target', readout.includes('100.0 MB') && readout.includes('120.0 MB'), readout);
check('readout video bitrate ~1452k', /1452k/.test(readout), readout);
check('label shows the auto bitrate', els['v_bit_label_text'].textContent.indexOf('Auto Quality') >= 0, els['v_bit_label_text'].textContent);

// 3. Manual mode: the slider becomes visible and the label switches back
sandbox.setAutoQualityEnabled(false);
check('manual mode shows the slider', els['vidBitrateSliderContainer'].style.display === 'flex', els['vidBitrateSliderContainer'].style.display);
check('manual mode label', els['v_bit_label_text'].textContent.indexOf('Max Dynamic Bitrate') === 0, els['v_bit_label_text'].textContent);
check('manual mode seeds the slider', els['v_bit_slider'].value === '1500', els['v_bit_slider'].value);

// 4. Auto mode + an applied wave -> the wave is cleared
els['vid_bitrate_envelope'].value = JSON.stringify({ points: [1000, 2000, 1500] });
sandbox.setAutoQualityEnabled(true);
check('auto mode clears the wave', els['vid_bitrate_envelope'].value === '', els['vid_bitrate_envelope'].value);
check('auto mode hides the manual slider', els['vidBitrateSliderContainer'].style.display === 'none');
check('wave button disabled in auto mode', els['bitrateWaveBtn'].disabled === true);

// 5. Clamp warning: a 100 MB source in 10 s asks for ~84 Mbps -> clamped
sandbox.window._lastBitrates.durationSec = 10;
els['autoQualityPct'].value = '100';
sandbox.onAutoQualityPct('100');
check('max target clamped warning', els['autoQualityReadout'].classList.contains('auto-quality-warn'), els['autoQualityReadout'].textContent);
check('clamped readout mentions the ceiling', /clamped/.test(els['autoQualityReadout'].textContent), els['autoQualityReadout'].textContent);
sandbox.window._lastBitrates.durationSec = 600;

// 6. Sub-tabs
sandbox.switchVidQualityTab('extended');
check('extended pane visible', !els['vidQualityPaneExtended'].classList.contains('hidden'));
check('basic pane hidden', els['vidQualityPaneBasic'].classList.contains('hidden'));

console.log('RESULT: ' + (failures ? 'FAIL' : 'PASS'));
process.exit(failures ? 1 : 0);
