// Editor AI-assists (Tier 2).
//
// Each button in the panel names an action (tighten, tldr, title,
// sidenote, alt-text). Clicking fires a POST to
// /blog/<slug>/assist/<action>/ with the appropriate payload and
// renders the result in the panel. The result has Insert / Copy /
// Dismiss — we never mutate the textarea until the author asks.
//
// Failure modes:
//   * 503 offline → show "AI assists are offline" and disable buttons
//     for the rest of this session.
//   * 429         → show "rate limited ({scope})", keep buttons enabled.
//   * Anything else → show the error string in the result body.

(function () {
    'use strict';
    var panel = document.getElementById('assist-panel');
    if (!panel) return;
    var textarea = document.querySelector('textarea[name="body"]');
    if (!textarea) return;

    var URL_PREFIX = panel.dataset.assistUrlPrefix;
    var toggleBtn = document.getElementById('assist-toggle');
    var closeBtn  = document.getElementById('assist-close');
    var statusEl  = document.getElementById('assist-status');
    var resultEl  = document.getElementById('assist-result');
    var resultTitleEl = document.getElementById('assist-result-title');
    var resultBodyEl  = document.getElementById('assist-result-body');
    var btnInsert   = document.getElementById('assist-insert');
    var btnCopy     = document.getElementById('assist-copy');
    var btnDismiss  = document.getElementById('assist-dismiss');
    var buttons = panel.querySelectorAll('.assist-btn');

    // ── Popover open/close ────────────────────────────────────────
    function openPanel() {
        panel.classList.remove('hidden');
        if (toggleBtn) {
            toggleBtn.classList.add('is-open');
            toggleBtn.setAttribute('aria-expanded', 'true');
        }
    }
    function closePanel() {
        panel.classList.add('hidden');
        if (toggleBtn) {
            toggleBtn.classList.remove('is-open');
            toggleBtn.setAttribute('aria-expanded', 'false');
        }
    }
    function isOpen() { return !panel.classList.contains('hidden'); }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function (ev) {
            ev.stopPropagation();
            isOpen() ? closePanel() : openPanel();
        });
    }
    if (closeBtn) {
        closeBtn.addEventListener('click', closePanel);
    }
    // Click outside the popover closes it (but not clicks on the toggle
    // itself — that would double-toggle and immediately re-close).
    document.addEventListener('click', function (ev) {
        if (!isOpen()) return;
        if (panel.contains(ev.target)) return;
        if (toggleBtn && toggleBtn.contains(ev.target)) return;
        closePanel();
    });
    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape' && isOpen()) {
            closePanel();
            if (toggleBtn) toggleBtn.focus();
        }
    });

    // One in-flight request at a time. Avoids a rapid-click racing
    // two calls and rendering whichever finishes second.
    var inflight = false;
    var offline = false;
    var lastResult = null;   // {action, text}

    function csrfToken() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function setStatus(text) { statusEl.textContent = text; }

    function showResult(action, text) {
        lastResult = { action: action, text: text };
        resultTitleEl.textContent = action;
        resultBodyEl.textContent = text;
        resultEl.classList.remove('hidden');
    }

    function hideResult() {
        resultEl.classList.add('hidden');
        resultTitleEl.textContent = '';
        resultBodyEl.textContent = '';
        lastResult = null;
    }

    function selectionText() {
        var s = textarea.selectionStart, e = textarea.selectionEnd;
        if (s === e) return '';
        return textarea.value.slice(s, e);
    }

    function currentLine() {
        var caret = textarea.selectionStart;
        var text = textarea.value;
        var before = text.lastIndexOf('\n', caret - 1);
        var after = text.indexOf('\n', caret);
        return text.slice(before + 1, after === -1 ? text.length : after);
    }

    // For alt-text: pull the caption out of a markdown image line like
    //   ![A diagram of the pipeline](path.png)
    // If the author's cursor isn't on an image line, fall back to the
    // current line's plain text.
    function imageCaptionFromLine(line) {
        var m = line.match(/!\[([^\]]*)\]\([^)]+\)/);
        return m ? m[1] : line.trim();
    }

    function payloadFor(action) {
        if (action === 'tighten') {
            var sel = selectionText();
            if (!sel) return { error: 'select some prose first' };
            return { ok: true, body: { text: sel } };
        }
        if (action === 'sidenote') {
            var sel2 = selectionText();
            if (!sel2) return { error: 'select a passage first' };
            return { ok: true, body: { passage: sel2 } };
        }
        if (action === 'tldr') {
            return { ok: true, body: { body: textarea.value } };
        }
        if (action === 'title') {
            var titleInput = document.querySelector('input[name="title"]');
            var current = titleInput ? titleInput.value : '';
            return { ok: true, body: { body: textarea.value, current_title: current } };
        }
        if (action === 'alt-text') {
            var line = currentLine();
            var caption = imageCaptionFromLine(line);
            if (!caption) return { error: 'put cursor on an image or caption line' };
            // Use a window of surrounding text as context.
            var caret = textarea.selectionStart;
            var ctxStart = Math.max(0, caret - 400);
            var ctxEnd = Math.min(textarea.value.length, caret + 400);
            var context = textarea.value.slice(ctxStart, ctxEnd);
            return { ok: true, body: { caption: caption, context: context } };
        }
        return { error: 'unknown action' };
    }

    function run(action) {
        if (inflight) return;
        if (offline) { setStatus('AI assists offline'); return; }
        var p = payloadFor(action);
        if (p.error) { setStatus(p.error); return; }

        inflight = true;
        setStatus('thinking…');
        buttons.forEach(function (b) { b.disabled = true; });

        fetch(URL_PREFIX + action + '/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify(p.body),
        })
        .then(function (r) {
            return r.json().then(function (data) { return { status: r.status, data: data }; });
        })
        .then(function (res) {
            if (res.status === 503) {
                offline = true;
                setStatus('AI assists offline');
                return;
            }
            if (res.status === 429) {
                setStatus('rate limited (' + (res.data.scope || 'limit') + ')');
                return;
            }
            if (!res.data || !res.data.ok) {
                setStatus('error: ' + (res.data && res.data.error ? res.data.error : 'unknown'));
                return;
            }
            var out = res.data.result;
            var text = Array.isArray(out) ? out.map(function (s, i) { return (i + 1) + '. ' + s; }).join('\n') : out;
            showResult(action, text);
            setStatus('done');
        })
        .catch(function () {
            setStatus('network error');
        })
        .finally(function () {
            inflight = false;
            buttons.forEach(function (b) { b.disabled = false; });
        });
    }

    buttons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            run(btn.dataset.action);
        });
    });

    btnInsert.addEventListener('click', function () {
        if (!lastResult) return;
        var s = textarea.selectionStart, e = textarea.selectionEnd;
        // For tighten/sidenote we replace the selection; for everything
        // else we insert at the cursor with a blank line on either side
        // so paragraph-splitting in the markdown parser is happy.
        var before = textarea.value.slice(0, s);
        var after = textarea.value.slice(e);
        var insertion = lastResult.text;
        if (lastResult.action !== 'tighten' && lastResult.action !== 'sidenote') {
            insertion = '\n\n' + insertion + '\n\n';
        }
        textarea.value = before + insertion + after;
        var caret = s + insertion.length;
        textarea.setSelectionRange(caret, caret);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        hideResult();
        setStatus('inserted');
    });

    btnCopy.addEventListener('click', function () {
        if (!lastResult) return;
        (navigator.clipboard && navigator.clipboard.writeText
            ? navigator.clipboard.writeText(lastResult.text)
            : Promise.reject()
        ).then(function () { setStatus('copied'); })
         .catch(function () { setStatus('copy failed'); });
    });

    btnDismiss.addEventListener('click', function () {
        hideResult();
        setStatus('ready');
    });
})();
