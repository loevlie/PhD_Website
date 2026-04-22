// Smart-paste in the editor.
//
// On paste events in the textarea, if the clipboard contains exactly
// one http(s) URL and nothing else of substance, ask the server what
// it thinks that URL is (arxiv / github repo / github permalink /
// wiki). If the server returns a marker, replace the paste with the
// marker. Otherwise fall through to the browser's default paste.
//
// DETECTION LIVES ON THE SERVER so regex patterns have ONE source of
// truth. The trade-off is a ~80ms round-trip per paste; acceptable
// because the author's gesture is deliberate, not reactive.
//
// Fallback behavior is critical: any failure (network, CSRF, JSON)
// must let the original paste go through unmolested. An author
// pasting while their session expired should NOT silently lose
// their clipboard contents.

(function () {
    'use strict';
    var textarea = document.querySelector('textarea[name="body"]');
    if (!textarea) return;

    var ENDPOINT = '/editor/smart-paste/';
    var URL_RE = /^(https?:\/\/\S+)$/i;

    function csrfToken() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function isSingleUrl(text) {
        if (!text) return null;
        var trimmed = text.trim();
        var m = trimmed.match(URL_RE);
        return m ? m[1] : null;
    }

    function insertAtCursor(replacement) {
        var s = textarea.selectionStart;
        var e = textarea.selectionEnd;
        var before = textarea.value.slice(0, s);
        var after = textarea.value.slice(e);
        textarea.value = before + replacement + after;
        var caret = s + replacement.length;
        textarea.setSelectionRange(caret, caret);
        // Fire input so the editor's autosave / preview pipeline runs.
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    textarea.addEventListener('paste', function (ev) {
        // Only handle plain-text pastes; binary data (images) is
        // owned by the existing image-upload handler elsewhere in the
        // editor.
        var data = (ev.clipboardData || window.clipboardData);
        if (!data) return;
        var text = data.getData('text/plain');
        var url = isSingleUrl(text);
        if (!url) return;  // fall through to default paste

        // Claim the event NOW so we don't race with the browser's
        // default paste. If the server comes back with no match, we
        // re-insert the raw URL ourselves.
        ev.preventDefault();

        fetch(ENDPOINT, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify({ url: url }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data && data.ok && data.match && data.match.marker) {
                // Rich URL: ask the author whether they want the full
                // block card or an inline link. Readers now get a
                // hover-preview of the same card either way, so the
                // choice is really "how does this read in the layout?".
                askFormat(data.match).then(function (choice) {
                    if (choice === 'card') {
                        insertAtCursor('\n\n' + data.match.marker + '\n\n');
                    } else if (choice === 'inline') {
                        insertAtCursor(url);
                    }
                    // 'cancel' → insert nothing (author pressed Esc).
                });
            } else {
                // No match — insert the raw URL the author pasted.
                insertAtCursor(url);
            }
        })
        .catch(function () {
            // Network/CSRF failure — never drop the paste.
            insertAtCursor(url);
        });
    });

    // ── Paste-format dialog ────────────────────────────────────────
    // Fires when smart-paste detects a rich URL. Offers "Full card"
    // (block embed, the original smart-paste behaviour) or "Inline
    // link" (plain URL, upgraded to a hover card for readers).
    function askFormat(match) {
        return new Promise(function (resolve) {
            var dlg = document.getElementById('paste-format-dialog');
            if (!dlg) { resolve('card'); return; }          // missing DOM → no prompt
            var labelEl = document.getElementById('paste-format-label');
            var markerEl = document.getElementById('paste-format-marker');
            var cardBtn = document.getElementById('paste-format-card');
            var inlineBtn = document.getElementById('paste-format-inline');
            var cancelBtn = document.getElementById('paste-format-cancel');
            var kindLabel = ({
                'arxiv': 'arXiv paper',
                'github': 'GitHub repo',
                'github_snippet': 'GitHub code',
                'wiki': 'Wikipedia article',
            })[match.kind] || 'link';
            labelEl.textContent = 'Pasted ' + kindLabel + ' — how should it appear?';
            markerEl.textContent = match.marker;

            function cleanup(result) {
                cardBtn.removeEventListener('click', onCard);
                inlineBtn.removeEventListener('click', onInline);
                cancelBtn.removeEventListener('click', onCancel);
                dlg.removeEventListener('close', onClose);
                try { dlg.close(); } catch (e) {}
                resolve(result);
            }
            function onCard(ev) { ev.preventDefault(); cleanup('card'); }
            function onInline(ev) { ev.preventDefault(); cleanup('inline'); }
            function onCancel(ev) { ev.preventDefault(); cleanup('cancel'); }
            function onClose() { cleanup('cancel'); }
            cardBtn.addEventListener('click', onCard);
            inlineBtn.addEventListener('click', onInline);
            cancelBtn.addEventListener('click', onCancel);
            dlg.addEventListener('close', onClose);
            dlg.showModal();
            setTimeout(function () { cardBtn.focus(); }, 30);
        });
    }
})();
