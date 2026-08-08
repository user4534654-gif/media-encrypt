async function startBatch(action) {
    let files;
    if (action === 'scramble') {
        if (activeMediaType === 'video') {
            files = upload.files;
            if (!files.length) return alert("Select video files to encrypt first!");
            if (!encVideo.checked && !encAudio.checked) return alert("Select at least one encryption method!");
            if (encryptionMode === 'center' && !centerUpload.files.length) {
                return alert("Select a central video file!");
            }
        } else if (activeMediaType === 'image') {
            files = imageUpload.files;
            if (!files.length) return alert("Select image files to encrypt first!");
            if (imgEncryptionMode === 'center' && !centerImageUpload.files.length) {
                return alert("Select a central image file!");
            }
        } else if (activeMediaType === 'audio') {
            files = audioUpload.files;
            if (!files.length) return alert("Select audio files to encrypt first!");
        }
    } else {
        files = decryptUpload.files;
        if (!files.length) return alert("Select encrypted files to decrypt first!");
        if (!document.getElementById('decKey').value.trim()) return alert("Please enter the decryption key!");
    }
    const progBox = document.getElementById('progBox');
    const spinner = document.getElementById('progSpinner');
    if (progBox) progBox.style.display = 'block';
    if (spinner) {
        spinner.style.display = 'inline-block';
        spinner.style.animationPlayState = 'running';
    }
    const keysOut = document.getElementById('keysOutput');
    if (keysOut) keysOut.innerHTML = '';
    for (let i = 0; i < files.length; i++) {
        const progTitle = document.getElementById('progTitle');
        if (progTitle) progTitle.innerText = `Processing ${i+1}/${files.length}: ${files[i].name}`;
        const fileStartTime = Date.now();
        let lastEta = '';
        const progFill = document.getElementById('progFill');
        if (progFill) {
            progFill.style.width = '0%';
            progFill.classList.remove('complete');
            progFill.classList.remove('indeterminate');
        }
        const fd = new FormData();
        fd.append('file', files[i]); 
        fd.append('action', action); 
        fd.append('task_id', `task_${Date.now()}`);
        if (action === 'scramble') {
            if (activeMediaType === 'video') {
                fd.append('enc_video', encVideo.checked); 
                fd.append('enc_audio', encAudio.checked);
                fd.append('cols', document.getElementById('cols').value); 
                fd.append('rows', document.getElementById('rows').value);
                fd.append('sid', document.getElementById('sid').value); 
                fd.append('vid_format', document.getElementById('v_fmt').value); 
                fd.append('vid_codec', document.getElementById('v_codec').value);
                const isAutoBitrate = document.getElementById('autoVidBitrate') ? document.getElementById('autoVidBitrate').checked : true;
                fd.append('vid_bitrate', isAutoBitrate ? 'auto' : document.getElementById('v_bit_slider').value + 'k');
                fd.append('vid_preset', document.getElementById('v_preset').value);
                const aSrAuto = document.getElementById('a_sr_auto') ? document.getElementById('a_sr_auto').checked : true;
                fd.append('aud_sr', aSrAuto ? 'auto' : document.getElementById('a_sr_slider').value);
                fd.append('aud_codec', document.getElementById('a_codec').value);
                fd.append('aud_bitrate', document.getElementById('a_bit').value);
                fd.append('resize_w', document.getElementById('resW').value); 
                fd.append('resize_h', document.getElementById('resH').value);
                fd.append('no_scale', document.getElementById('noScale').checked);
                fd.append('center_mode', encryptionMode === 'center');
                if (encryptionMode === 'center' && centerUpload.files.length) {
                    fd.append('center_file', centerUpload.files[0]);
                }
                fd.append('aud_method', document.getElementById('v_aud_method').value);
                fd.append('aud_splits', document.getElementById('v_aud_splits').value);
                fd.append('vol_factor', parseFloat(document.getElementById('vol_factor_slider').value) / 100.0);
                fd.append('dual_track', document.getElementById('dual_track').checked);
                fd.append('center_size', document.getElementById('center_size').value);
                fd.append('video_encrypt_mode', document.getElementById('video_encrypt_mode').value);
                fd.append('aud_track', document.getElementById('aud_track').value);
                fd.append('outer_end_action', document.getElementById('outer_end_action').value);
                fd.append('center_end_action', document.getElementById('center_end_action').value);
                fd.append('center_aud_action', document.getElementById('center_aud_action').value);
                fd.append('export_svg', document.getElementById('exportSvg').checked);
            } else if (activeMediaType === 'image') {
                fd.append('enc_video', 'true'); 
                fd.append('enc_audio', 'false');
                fd.append('cols', document.getElementById('img_cols').value); 
                fd.append('rows', document.getElementById('img_rows').value);
                fd.append('sid', document.getElementById('img_sid').value); 
                fd.append('img_format', activeImageFormat);
                fd.append('center_mode', imgEncryptionMode === 'center');
                if (imgEncryptionMode === 'center' && centerImageUpload.files.length) {
                    fd.append('center_file', centerImageUpload.files[0]);
                }
                fd.append('center_size', document.getElementById('img_center_size').value);
                fd.append('video_encrypt_mode', document.getElementById('img_video_encrypt_mode').value);
                fd.append('export_svg', document.getElementById('imgExportSvg').checked);
            } else if (activeMediaType === 'audio') {
                fd.append('enc_video', 'false'); 
                fd.append('enc_audio', 'true');
                fd.append('carrier_freq', document.getElementById('carrier_freq_slider').value);
                const audioSrAuto = document.getElementById('audio_sr_auto') ? document.getElementById('audio_sr_auto').checked : true;
                fd.append('aud_sr', audioSrAuto ? 'auto' : document.getElementById('audio_sr_slider').value); 
                fd.append('aud_codec', document.getElementById('audio_codec').value);
                fd.append('aud_bitrate', document.getElementById('audio_bit').value);
                fd.append('aud_format', document.getElementById('audio_fmt').value);
                fd.append('aud_method', document.getElementById('aud_method').value);
                fd.append('aud_splits', document.getElementById('aud_splits').value);
                fd.append('sid', document.getElementById('aud_seed').value);
                fd.append('vol_factor', parseFloat(document.getElementById('aud_vol_factor_slider').value) / 100.0);
                fd.append('aud_track', document.getElementById('audio_track_select').value);
            }
        } else {
            fd.append('key', document.getElementById('decKey').value);
            fd.append('vid_format', 'auto'); 
            fd.append('vid_codec', 'auto');
            fd.append('vid_bitrate', 'auto');
            fd.append('vid_preset', 'auto');
            fd.append('aud_sr', 'auto'); 
            fd.append('aud_codec', 'auto');
            fd.append('aud_bitrate', 'auto');
        }
        const poll = setInterval(async () => {
            try {
                const res = await fetch(`/api/progress?task_id=${fd.get('task_id')}`);
                const data = await res.json();
                const fill = document.getElementById('progFill');
                const txt = document.getElementById('progText');
                const pct = parseInt(data.progress) || 0;
                if (fill) {
                    fill.style.width = `${pct}%`;
                    if (pct === 0) {
                        fill.classList.add('indeterminate');
                    } else {
                        fill.classList.remove('indeterminate');
                    }
                }
                if (txt) {
                    const elapsedSec = (Date.now() - fileStartTime) / 1000;
                    let display = `${pct}%` + lastEta;
                    if (pct > 0 && pct < 100) {
                        const remaining = (elapsedSec / pct) * (100 - pct);
                        lastEta = `  ·  ≈ ${Math.round(remaining)}s left`;
                        display = `${pct}%${lastEta}`;
                    }
                    txt.innerText = display;
                }
            } catch (err) {}
        }, 500);
        try {
            const res = await fetch('/api/process', { method: 'POST', body: fd });
            clearInterval(poll);
            const result = await res.json();
            const fill = document.getElementById('progFill');
            const txt = document.getElementById('progText');
            if (fill) {
                fill.style.width = `100%`;
                fill.classList.remove('indeterminate');
                fill.classList.add('complete');
            }
            if (txt) txt.innerText = `100%`;
            if (result.status === 'error') {
                openDebugger(`Error processing ${files[i].name}: ${result.message}`, result.traceback, result.diagnostic);
            } else if (result.key && keysOut) {
                const outFile = result.file ? result.file.split(/[\\/]/).pop() : '';
                keysOut.innerHTML += `
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; background: rgba(0,0,0,0.03); padding: 5px 8px; border-radius: 6px; border: 1px solid #e1e4e8; word-break: break-all;">
                        <span style="font-weight: 500; color: #333; font-size: 12px; max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${files[i].name}">${files[i].name}</span>
                        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                            <code style="background: #e1f5fe; color: #0288d1; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 12px; border: 1px dashed #0288d1; font-family: monospace;">${result.key}</code>
                            <button type="button" class="ios-btn-small" onclick="saveKeyToFile('${result.key}', '${outFile}', this)" style="padding: 2px 6px; font-size: 11px; margin: 0; background: linear-gradient(to bottom, #ffffff 0%, #eaeaea 100%); cursor: pointer; border-radius: 4px; font-weight: bold; border: 1px solid #b0b0b0;">💾 Save</button>
                            <button type="button" class="ios-btn-small" onclick="copyKeyToClipboard('${result.key}', this)" style="padding: 2px 6px; font-size: 11px; margin: 0; background: linear-gradient(to bottom, #ffffff 0%, #eaeaea 100%); cursor: pointer; border-radius: 4px; font-weight: bold; border: 1px solid #b0b0b0;">📋 Copy</button>
                        </div>
                    </div>
                `;
            }
        } catch (err) {
            clearInterval(poll);
            openDebugger(`Network error processing ${files[i].name}`, err.stack || err.toString());
        }
    }
    const title = document.getElementById('progTitle');
    if (title) title.innerText = "All Files Processed!";
    if (spinner) {
        spinner.style.display = 'none';
        spinner.style.animationPlayState = 'paused';
    }
    switchMainTab('vault');
    if (action === 'scramble') {
        switchFolder('encrypted');
    } else {
        switchFolder('decrypted');
    }
}
function openDebugger(errorMessage, tracebackText, diagnostic) {
    const errorEl = document.getElementById('debugErrorMessage');
    const locationEl = document.getElementById('debugLocation');
    const rootCauseEl = document.getElementById('debugRootCause');
    const helpEl = document.getElementById('debugDiagnosticHelp');
    const snippetContainer = document.getElementById('debugCodeSnippetContainer');
    const snippetEl = document.getElementById('debugCodeSnippet');
    const localsBody = document.getElementById('debugLocalsBody');
    const tbEl = document.getElementById('debugTraceback');
    const modal = document.getElementById('debugModal');
    const diag = diagnostic || {};
    if (errorEl) {
        errorEl.innerText = diag.error_type ? `${diag.error_type}: ${diag.error_message || errorMessage}` : (errorMessage || 'Unknown Error');
    }
    if (locationEl) {
        locationEl.innerText = diag.file ? `Location: ${diag.file}:${diag.line || 0} in ${diag.function || 'unknown'}()` : 'Location: Unknown';
    }
    if (rootCauseEl) {
        rootCauseEl.innerText = diag.root_cause || 'Process execution interrupted by runtime exception.';
    }
    if (helpEl) {
        helpEl.innerText = diag.suggestion || 'Inspect the stack traceback and local variables below for details.';
    }
    if (snippetEl && snippetContainer) {
        if (diag.code_line && diag.code_line !== 'N/A') {
            snippetEl.innerText = `Line ${diag.line}: ${diag.code_line}`;
            snippetContainer.style.display = 'block';
        } else {
            snippetContainer.style.display = 'none';
        }
    }
    if (localsBody) {
        localsBody.innerHTML = '';
        const vars = diag.local_vars || {};
        const keys = Object.keys(vars);
        if (keys.length > 0) {
            keys.forEach(k => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid #e0e0e0';
                tr.innerHTML = `<td style="padding: 6px 10px; font-weight: bold; color: #0066cc;">${k}</td><td style="padding: 6px 10px; color: #333; word-break: break-all;">${vars[k]}</td>`;
                localsBody.appendChild(tr);
            });
        } else {
            localsBody.innerHTML = '<tr><td colspan="2" style="padding: 8px 10px; color: #888;">No local variables captured at failure.</td></tr>';
        }
    }
    if (tbEl) {
        tbEl.innerText = diag.traceback || tracebackText || "No Python traceback was generated.";
    }
    if (modal) modal.classList.remove('hidden');
}
function closeDebugger() {
    const modal = document.getElementById('debugModal');
    if (modal) modal.classList.add('hidden');
}
function copyTracebackToClipboard() {
    const errorEl = document.getElementById('debugErrorMessage');
    const tbEl = document.getElementById('debugTraceback');
    const copyBtn = document.getElementById('copyDebugLogBtn');
    const errorText = errorEl ? errorEl.innerText : '';
    const tracebackText = tbEl ? tbEl.innerText : '';
    const log = `Error: ${errorText}\n\nTraceback:\n${tracebackText}`;
    navigator.clipboard.writeText(log).then(() => {
        if (copyBtn) {
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = "✅ Copied!";
            setTimeout(() => {
                copyBtn.innerHTML = originalText;
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        alert('Failed to copy traceback to clipboard.');
    });
}
async function saveKeyToFile(key, filename, btn) {
    if (!filename) {
        alert("Key saved automatically next to the encrypted file.");
        return;
    }
    try {
        const res = await fetch('/api/save_key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename, key: key })
        });
        const data = await res.json();
        if (data.success) {
            const originalText = btn.innerHTML;
            btn.innerHTML = "✅ Saved";
            btn.style.color = "#34c759";
            btn.style.borderColor = "#34c759";
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.color = "";
                btn.style.borderColor = "#b0b0b0";
            }, 1500);
        } else {
            alert("Failed to save key file: " + (data.error || "unknown error"));
        }
    } catch (err) {
        alert("Failed to save key file.");
    }
}
function copyKeyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.innerHTML;
        btn.innerHTML = "✅ Copied!";
        btn.style.color = "#34c759";
        btn.style.borderColor = "#34c759";
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.color = "";
            btn.style.borderColor = "#b0b0b0";
        }, 1500);
    }).catch(err => {
        console.error('Failed to copy key: ', err);
        alert('Failed to copy key to clipboard.');
    });
}
