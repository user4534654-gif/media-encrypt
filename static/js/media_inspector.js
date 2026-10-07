/* Media Inspector — pre-playback media data preview.
 * Shows a player + table: name, file size, resolution,
 * duration, video/audio codecs, bitrates, format.
 * Works for local files (input[type=file]) and Vault files
 * (via /api/vault_file_info). Called from vault.js:
 * loadVideoPreview / loadCenterVideoPreview / loadImagePreview / loadAudioPreview.
 */

(function () {
    'use strict';

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function formatBytes(bytes) {
        if (bytes == null || isNaN(bytes)) return '—';
        bytes = Number(bytes);
        if (bytes < 1024) return bytes + ' B';
        var units = ['B', 'KB', 'MB', 'GB'];
        var i = 0;
        while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
        return bytes.toFixed(bytes >= 100 ? 1 : 2) + ' ' + units[i];
    }

    function formatClock(sec) {
        if (sec == null || !isFinite(sec)) return '—';
        sec = Math.max(0, Number(sec));
        var h = Math.floor(sec / 3600);
        var m = Math.floor((sec % 3600) / 60);
        var s = sec % 60;
        function p(n, l) { n = String(n); while (n.length < l) n = '0' + n; return n; }
        return p(h, 2) + ':' + p(m, 2) + ':' + (s < 10 ? '0' : '') + s.toFixed(2);
    }

    function row(label, value) {
        return '<div class="mi-row"><span class="mi-label">' + esc(label) +
            '</span><span class="mi-value">' + value + '</span></div>';
    }

    function val(text) { return esc(text == null || text === '' ? '—' : text); }

    // Probe a local File via <video>/<img>: resolution + duration.
    function probeLocalFile(file) {
        return new Promise(function (resolve) {
            var out = { width: null, height: null, durationSec: null };
            if (!file || !file.type) return resolve(out);
            if (file.type.indexOf('image/') === 0) {
                var img = new Image();
                var url = URL.createObjectURL(file);
                img.onload = function () {
                    out.width = img.naturalWidth; out.height = img.naturalHeight;
                    URL.revokeObjectURL(url); resolve(out);
                };
                img.onerror = function () { URL.revokeObjectURL(url); resolve(out); };
                img.src = url;
            } else if (file.type.indexOf('video/') === 0 || file.type.indexOf('audio/') === 0) {
                var el = document.createElement(file.type.indexOf('audio/') === 0 ? 'audio' : 'video');
                el.preload = 'metadata';
                var url2 = URL.createObjectURL(file);
                el.onloadedmetadata = function () {
                    if (isFinite(el.duration)) out.durationSec = el.duration;
                    if (el.videoWidth) { out.width = el.videoWidth; out.height = el.videoHeight; }
                    URL.revokeObjectURL(url2); resolve(out);
                };
                el.onerror = function () { URL.revokeObjectURL(url2); resolve(out); };
                el.src = url2;
            } else {
                resolve(out);
            }
        });
    }

    function estimateKbps(sizeBytes, durationSec) {
        if (!sizeBytes || !durationSec || durationSec <= 0) return null;
        return Math.max(1, Math.round((sizeBytes * 8) / durationSec / 1000));
    }

    // Single shared inspector card renderer.
    function renderInspector(containerId, opts) {
        var box = document.getElementById(containerId);
        if (!box) return;
        // opts: {title, filename, playerHtml, rowsHtml, note}
        box.classList.remove('hidden');
        box.innerHTML =
            '<div class="mi-header"><span>' + esc(opts.title || '👁 Preview') + '</span>' +
            '<button type="button" class="ios-btn-small mi-close" onclick="clearMediaInspector(\'' + containerId + '\')">✕</button></div>' +
            '<div class="mi-body">' +
            '<div class="mi-player">' + (opts.playerHtml || '') + '</div>' +
            '<div class="mi-table">' +
            row('📄 File', '<b title="' + esc(opts.filename || '') + '">' + esc(opts.filename || '—') + '</b>') +
            (opts.rowsHtml || '') +
            '</div></div>' +
            (opts.note ? '<div class="mi-note">' + opts.note + '</div>' : '');
    }

    window.clearMediaInspector = function (containerId) {
        var box = document.getElementById(containerId);
        if (!box) return;
        box.classList.add('hidden');
        box.innerHTML = '';
    };

    function serverRows(info, sizeBytes) {
        info = info || {};
        var res = info.resolution || '—';
        var dur = info.duration || (info.duration_sec ? formatClock(info.duration_sec) : '—');
        var size = sizeBytes != null ? sizeBytes :
            (info.file_size_mb != null ? Math.round(info.file_size_mb * 1024 * 1024) : null);
        return (
            row('💾 Size', val(formatBytes(size) + (info.file_size_mb != null ? ' (' + info.file_size_mb + ' MB)' : ''))) +
            row('📐 Resolution', val(res)) +
            row('⏱ Duration', val(dur)) +
            row('🎬 Video', val([info.video_codec, info.video_bitrate].filter(Boolean).join(' · '))) +
            row('🎵 Audio', val([info.audio_codec, info.audio_sr ? info.audio_sr + ' Hz' : null, info.audio_bitrate].filter(Boolean).join(' · '))) +
            row('📦 Format', val(info.format))
        );
    }

    function playerFor(url, kind, filename) {
        if (kind === 'image') {
            return '<img src="' + esc(url) + '" alt="' + esc(filename || '') + '">';
        }
        if (kind === 'audio') {
            return '<audio src="' + esc(url) + '" controls preload="metadata" style="width:100%"></audio>';
        }
        return '<video src="' + esc(url) + '" controls muted playsinline preload="metadata"></video>';
    }

    // ── API expected by vault.js ──────────────────────────────────────────────
    window.loadVideoPreview = function (fileUrl, filename, serverInfo) {
        function done(info, sizeBytes) {
            renderInspector('videoInspector', {
                title: '👁 Video preview before processing',
                filename: filename,
                playerHtml: playerFor(fileUrl, 'video', filename),
                rowsHtml: serverRows(info, sizeBytes)
            });
        }
        if (serverInfo) {
            done(serverInfo, null);
        } else {
            // Vault file without info (e.g. right after upload): retry via the server.
            fetch('/api/vault_file_info?filename=' + encodeURIComponent(filename || '') + '&folder=input')
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (d) { done(d && d.info, d && d.size_bytes); })
                .catch(function () { done(null, null); });
        }
    };

    window.loadCenterVideoPreview = function (fileUrl, filename, serverInfo) {
        function done(info, sizeBytes) {
            renderInspector('centerVideoInspector', {
                title: '👁 Center video before processing',
                filename: filename,
                playerHtml: playerFor(fileUrl, 'video', filename),
                rowsHtml: serverRows(info, sizeBytes)
            });
        }
        if (serverInfo) { done(serverInfo, null); return; }
        var m = /folder=([^&]+)/.exec(fileUrl || '');
        var folder = m ? decodeURIComponent(m[1]) : 'input';
        // fileUrl looks like /vault/<folder>/<name> — extract folder directly
        var vm = /\/vault\/([^/]+)\//.exec(fileUrl || '');
        if (vm) folder = vm[1];
        fetch('/api/vault_file_info?filename=' + encodeURIComponent(filename || '') + '&folder=' + encodeURIComponent(folder))
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) { done(d && d.info, d && d.size_bytes); })
            .catch(function () { done(null, null); });
    };

    window.loadImagePreview = function (fileUrl, filename) {
        fetch('/api/vault_file_info?filename=' + encodeURIComponent(filename || '') + '&folder=input')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
                var info = (d && d.info) || {};
                renderInspector('imageInspector', {
                    title: '👁 Image preview',
                    filename: filename,
                    playerHtml: playerFor(fileUrl, 'image', filename),
                    rowsHtml: serverRows(info, d && d.size_bytes)
                });
            })
            .catch(function () {
                renderInspector('imageInspector', {
                    title: '👁 Image preview',
                    filename: filename,
                    playerHtml: playerFor(fileUrl, 'image', filename),
                    rowsHtml: ''
                });
            });
    };

    window.loadAudioPreview = function (fileUrl, filename) {
        fetch('/api/vault_file_info?filename=' + encodeURIComponent(filename || '') + '&folder=input')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (d) {
                var info = (d && d.info) || {};
                renderInspector('audioInspector', {
                    title: '👁 Audio preview',
                    filename: filename,
                    playerHtml: playerFor(fileUrl, 'audio', filename),
                    rowsHtml: serverRows(info, d && d.size_bytes)
                });
            })
            .catch(function () {
                renderInspector('audioInspector', {
                    title: '👁 Audio preview',
                    filename: filename,
                    playerHtml: playerFor(fileUrl, 'audio', filename),
                    rowsHtml: ''
                });
            });
    };

    // ── Local files (not in Vault yet): size is known immediately, the rest comes from the browser
    function showLocalPreview(containerId, title, file, kind) {
        if (!file) { window.clearMediaInspector(containerId); return; }
        var objectUrl = URL.createObjectURL(file);
        probeLocalFile(file).then(function (p) {
            var kbps = estimateKbps(file.size, p.durationSec);
            var res = (p.width && p.height) ? p.width + 'x' + p.height : '—';
            var rows =
                row('💾 Size', val(formatBytes(file.size))) +
                (kind !== 'audio' ? row('📐 Resolution', val(res)) : '') +
                (kind !== 'image' ? row('⏱ Duration', val(p.durationSec != null ? formatClock(p.durationSec) + ' (' + p.durationSec.toFixed(2) + ' s)' : '—')) : '') +
                (kbps ? row('📊 Bitrate (est.)', val(kbps + ' kbps')) : '') +
                row('📦 Type', val(file.type || '—'));
            var extra = '';
            if (window._localFileExtras && window._localFileExtras[file.name]) {
                extra = window._localFileExtras[file.name];
            }
            renderInspector(containerId, {
                title: title,
                filename: file.name,
                playerHtml: kind === 'image'
                    ? '<img src="' + objectUrl + '" alt="">'
                    : (kind === 'audio'
                        ? '<audio src="' + objectUrl + '" controls preload="metadata" style="width:100%"></audio>'
                        : '<video src="' + objectUrl + '" controls muted playsinline preload="metadata"></video>'),
                rowsHtml: rows,
                note: extra
            });
        });
    }

    window.showLocalVideoPreview = function (file) {
        showLocalPreview('videoInspector', '👁 Video preview before processing', file, 'video');
    };
    window.showLocalCenterPreview = function (file) {
        showLocalPreview('centerVideoInspector', '👁 Center video before processing', file, 'video');
    };

    // Hook up the inputs after DOM load (in addition to ui.js).
    document.addEventListener('DOMContentLoaded', function () {
        var main = document.getElementById('mediaUpload');
        if (main) {
            main.addEventListener('change', function (e) {
                var files = e.target.files ? Array.prototype.slice.call(e.target.files) : [];
                // Reset the Vault selection — the source is local now.
                try {
                    if (typeof selectedVaultMedia !== 'undefined' && selectedVaultMedia) {
                        selectedVaultMedia.video = null;
                    }
                } catch (err) { /* ignore */ }
                if (!files.length) { window.clearMediaInspector('videoInspector'); return; }
                window.showLocalVideoPreview(files[0]);
                var box = document.getElementById('videoInspector');
                if (box && files.length > 1) {
                    // the batch-processing badge already lives in fileList; no duplicate here
                }
            });
        }
        var center = document.getElementById('centerVideoUpload');
        if (center) {
            center.addEventListener('change', function (e) {
                var files = e.target.files ? Array.prototype.slice.call(e.target.files) : [];
                try {
                    if (typeof selectedVaultMedia !== 'undefined' && selectedVaultMedia) {
                        selectedVaultMedia.videoCenter = null;
                    }
                } catch (err) { /* ignore */ }
                if (!files.length) { window.clearMediaInspector('centerVideoInspector'); return; }
                window.showLocalCenterPreview(files[0]);
            });
        }
        // Image / Audio local previews (when their containers exist).
        var imgInput = document.getElementById('imageUpload');
        if (imgInput) {
            imgInput.addEventListener('change', function (e) {
                var f = e.target.files && e.target.files[0];
                if (!f) return;
                if (document.getElementById('imageInspector')) {
                    showLocalPreview('imageInspector', '👁 Image preview', f, 'image');
                }
            });
        }
        var audInput = document.getElementById('audioUpload');
        if (audInput) {
            audInput.addEventListener('change', function (e) {
                var f = e.target.files && e.target.files[0];
                if (!f) return;
                if (document.getElementById('audioInspector')) {
                    showLocalPreview('audioInspector', '👁 Audio preview', f, 'audio');
                }
            });
        }
    });
})();
