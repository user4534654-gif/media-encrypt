async function loadVault() {
    const res = await fetch(`/api/vault?folder=${activeFolder}`);
    const data = await res.json();
    const grid = document.getElementById('vaultGrid');
    if (!grid) return;
    grid.innerHTML = '';
    if (!data.files || data.files.length === 0) {
        grid.innerHTML = '<p style="color:#666; grid-column: 1 / -1; text-align:center; font-weight:bold; margin-top:20px;">Directory is empty.</p>';
        return;
    }
    data.files.forEach(f => {
        const isVideo = f.match(/\.(mp4|mkv|avi|webm|mov|m4v|3gp)$/i);
        const isAudio = f.match(/\.(mp3|wav|ogg|flac|m4a)$/i);
        const isImage = f.match(/\.(jpg|jpeg|png|bmp|gif|webp|avif)$/i);
        let preview = '';
        if (isImage) {
            preview = `<img src="/vault/${activeFolder}/${encodeURIComponent(f)}" style="width: 100px; height: 75px; object-fit: cover; border-radius: 6px; border: 1px solid #c8c7cc; margin-bottom: 5px;" alt="Image preview">`;
        } else if (isVideo) {
            preview = `
                <div style="width: 100px; height: 75px; position: relative; border-radius: 6px; border: 1px solid #c8c7cc; overflow: hidden; margin-bottom: 5px; background: rgba(0,0,0,0.05); display: flex; align-items: center; justify-content: center;">
                    <div class="video-fallback" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 2.2em; z-index: 1;">🎬</div>
                    <video src="/vault/${activeFolder}/${encodeURIComponent(f)}#t=0.1" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 2; display: none;" preload="metadata" muted onloadedmetadata="this.style.display='block';" onerror="this.style.display='none';"></video>
                </div>
            `;
        } else if (isAudio) {
            preview = `<div style="font-size: 2.5em; margin-bottom:5px; height: 75px; display: flex; align-items: center; justify-content: center;">🎵</div>`;
        } else {
            preview = `<div style="font-size: 2.5em; margin-bottom:5px; height: 75px; display: flex; align-items: center; justify-content: center;">📄</div>`;
        }
        grid.innerHTML += `
            <div class="vault-item">
                <div style="width: 100%; display: flex; justify-content: center; align-items: center;">${preview}</div>
                <span title="${f}">${f}</span>
                <div class="vault-actions" style="display: flex; flex-direction: column; gap: 4px; width: 100%;">
                    <div style="display: flex; gap: 4px; width: 100%;">
                        <button class="vault-btn" style="flex: 1;" onclick="viewMedia('${activeFolder}', '${f}')">View</button>
                        <button class="vault-btn" style="flex: 1; background: linear-gradient(to bottom, #9eb0c0 0%, #304f69 100%); color: #fff; border-color: #1a3348;" onclick="openMedia('${activeFolder}', '${f}')">Open</button>
                    </div>
                    <button class="vault-btn delete" style="width: 100%;" onclick="deleteMedia('${activeFolder}', '${f}')">Delete</button>
                </div>
            </div>
        `;
    });
}
async function openMedia(folder, filename) {
    try {
        const res = await fetch('/api/open_file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder: folder, filename: filename })
        });
        const data = await res.json();
        if (data.error) {
            alert(`Error opening file: ${data.error}`);
        }
    } catch (err) {
        alert("Failed to open file via server.");
    }
}
function viewMedia(folder, filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const url = `/vault/${folder}/${encodeURIComponent(filename)}`;
    let content = '';
    if (['mp4', 'webm', 'ogg', 'mov', 'mkv', 'avi', 'm4v', '3gp'].includes(ext)) {
        const mimeType = ext === 'webm' ? 'video/webm' : (ext === 'ogg' ? 'video/ogg' : 'video/mp4');
        content = `
            <div style="display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 10px;">
                <video controls autoplay style="max-width:85vw; max-height:75vh; border-radius:4px; outline:none;">
                    <source src="${url}" type="${mimeType}">
                </video>
                <button class="ios-btn-small" style="max-width: 200px;" onclick="openMedia('${folder}', '${filename}')">📺 Open in System Player</button>
            </div>
        `;
    } else if (['mp3', 'wav', 'flac', 'm4a'].includes(ext)) {
        content = `
            <div style="padding:40px; text-align:center;">
                <div style="font-size:4em; margin-bottom:20px;">🎵</div>
                <audio src="${url}" controls autoplay style="outline:none; margin-bottom: 15px;"></audio>
                <div>
                    <button class="ios-btn-small" onclick="openMedia('${folder}', '${filename}')">🔊 Open in System Player</button>
                </div>
            </div>`;
    } else if (['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp', 'avif'].includes(ext)) {
        content = `
            <div style="display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 10px;">
                <img src="${url}" style="max-width:85vw; max-height:75vh; border-radius:4px; box-shadow: 0 4px 20px rgba(0,0,0,0.8);">
                <button class="ios-btn-small" style="max-width: 200px;" onclick="openMedia('${folder}', '${filename}')">🖼️ Open in System Viewer</button>
            </div>
        `;
    } else {
        content = `
            <div style="padding:40px; text-align:center;">
                <div style="font-size:3em; margin-bottom:15px;">⚠️</div>
                <p style="font-weight: bold; margin-bottom: 15px;">Browser playback not supported for .${ext} files.</p>
                <div style="display:flex; gap:10px; justify-content:center;">
                    <button class="ios-btn-small" onclick="openMedia('${folder}', '${filename}')">Open in System Player</button>
                    <a href="${url}" download class="ios-btn-small" style="text-decoration:none; line-height:14px; background:linear-gradient(to bottom, #ffffff 0%, #c8c8c8 100%); color:#333; border-color:#a0a0a0;">Download</a>
                </div>
            </div>`;
    }
    const contentEl = document.getElementById('mediaViewerContent');
    const modalEl = document.getElementById('mediaModal');
    if (contentEl) contentEl.innerHTML = content;
    if (modalEl) modalEl.classList.remove('hidden');
}
function closeViewer() {
    const modalEl = document.getElementById('mediaModal');
    const contentEl = document.getElementById('mediaViewerContent');
    if (modalEl) modalEl.classList.add('hidden');
    if (contentEl) contentEl.innerHTML = '';
}
async function deleteMedia(folder, filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    await fetch(`/api/vault/${folder}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    loadVault();
}
let vaultPickerTarget = { mediaType: 'video', isCenter: false };
let selectedVaultMedia = {
    video: null,
    videoCenter: null,
    image: null,
    imageCenter: null,
    audio: null,
    decrypt: []
};
async function openInputVaultPicker(mediaType, isCenter = false) {
    vaultPickerTarget = { mediaType, isCenter };
    const titleEl = document.getElementById('vaultPickerTitle');
    if (titleEl) {
        const folderName = mediaType === 'decrypt' ? 'Encrypted / Inputs' : 'Input Vault';
        titleEl.innerText = `📂 Select ${isCenter ? 'Center ' : ''}${mediaType.toUpperCase()} from ${folderName}`;
    }
    const modal = document.getElementById('vaultPickerModal');
    if (modal) modal.classList.remove('hidden');
    await refreshVaultPicker();
}
function closeVaultPicker() {
    const modal = document.getElementById('vaultPickerModal');
    if (modal) modal.classList.add('hidden');
}
async function refreshVaultPicker() {
    const listEl = document.getElementById('vaultPickerList');
    if (!listEl) return;
    listEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">Loading vault files...</div>';
    const targetFolder = vaultPickerTarget.mediaType === 'decrypt' ? 'encrypted' : 'input';
    try {
        const res = await fetch(`/api/vault?folder=${targetFolder}`);
        const data = await res.json();
        let files = data.files || [];
        if (vaultPickerTarget.mediaType === 'decrypt' && files.length === 0) {
            const resInput = await fetch(`/api/vault?folder=input`);
            const dataInput = await resInput.json();
            files = dataInput.files || [];
        }
        if (files.length === 0) {
            listEl.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">No files found in this vault folder.</div>';
            return;
        }
        listEl.innerHTML = '';
        files.forEach(f => {
            const isVideo = f.match(/\.(mp4|mkv|avi|webm|mov|m4v|3gp)$/i);
            const isAudio = f.match(/\.(mp3|wav|ogg|flac|m4a)$/i);
            const isImage = f.match(/\.(jpg|jpeg|png|bmp|gif|webp|avif)$/i);
            let icon = '📄';
            if (isVideo) icon = '🎬';
            else if (isAudio) icon = '🎵';
            else if (isImage) icon = '🖼️';
            const item = document.createElement('div');
            item.className = 'vault-picker-item';
            item.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px; overflow: hidden;">
                    <span style="font-size: 1.4em;">${icon}</span>
                    <span class="vault-picker-name" title="${f}">${f}</span>
                </div>
                <button type="button" class="ios-btn-small" style="padding: 4px 12px; font-weight: 600;" onclick="selectVaultFile('${f.replace(/'/g, "\\'")}')">Select</button>
            `;
            listEl.appendChild(item);
        });
    } catch (e) {
        listEl.innerHTML = `<div style="padding: 20px; text-align: center; color: #ff3b30;">Error loading files: ${e.message}</div>`;
    }
}
async function selectVaultFile(filename) {
    const { mediaType, isCenter } = vaultPickerTarget;
    await selectVaultFileDirectly(filename, mediaType, isCenter);
    closeVaultPicker();
}
async function selectVaultFileDirectly(filename, mediaType, isCenter) {
    const folder = mediaType === 'decrypt' ? 'encrypted' : 'input';
    try {
        const res = await fetch(`/api/vault_file_info?filename=${encodeURIComponent(filename)}&folder=${folder}`);
        const data = await res.json();
        const fileUrl = data.url || `/vault/${folder}/${encodeURIComponent(filename)}`;
        if (mediaType === 'video') {
            if (isCenter) {
                selectedVaultMedia.videoCenter = filename;
                const cList = document.getElementById('centerFileList');
                if (cList) cList.innerHTML = `<span class="badge" style="background:#007aff; color:#fff;">📁 Vault: ${filename}</span>`;
                if (typeof loadCenterVideoPreview === 'function') {
                    loadCenterVideoPreview(fileUrl, filename);
                }
            } else {
                selectedVaultMedia.video = filename;
                const fList = document.getElementById('fileList');
                if (fList) fList.innerHTML = `<span class="badge" style="background:#34c759; color:#fff;">📁 Vault: ${filename}</span>`;
                if (typeof loadVideoPreview === 'function') {
                    loadVideoPreview(fileUrl, filename, data.info);
                }
            }
        } else if (mediaType === 'image') {
            if (isCenter) {
                selectedVaultMedia.imageCenter = filename;
                const cList = document.getElementById('centerImageList');
                if (cList) cList.innerHTML = `<span class="badge" style="background:#007aff; color:#fff;">📁 Vault: ${filename}</span>`;
                if (typeof loadCenterImagePreview === 'function') {
                    loadCenterImagePreview(fileUrl, filename);
                }
            } else {
                selectedVaultMedia.image = filename;
                const iList = document.getElementById('imageList');
                if (iList) iList.innerHTML = `<span class="badge" style="background:#34c759; color:#fff;">📁 Vault: ${filename}</span>`;
                if (typeof loadImagePreview === 'function') {
                    loadImagePreview(fileUrl, filename);
                }
            }
        } else if (mediaType === 'audio') {
            selectedVaultMedia.audio = filename;
            const aList = document.getElementById('audioList');
            if (aList) aList.innerHTML = `<span class="badge" style="background:#34c759; color:#fff;">📁 Vault: ${filename}</span>`;
            if (typeof loadAudioPreview === 'function') {
                loadAudioPreview(fileUrl, filename);
            }
        } else if (mediaType === 'decrypt') {
            selectedVaultMedia.decrypt = [filename];
            const dList = document.getElementById('decryptFileList');
            if (dList) dList.innerHTML = `<span class="badge" style="background:#ff9500; color:#fff;">📁 Vault: ${filename}</span>`;
        }
    } catch (e) {
        console.error("Failed to select vault file:", e);
    }
}
