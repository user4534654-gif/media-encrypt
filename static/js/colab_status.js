/* ── Background Colab file-presence indicator ────────────────────────────────
   A file picked in the browser lives only in the browser until the job is
   submitted. In Colab the submission uploads it into the VM's vault, and
   there was no feedback about whether that actually happened. This module
   shows a small non-blocking badge in the corner:

     pending   - files selected, not in the Colab vault yet
     uploading - multipart upload in progress (percent from process.js)
     checking  - upload finished, verifying the vault
     ok        - every selected file is present in the Colab vault
     error     - upload failed

   It never overlays a control and never blocks interaction: pointer-events
   are off and every check is an async fetch with a silent failure path. */
(function () {
    'use strict';

    const BADGE_ID = 'colabFileStatus';
    const TEXT_ID = 'colabFileStatusText';
    const POLL_MS = 4000;

    let enabled = false;
    let selectedNames = [];
    let pollTimer = null;
    let uploading = false;

    /* The badge is useful through every tunnel, including Cloudflare and
       Pinggy where the browser host is not a Colab domain. Host detection
       only changes the wording, not whether the indicator is shown. */
    function isColabHost() {
        return /colab\.research\.google\.com|colab\.googleusercontent\.com/.test(location.hostname);
    }

    function vaultLabel() {
        return isColabHost() ? 'Colab' : 'server vault';
    }

    function badge() {
        return document.getElementById(BADGE_ID);
    }

    function show(text, state) {
        const el = badge();
        if (!el || !enabled) return;
        el.classList.remove('hidden');
        el.dataset.state = state || 'info';
        const label = document.getElementById(TEXT_ID);
        if (label) label.textContent = text;
    }

    function hide() {
        const el = badge();
        if (el) el.classList.add('hidden');
    }

    function selectedFileNames() {
        const names = [];
        document.querySelectorAll('input[type="file"]').forEach(function (input) {
            if (input.files) {
                Array.prototype.forEach.call(input.files, function (file) {
                    if (names.indexOf(file.name) === -1) names.push(file.name);
                });
            }
        });
        return names;
    }

    function refresh() {
        selectedNames = selectedFileNames();

        if (!selectedNames.length && !uploading) {
            hide();
            if (pollTimer) {
                clearInterval(pollTimer);
                pollTimer = null;
            }
            return;
        }

        if (!pollTimer) {
            pollTimer = setInterval(checkVault, POLL_MS);
        }
        checkVault();
    }

    async function checkVault() {
        if (uploading || !selectedNames.length) return;

        try {
            const res = await fetch('/api/vault?folder=input', { cache: 'no-store' });
            const data = await res.json();
            const remote = Array.isArray(data.files) ? data.files : [];
            const found = selectedNames.filter(function (name) {
                return remote.indexOf(name) !== -1;
            });

            if (found.length === selectedNames.length) {
                show('✓ ' + selectedNames.length + ' file(s) in ' + vaultLabel(), 'ok');
                clearInterval(pollTimer);
                pollTimer = null;
            } else if (found.length) {
                show('◐ ' + found.length + '/' + selectedNames.length + ' file(s) in ' + vaultLabel(), 'partial');
            } else {
                show('◌ ' + selectedNames.length + ' file(s) selected · not uploaded yet', 'pending');
            }
        } catch (err) {
            // A transient tunnel hiccup must not disturb the user.
            show('◌ Waiting for ' + vaultLabel() + '…', 'pending');
        }
    }

    /* Called by process.js while the job submission (with the file bytes)
       is being uploaded to the server. */
    function updateStatus(state, detail) {
        if (!enabled) return;

        if (state === 'uploading') {
            uploading = true;
            const pct = (typeof detail === 'number') ? ' ' + detail + '%' : '';
            show('⬆ Uploading to Colab…' + pct, 'uploading');
            return;
        }

        if (state === 'error') {
            uploading = false;
            show('⚠ Upload failed', 'error');
            return;
        }

        // 'checking' (and any unknown state) resumes the passive vault check.
        uploading = false;
        show('◌ Checking Colab vault…', 'pending');
        checkVault();
        if (!pollTimer && selectedNames.length) {
            pollTimer = setInterval(checkVault, POLL_MS);
        }
    }

    function init() {
        enabled = true;
        hide();

        document.addEventListener('change', function (event) {
            if (event.target && event.target.matches && event.target.matches('input[type="file"]')) {
                refresh();
            }
        }, true);

        window.updateColabFileStatus = updateStatus;
        window.markColabFilesSelected = refresh;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
