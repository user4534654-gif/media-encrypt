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
        content = `
            <div style="display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 10px;">
                <video src="${url}" controls autoplay style="max-width:85vw; max-height:75vh; border-radius:4px; outline:none;"></video>
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
