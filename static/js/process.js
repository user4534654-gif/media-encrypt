let activeJobPollingInterval = null;
let currentJobStartTime = null;
async function startBatch(action) {
    let rawFiles = [];
    let isVaultSelection = false;
    if (action === 'scramble') {
        if (activeMediaType === 'video') {
            if (upload.files && upload.files.length > 0) {
                rawFiles = Array.from(upload.files);
            } else if (selectedVaultMedia.video) {
                rawFiles = [selectedVaultMedia.video];
                isVaultSelection = true;
            }
            if (!rawFiles.length) return alert("Select video files to encrypt first!");
            if (!encVideo.checked && !encAudio.checked) return alert("Select at least one encryption method!");
            if (encryptionMode === 'center' && !centerUpload.files.length && !selectedVaultMedia.videoCenter) {
                return alert("Select a central video file!");
            }
        } else if (activeMediaType === 'image') {
            if (imageUpload.files && imageUpload.files.length > 0) {
                rawFiles = Array.from(imageUpload.files);
            } else if (selectedVaultMedia.image) {
                rawFiles = [selectedVaultMedia.image];
                isVaultSelection = true;
            }
            if (!rawFiles.length) return alert("Select image files to encrypt first!");
            if (imgEncryptionMode === 'center' && !centerImageUpload.files.length && !selectedVaultMedia.imageCenter) {
                return alert("Select a central image file!");
            }
        } else if (activeMediaType === 'audio') {
            if (audioUpload.files && audioUpload.files.length > 0) {
                rawFiles = Array.from(audioUpload.files);
            } else if (selectedVaultMedia.audio) {
                rawFiles = [selectedVaultMedia.audio];
                isVaultSelection = true;
            }
            if (!rawFiles.length) return alert("Select audio files to encrypt first!");
        }
    } else {
        if (decryptUpload.files && decryptUpload.files.length > 0) {
            rawFiles = Array.from(decryptUpload.files);
        } else if (selectedVaultMedia.decrypt && selectedVaultMedia.decrypt.length > 0) {
            rawFiles = Array.from(selectedVaultMedia.decrypt);
            isVaultSelection = true;
        }
        if (!rawFiles.length) return alert("Select encrypted files to decrypt first!");
        if (!document.getElementById('decKey').value.trim()) return alert("Please enter the decryption key!");
    }
    const progBox = document.getElementById('progBox');
    const spinner = document.getElementById('progSpinner');
    const cancelCont = document.getElementById('progCancelContainer');
    const cancelBtn = document.getElementById('progCancelBtn');
    const statusMsg = document.getElementById('progStatusMessage');
    const keysOut = document.getElementById('keysOutput');
    const progTitle = document.getElementById('progTitle');
    const progFill = document.getElementById('progFill');
    const progText = document.getElementById('progText');
    if (progBox) progBox.style.display = 'block';
    if (spinner) {
        spinner.style.display = 'inline-block';
        spinner.style.animationPlayState = 'running';
    }
    if (cancelCont) cancelCont.style.display = 'block';
    if (cancelBtn) {
        cancelBtn.disabled = false;
        cancelBtn.innerText = '✕ Cancel Processing';
        cancelBtn.style.opacity = '1';
    }
    if (statusMsg) {
        statusMsg.style.display = 'none';
        statusMsg.innerText = '';
    }
    if (keysOut) {
        keysOut.style.display = 'none';
        keysOut.innerHTML = '';
    }
    if (progFill) {
        progFill.style.width = '0%';
        progFill.classList.remove('complete');
        progFill.classList.remove('indeterminate');
    }
    if (progText) progText.innerText = '0%';
    if (progTitle) progTitle.innerText = `Starting batch job (${rawFiles.length} file(s))...`;
    currentJobStartTime = Date.now();
    const fd = new FormData();
    fd.append('action', action);
    if (isVaultSelection) {
        fd.append('vault_filenames', JSON.stringify(rawFiles));
        let chosenFolder = 'input';
        if (action === 'scramble') {
            if (activeMediaType === 'video' && selectedVaultMedia.videoFolder) chosenFolder = selectedVaultMedia.videoFolder;
            else if (activeMediaType === 'image' && selectedVaultMedia.imageFolder) chosenFolder = selectedVaultMedia.imageFolder;
            else if (activeMediaType === 'audio' && selectedVaultMedia.audioFolder) chosenFolder = selectedVaultMedia.audioFolder;
        } else {
            chosenFolder = selectedVaultMedia.decryptFolder || 'encrypted';
        }
        fd.append('vault_folder', chosenFolder);
    } else {
        rawFiles.forEach(f => {
            fd.append('files', f);
        });
    }
    if (action === 'scramble') {
        if (activeMediaType === 'video') {
            const fmtVal = document.getElementById('v_fmt').value;
            const isInputImage = rawFiles.length > 0 && (
                typeof rawFiles[0] === 'string'
                    ? /\.(jpe?g|png|webp|avif|bmp)$/i.test(rawFiles[0])
                    : (rawFiles[0].type ? rawFiles[0].type.startsWith('image/') : /\.(jpe?g|png|webp|avif|bmp)$/i.test(rawFiles[0].name))
            );
            if (isInputImage) {
                let imgFmt = fmtVal;
                if (imgFmt === 'auto' || ['.mp4', '.mkv', '.avi', '.webm', '.mov'].includes(imgFmt)) {
                    imgFmt = (typeof activeImageFormat !== 'undefined' && activeImageFormat) ? activeImageFormat : 'auto';
                }
                fd.append('img_format', imgFmt);
                fd.append('enc_video', 'true');
                fd.append('enc_audio', 'false');
            } else {
                fd.append('enc_video', encVideo.checked); 
                fd.append('enc_audio', encAudio.checked);
                fd.append('vid_format', fmtVal); 
            }
            fd.append('cols', document.getElementById('cols').value); 
            fd.append('rows', document.getElementById('rows').value);
            fd.append('sid', document.getElementById('sid').value); 
            fd.append('vid_codec', document.getElementById('v_codec').value);
            const isAutoBitrate = document.getElementById('autoVidBitrate') ? document.getElementById('autoVidBitrate').checked : true;
            fd.append('vid_bitrate', isAutoBitrate ? 'auto' : document.getElementById('v_bit_slider').value + 'k');
            const spatialMode = document.getElementById('v_spatial_mode') ? document.getElementById('v_spatial_mode').value : 'off';
            fd.append('spatial_compression_mode', spatialMode);
            fd.append('vid_preset', document.getElementById('v_preset').value);
            const aSrAuto = document.getElementById('a_sr_auto') ? document.getElementById('a_sr_auto').checked : true;
            fd.append('aud_sr', aSrAuto ? 'auto' : document.getElementById('a_sr_slider').value);
            fd.append('aud_codec', document.getElementById('a_codec').value);
            const aBitAuto = document.getElementById('a_bit_auto') ? document.getElementById('a_bit_auto').checked : false;
            const aBitVal = document.getElementById('a_bit_slider') ? document.getElementById('a_bit_slider').value + 'k' : '320k';
            fd.append('aud_bitrate', aBitAuto ? 'auto' : aBitVal);
            fd.append('resize_w', document.getElementById('resW').value); 
            fd.append('resize_h', document.getElementById('resH').value);
            fd.append('no_scale', document.getElementById('noScale').checked);
            fd.append('center_mode', encryptionMode === 'center');
            if (encryptionMode === 'center') {
                if (centerUpload.files.length) {
                    fd.append('center_file', centerUpload.files[0]);
                } else if (selectedVaultMedia.videoCenter) {
                    fd.append('center_vault_filename', selectedVaultMedia.videoCenter);
                    if (selectedVaultMedia.videoCenterFolder) {
                        fd.append('center_vault_folder', selectedVaultMedia.videoCenterFolder);
                    }
                }
            }
            fd.append('aud_method', document.getElementById('v_aud_method').value);
            const volBgElem = document.getElementById('vol_factor_bg_slider') || document.getElementById('vol_factor_slider');
            const volCenterElem = document.getElementById('vol_factor_center_slider');
            const volBgVal = volBgElem ? (parseFloat(volBgElem.value) / 100.0) : 1.0;
            const volCenterVal = volCenterElem ? (parseFloat(volCenterElem.value) / 100.0) : 1.0;
            fd.append('vol_factor', volBgVal);
            fd.append('vol_factor_bg', volBgVal);
            fd.append('vol_factor_center', volCenterVal);
            const isDualTrack = document.getElementById('dual_track') ? document.getElementById('dual_track').checked : (document.getElementById('dualTrackPreviewToggle') ? document.getElementById('dualTrackPreviewToggle').checked : false);
            fd.append('dual_track', isDualTrack);
            fd.append('center_size', document.getElementById('center_size').value);
            fd.append('video_encrypt_mode', document.getElementById('video_encrypt_mode').value);
            fd.append('aud_track', document.getElementById('aud_track') ? document.getElementById('aud_track').value : 'both');
            fd.append('outer_end_action', document.getElementById('outer_end_action').value);
            fd.append('center_end_action', document.getElementById('center_end_action').value);            const centerAudActionElem = document.getElementById('center_aud_action');
            fd.append('center_aud_action', centerAudActionElem ? centerAudActionElem.value : 'silence');
            fd.append('export_svg', document.getElementById('exportSvg').checked);
            fd.append('use_gpu', document.getElementById('useGpu') ? document.getElementById('useGpu').checked : false);
            fd.append('save_key_file', document.getElementById('saveKeyFile') ? document.getElementById('saveKeyFile').checked : true);
            fd.append('generate_qr', document.getElementById('generateQr') ? document.getElementById('generateQr').checked : false);
            if (typeof getCustomAudioFiles === 'function') {
                const customAud = getCustomAudioFiles();
                if (customAud.fileL) {
                    fd.append('custom_audio_l', customAud.fileL);
                    fd.append('enc_custom_l', customAud.encL ? 'true' : 'false');
                }
                if (customAud.fileR) {
                    fd.append('custom_audio_r', customAud.fileR);
                    fd.append('enc_custom_r', customAud.encR ? 'true' : 'false');
                }
            }
            const enableSpatial = document.getElementById('enableSpatialZones') ? document.getElementById('enableSpatialZones').checked : false;
            if (enableSpatial && typeof getSpatialPatchConfig === 'function') {
                const patchCfg = getSpatialPatchConfig();
                if (patchCfg.patch_roi) {
                    fd.append('patch_roi', JSON.stringify(patchCfg.patch_roi));
                }
                if (patchCfg.patch_segments && patchCfg.patch_segments.length > 0) {
                    fd.append('patch_segments', JSON.stringify(patchCfg.patch_segments));
                }
                if (patchCfg.patch_intervals && patchCfg.patch_intervals.length > 0) {
                    fd.append('patch_intervals', JSON.stringify(patchCfg.patch_intervals));
                }
                fd.append('roi_invert', patchCfg.roi_invert ? 'true' : 'false');
                fd.append('optical_markers', patchCfg.optical_markers ? 'true' : 'false');
                fd.append('marker_placement', patchCfg.marker_placement || 'outside');
            }
        } else if (activeMediaType === 'image') {
            fd.append('enc_video', 'true'); 
            fd.append('enc_audio', 'false');
            fd.append('cols', document.getElementById('img_cols').value); 
            fd.append('rows', document.getElementById('img_rows').value); 
            fd.append('sid', document.getElementById('img_sid').value); 
            fd.append('img_format', activeImageFormat);
            fd.append('center_mode', imgEncryptionMode === 'center');
            if (imgEncryptionMode === 'center') {
                if (centerImageUpload.files.length) {
                    fd.append('center_file', centerImageUpload.files[0]);
                } else if (selectedVaultMedia.imageCenter) {
                    fd.append('center_vault_filename', selectedVaultMedia.imageCenter);
                    if (selectedVaultMedia.imageCenterFolder) {
                        fd.append('center_vault_folder', selectedVaultMedia.imageCenterFolder);
                    }
                }
            }
            fd.append('center_size', document.getElementById('img_center_size').value);
            fd.append('video_encrypt_mode', document.getElementById('img_video_encrypt_mode').value);
            fd.append('export_svg', document.getElementById('imgExportSvg').checked);
            fd.append('save_key_file', document.getElementById('imgSaveKeyFile') ? document.getElementById('imgSaveKeyFile').checked : true);
            fd.append('generate_qr', document.getElementById('imgGenerateQr') ? document.getElementById('imgGenerateQr').checked : false);
            const enableZones = document.getElementById('imgEnableSpatialZones');
            if (enableZones && enableZones.checked) {
                const x1 = parseFloat(document.getElementById('imgCoordX1').value) || 0.20;
                const y1 = parseFloat(document.getElementById('imgCoordY1').value) || 0.20;
                const x2 = parseFloat(document.getElementById('imgCoordX2').value) || 0.80;
                const y2 = parseFloat(document.getElementById('imgCoordY2').value) || 0.80;
                fd.append('patch_roi', JSON.stringify([x1, y1, x2, y2]));
                fd.append('roi_invert', document.getElementById('imgRoiInvert').checked ? 'true' : 'false');
                fd.append('optical_markers', document.getElementById('imgOpticalMarkers').checked ? 'true' : 'false');
            }
        } else if (activeMediaType === 'audio') {
            fd.append('enc_video', 'false'); 
            fd.append('enc_audio', 'true');
            fd.append('carrier_freq', document.getElementById('carrier_freq_slider').value);
            const audioSrAuto = document.getElementById('audio_sr_auto') ? document.getElementById('audio_sr_auto').checked : true;
            fd.append('aud_sr', audioSrAuto ? 'auto' : document.getElementById('audio_sr_slider').value); 
            fd.append('aud_codec', document.getElementById('audio_codec').value);
            const audioBitAuto = document.getElementById('audio_bit_auto') ? document.getElementById('audio_bit_auto').checked : false;
            const audioBitVal = document.getElementById('audio_bit_slider') ? document.getElementById('audio_bit_slider').value + 'k' : '320k';
            fd.append('aud_bitrate', audioBitAuto ? 'auto' : audioBitVal);
            fd.append('aud_format', document.getElementById('audio_fmt').value);
            fd.append('aud_method', document.getElementById('aud_method').value);
            fd.append('aud_splits', document.getElementById('aud_splits').value);
            fd.append('sid', document.getElementById('aud_seed').value);
            fd.append('vol_factor', parseFloat(document.getElementById('aud_vol_factor_slider').value) / 100.0);
            fd.append('aud_track', document.getElementById('audio_track_select').value);
            fd.append('save_key_file', document.getElementById('audSaveKeyFile') ? document.getElementById('audSaveKeyFile').checked : true);
            fd.append('generate_qr', document.getElementById('audGenerateQr') ? document.getElementById('audGenerateQr').checked : false);
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
        fd.append('use_gpu', document.getElementById('useGpu') ? document.getElementById('useGpu').checked : false);
    }
    try {
        const res = await fetch('/api/job/start', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.status === 'ok') {
            startJobPolling();
        } else {
            if (spinner) spinner.style.display = 'none';
            if (cancelCont) cancelCont.style.display = 'none';
            alert("Could not start processing: " + (data.message || "Unknown error"));
        }
    } catch (err) {
        if (spinner) spinner.style.display = 'none';
        if (cancelCont) cancelCont.style.display = 'none';
        openDebugger("Network error submitting batch job", err.stack || err.toString());
    }
}
function startJobPolling() {
    if (activeJobPollingInterval) {
        clearInterval(activeJobPollingInterval);
    }
    activeJobPollingInterval = setInterval(pollJobStatus, 500);
    pollJobStatus();
}
async function pollJobStatus() {
    try {
        const res = await fetch('/api/job/status');
        const data = await res.json();
        renderJobState(data);
    } catch (err) {
        console.warn("Polling status error:", err);
    }
}
function renderJobState(data) {
    if (!data || data.status === 'idle') return;
    const progBox = document.getElementById('progBox');
    const spinner = document.getElementById('progSpinner');
    const cancelCont = document.getElementById('progCancelContainer');
    const cancelBtn = document.getElementById('progCancelBtn');
    const statusMsg = document.getElementById('progStatusMessage');
    const progTitle = document.getElementById('progTitle');
    const progFill = document.getElementById('progFill');
    const progText = document.getElementById('progText');
    if (progBox) progBox.style.display = 'block';
    if (data.status === 'running') {
        if (spinner) {
            spinner.style.display = 'inline-block';
            spinner.style.animationPlayState = 'running';
        }
        if (cancelCont) cancelCont.style.display = 'block';
        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.innerText = '✕ Cancel Processing';
        }
        if (statusMsg) statusMsg.style.display = 'none';
        if (progTitle) {
            const curIdx = data.current_index || 1;
            const tot = data.total_files || 1;
            const curFile = data.current_file || '';
            progTitle.innerText = `Processing ${curIdx}/${tot}: ${curFile}`;
        }
        const pct = parseInt(data.progress) || 0;
        if (progFill) {
            progFill.style.width = `${pct}%`;
            if (pct === 0) {
                progFill.classList.add('indeterminate');
            } else {
                progFill.classList.remove('indeterminate');
            }
        }
        if (progText) {
            let display = `${pct}%`;
            if (pct > 0 && pct < 100 && currentJobStartTime) {
                const elapsedSec = (Date.now() - currentJobStartTime) / 1000;
                const remaining = (elapsedSec / pct) * (100 - pct);
                display += `  ·  ≈ ${Math.round(remaining)}s left`;
            }
            progText.innerText = display;
        }
        if (data.keys && data.keys.length > 0) {
            renderKeysOutput(data.keys);
        }
    } else if (data.status === 'completed') {
        if (activeJobPollingInterval) {
            clearInterval(activeJobPollingInterval);
            activeJobPollingInterval = null;
        }
        if (spinner) {
            spinner.style.display = 'none';
            spinner.style.animationPlayState = 'paused';
        }
        if (cancelCont) cancelCont.style.display = 'none';
        if (progTitle) progTitle.innerText = `All Files Processed! (${data.total_files} file(s))`;
        if (progFill) {
            progFill.style.width = '100%';
            progFill.classList.remove('indeterminate');
            progFill.classList.add('complete');
        }
        if (progText) progText.innerText = '100%';
        if (statusMsg) {
            statusMsg.style.display = 'block';
            statusMsg.style.background = '#e8f5e9';
            statusMsg.style.color = '#2e7d32';
            statusMsg.style.border = '1px solid #c8e6c9';
            statusMsg.innerText = '✅ Processing complete!';
        }
        if (data.keys && data.keys.length > 0) {
            renderKeysOutput(data.keys);
        }
        if (typeof loadVaultFiles === 'function') {
            loadVaultFiles(data.action === 'scramble' ? 'encrypted' : 'decrypted');
        }
    } else if (data.status === 'cancelled') {
        if (activeJobPollingInterval) {
            clearInterval(activeJobPollingInterval);
            activeJobPollingInterval = null;
        }
        if (spinner) {
            spinner.style.display = 'none';
            spinner.style.animationPlayState = 'paused';
        }
        if (cancelCont) cancelCont.style.display = 'none';
        if (progTitle) progTitle.innerText = `Processing Cancelled`;
        if (progFill) {
            progFill.classList.remove('indeterminate');
            progFill.classList.remove('complete');
        }
        if (progText) progText.innerText = 'Cancelled';
        if (statusMsg) {
            statusMsg.style.display = 'block';
            statusMsg.style.background = '#ffebee';
            statusMsg.style.color = '#c62828';
            statusMsg.style.border = '1px solid #ffcdd2';
            statusMsg.innerText = '⚠️ Processing has been cancelled.';
        }
        if (data.keys && data.keys.length > 0) {
            renderKeysOutput(data.keys);
        }
        if (typeof loadVaultFiles === 'function') {
            loadVaultFiles(data.action === 'scramble' ? 'encrypted' : 'decrypted');
        }
    } else if (data.status === 'error') {
        if (activeJobPollingInterval) {
            clearInterval(activeJobPollingInterval);
            activeJobPollingInterval = null;
        }
        if (spinner) {
            spinner.style.display = 'none';
            spinner.style.animationPlayState = 'paused';
        }
        if (cancelCont) cancelCont.style.display = 'none';
        if (progTitle) progTitle.innerText = `Processing Error`;
        if (statusMsg) {
            statusMsg.style.display = 'block';
            statusMsg.style.background = '#ffebee';
            statusMsg.style.color = '#c62828';
            statusMsg.style.border = '1px solid #ffcdd2';
            statusMsg.innerText = '❌ An error occurred during processing.';
        }
        if (data.errors && data.errors.length > 0) {
            const err = data.errors[0];
            openDebugger(`Error processing ${err.file}: ${err.error}`, err.traceback, err.diagnostic);
        }
    }
}
async function cancelProcessing() {
    const cancelBtn = document.getElementById('progCancelBtn');
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.innerText = '⏳ Cancelling...';
        cancelBtn.style.opacity = '0.7';
    }
    try {
        const res = await fetch('/api/job/cancel', { method: 'POST' });
        const data = await res.json();
        const statusMsg = document.getElementById('progStatusMessage');
        if (statusMsg) {
            statusMsg.style.display = 'block';
            statusMsg.style.background = '#ffebee';
            statusMsg.style.color = '#c62828';
            statusMsg.style.border = '1px solid #ffcdd2';
            statusMsg.innerText = '⚠️ Processing has been cancelled.';
        }
        pollJobStatus();
    } catch (err) {
        console.error("Cancel request failed:", err);
    }
}
function renderKeysOutput(keys) {
    const keysOut = document.getElementById('keysOutput');
    if (!keysOut || !keys || !keys.length) return;
    keysOut.style.display = 'block';
    keysOut.innerHTML = '';
    keys.forEach(item => {
        const itemName = item.file || item.name || '';
        const keyVal = item.key || '';
        const outFile = item.out_file || '';
        const qrFile = item.qr_file || '';
        const isK85 = keyVal.startsWith('K85:');
        const k85Badge = isK85 
            ? `<span style="font-size: 10px; background: #ede9fe; color: #6d28d9; padding: 1px 5px; border-radius: 3px; font-weight: 700; border: 1px solid #ddd6fe;" title="Algorithmic Base85 Compressed Key">K85</span>` 
            : '';
        const qrBtn = qrFile ? `
            <a href="/api/vault/download?folder=output&filename=${encodeURIComponent(qrFile)}" download="${qrFile}" class="ios-btn-small" style="text-decoration: none; padding: 2px 6px; font-size: 11px; margin: 0; background: #e8f5e9; color: #2e7d32; border: 1px solid #81c784; cursor: pointer; border-radius: 4px; font-weight: bold; display: inline-flex; align-items: center; gap: 2px;" title="Download Key QR Code">📱 QR</a>
        ` : '';
        keysOut.innerHTML += `
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; background: rgba(0,0,0,0.03); padding: 5px 8px; border-radius: 6px; border: 1px solid #e1e4e8; min-width: 0; overflow: hidden; box-sizing: border-box;">
                <span style="font-weight: 500; color: #333; font-size: 12px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; word-break: break-all; overflow-wrap: anywhere;" title="${itemName}">${itemName}</span>
                <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                    ${k85Badge}
                    <code style="background: #e1f5fe; color: #0288d1; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 12px; border: 1px dashed #0288d1; font-family: monospace;">${keyVal}</code>
                    ${qrBtn}
                    <button type="button" class="ios-btn-small" onclick="saveKeyToFile('${keyVal}', '${outFile}', this)" style="padding: 2px 6px; font-size: 11px; margin: 0; background: linear-gradient(to bottom, #ffffff 0%, #eaeaea 100%); cursor: pointer; border-radius: 4px; font-weight: bold; border: 1px solid #b0b0b0;">💾 Save</button>
                    <button type="button" class="ios-btn-small" onclick="copyKeyToClipboard('${keyVal}', this)" style="padding: 2px 6px; font-size: 11px; margin: 0; background: linear-gradient(to bottom, #ffffff 0%, #eaeaea 100%); cursor: pointer; border-radius: 4px; font-weight: bold; border: 1px solid #b0b0b0;">📋 Copy</button>
                </div>
            </div>
        `;
    });
}
function onDecKeyChanged(val) {
    val = (val || '').trim();
    const k85Badge = document.getElementById('decKeyK85Badge');
    const modeBadge = document.getElementById('decKeyModeBadge');
    const patchBadge = document.getElementById('decKeyPatchBadge');
    const spatialBadge = document.getElementById('decKeySpatialBadge');
    if (k85Badge) k85Badge.classList.toggle('hidden', !val.startsWith('K85:'));
    if (modeBadge) modeBadge.classList.toggle('hidden', !val.includes('|c') && !val.includes('|ext'));
    if (patchBadge) patchBadge.classList.toggle('hidden', !val.includes('|p:') && !val.includes('|psegs:'));
    if (spatialBadge) spatialBadge.classList.toggle('hidden', !val.includes('|roi:') && !val.includes('|psegs:'));
}
async function handleQrFileUpload(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('qr_image', file);
    try {
        const res = await fetch('/api/scan_qr', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.status === 'ok' && data.key) {
            const decKeyInput = document.getElementById('decKey');
            if (decKeyInput) {
                decKeyInput.value = data.key;
                onDecKeyChanged(data.key);
            }
            alert("✅ Decryption Key successfully extracted from QR Code!");
        } else {
            alert("Could not read QR code: " + (data.message || "Unknown error"));
        }
    } catch (err) {
        alert("Error scanning QR code: " + err.message);
    } finally {
        event.target.value = '';
    }
}
async function triggerAutoDetectMarkers() {
    const decryptUpload = document.getElementById('decryptUpload');
    let file = null;
    if (decryptUpload && decryptUpload.files && decryptUpload.files.length > 0) {
        file = decryptUpload.files[0];
    }
    if (!file && typeof selectedVaultMedia !== 'undefined' && selectedVaultMedia.decrypt && selectedVaultMedia.decrypt.length > 0) {
        const filename = selectedVaultMedia.decrypt[0];
        const folder = selectedVaultMedia.decryptFolder || 'encrypted';
        const fd = new FormData();
        fd.append('vault_filename', filename);
        fd.append('vault_folder', folder);
        return doDetectOpticalMarkers(fd);
    }
    if (!file) {
        alert("Please select or upload an encrypted media file in Step 1 first.");
        return;
    }
    const fd = new FormData();
    fd.append('file', file);
    return doDetectOpticalMarkers(fd);
}
async function doDetectOpticalMarkers(fd) {
    try {
        const res = await fetch('/api/detect_optical_markers', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.status === 'ok' && data.roi) {
            const roi = data.roi;
            const roiStr = `|roi:${roi.join(',')}`;
            const decKeyInput = document.getElementById('decKey');
            if (decKeyInput) {
                let curVal = decKeyInput.value.trim();
                if (!curVal.includes('|roi:')) {
                    decKeyInput.value = (curVal ? curVal : '10x10|seed') + roiStr;
                }
                onDecKeyChanged(decKeyInput.value);
            }
            alert(`🎯 Optical B&W Corner Markers Detected!\nROI Coordinates: [${roi.join(', ')}]`);
        } else {
            alert(data.message || "No optical markers detected in this file.");
        }
    } catch (err) {
        alert("Error detecting optical markers: " + err.message);
    }
}
document.addEventListener('DOMContentLoaded', () => {
    fetch('/api/job/status').then(r => r.json()).then(data => {
        if (data && data.status && data.status !== 'idle') {
            renderJobState(data);
            if (data.status === 'running') {
                startJobPolling();
            }
        }
    }).catch(() => {});
});
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
async function startBatchWithFormData(fd, action) {
    const progBox = document.getElementById('progBox');
    const spinner = document.getElementById('progSpinner');
    const cancelCont = document.getElementById('progCancelContainer');
    const cancelBtn = document.getElementById('progCancelBtn');
    const statusMsg = document.getElementById('progStatusMessage');
    const keysOut = document.getElementById('keysOutput');
    const progTitle = document.getElementById('progTitle');
    const progFill = document.getElementById('progFill');
    const progText = document.getElementById('progText');
    if (progBox) progBox.style.display = 'block';
    if (spinner) {
        spinner.style.display = 'inline-block';
        spinner.style.animationPlayState = 'running';
    }
    if (cancelCont) cancelCont.style.display = 'block';
    if (cancelBtn) {
        cancelBtn.disabled = false;
        cancelBtn.innerText = '✕ Cancel Processing';
        cancelBtn.style.opacity = '1';
    }
    if (statusMsg) {
        statusMsg.style.display = 'none';
        statusMsg.innerText = '';
    }
    if (keysOut) {
        keysOut.style.display = 'none';
        keysOut.innerHTML = '';
    }
    if (progFill) {
        progFill.style.width = '0%';
        progFill.classList.remove('complete');
        progFill.classList.remove('indeterminate');
    }
    if (progText) progText.innerText = '0%';
    if (progTitle) progTitle.innerText = `Starting batch job...`;
    currentJobStartTime = Date.now();
    try {
        const res = await fetch('/api/job/start', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.status === 'ok') {
            startJobPolling();
        } else {
            alert(data.error || "Failed to start job");
            if (progBox) progBox.style.display = 'none';
        }
    } catch (e) {
        alert("Error starting job: " + e.message);
        if (progBox) progBox.style.display = 'none';
    }
}
