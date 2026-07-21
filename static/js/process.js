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
        
        const progFill = document.getElementById('progFill');
        if (progFill) {
            progFill.style.width = '0%';
            progFill.classList.remove('complete');
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
                fd.append('aud_sr', document.getElementById('a_sr').value); 
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
                fd.append('aud_sr', document.getElementById('audio_sr').value); 
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
                if (fill) fill.style.width = `${data.progress}%`;
                if (txt) txt.innerText = `${data.progress}%`;
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
                fill.classList.add('complete');
            }
            if (txt) txt.innerText = `100%`;
            
            if (result.status === 'error') {
                openDebugger(`Error processing ${files[i].name}: ${result.message}`, result.traceback);
            } else if (result.key && keysOut) {
                keysOut.innerHTML += `
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; background: rgba(0,0,0,0.03); padding: 5px 8px; border-radius: 6px; border: 1px solid #e1e4e8; word-break: break-all;">
                        <span style="font-weight: 500; color: #333; font-size: 12px; max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${files[i].name}">${files[i].name}</span>
                        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                            <code style="background: #e1f5fe; color: #0288d1; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 12px; border: 1px dashed #0288d1; font-family: monospace;">${result.key}</code>
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

function openDebugger(errorMessage, tracebackText) {
    const errorEl = document.getElementById('debugErrorMessage');
    const helpEl = document.getElementById('debugDiagnosticHelp');
    const tbEl = document.getElementById('debugTraceback');
    const modal = document.getElementById('debugModal');
    
    if (errorEl) errorEl.innerText = errorMessage;
    if (tbEl) tbEl.innerText = tracebackText || "No Python traceback was generated.";
    
    let recommendations = "Check that the Python packages 'opencv-python', 'scipy', and 'imageio-ffmpeg' are properly installed on your machine. If resolving video, ensure the source files are not corrupted and codecs are valid.";
    const lowerMsg = errorMessage.toLowerCase();
    
    if (lowerMsg.includes('ffmpeg') || lowerMsg.includes('ffprobe')) {
        recommendations = "FFmpeg binary execution failed. Please verify that 'imageio-ffmpeg' is installed in pip, or that FFmpeg is added to your system's PATH. If on Windows, try running pip install imageio-ffmpeg.";
    } else if (lowerMsg.includes('dimension') || lowerMsg.includes('grid') || lowerMsg.includes('columns') || lowerMsg.includes('rows') || lowerMsg.includes('split')) {
        recommendations = "Grid dimensions calculations mismatch. Make sure columns and rows count is greater than 1. If Center Mode is activated, ensure the columns and rows size is large enough to contain the central 1/4 layout.";
    } else if (lowerMsg.includes('seed') || lowerMsg.includes('key') || lowerMsg.includes('unscramble')) {
        recommendations = "Key error or seed hash parsing crash. Ensure you pasted the exact encryption key string (e.g. 10x10|myseed|a) and did not leave leading/trailing white spaces.";
    } else if (lowerMsg.includes('codec') || lowerMsg.includes('format')) {
        recommendations = "Media encoding error. The selected codec is incompatible with the selected container format. Try setting both format and codec to 'Auto' to let the server match the original input characteristics.";
    } else if (lowerMsg.includes('permission') || lowerMsg.includes('denied') || lowerMsg.includes('write')) {
        recommendations = "Operating system permission block. Verify that the server has write access permissions to the 'media_encrypt_vault' folders in the project directory.";
    }
    
    if (helpEl) helpEl.innerText = recommendations;
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
