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
                // Surround the marker with blank lines so it survives
                // paragraph splitting in the markdown parser.
                insertAtCursor('\n\n' + data.match.marker + '\n\n');
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
})();
