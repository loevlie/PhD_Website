// Editor spell-check panel.
//
// Wired from blog_edit.html. Self-gated: if the expected DOM hooks
// aren't present the module returns early and costs nothing. Runs on
// a 2s debounce off the editor's `textarea` input events. Persists a
// per-author "ignored words" list in localStorage so the checker
// doesn't re-flag words you've already waved through.
//
// DOM contract (all elements optional — missing one just disables
// that affordance):
//   #spellcheck-panel         … the list container
//   #spellcheck-count         … badge showing the count
//   #spellcheck-status        … "checking…" / "N issues" / "clean"
//   textarea[name=body]       … the markdown source we check
//   data-spellcheck-url="…"   … endpoint on #spellcheck-panel
//   data-slug="…"             … post slug on #spellcheck-panel
//
// Shape of misspellings (from /blog/<slug>/spellcheck/):
//   {word, line, col, offset, suggestions: [string]}

(function () {
    'use strict';
    var panel = document.getElementById('spellcheck-panel');
    if (!panel) return;
    var textarea = document.querySelector('textarea[name="body"]');
    if (!textarea) return;

    var list = document.getElementById('spellcheck-list');
    var countEl = document.getElementById('spellcheck-count');
    var statusEl = document.getElementById('spellcheck-status');
    var toggleBtn = document.getElementById('spellcheck-toggle');
    var closeBtn = document.getElementById('spellcheck-close');
    var url = panel.dataset.spellcheckUrl;
    if (!url) return;

    // ── Popover open/close (same pattern as editor-assist.js) ─────
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

    var EXTRAS_KEY = 'dl.spellcheck.extras';
    var DEBOUNCE_MS = 2000;

    function readExtras() {
        try { return JSON.parse(localStorage.getItem(EXTRAS_KEY) || '[]'); }
        catch (e) { return []; }
    }
    function writeExtras(arr) {
        try { localStorage.setItem(EXTRAS_KEY, JSON.stringify(arr)); } catch (e) {}
    }
    function addExtra(word) {
        var arr = readExtras();
        if (arr.indexOf(word) === -1) { arr.push(word); writeExtras(arr); }
    }

    function setStatus(msg, cls) {
        if (!statusEl) return;
        statusEl.textContent = msg;
        statusEl.className = 'spellcheck-status' + (cls ? ' ' + cls : '');
    }

    var inFlight = null;
    var debounceTimer = null;

    function csrfToken() {
        var m = document.cookie.match(/csrftoken=([^;]+)/);
        return m ? m[1] : '';
    }

    function check() {
        if (inFlight) { inFlight.abort(); inFlight = null; }
        var text = textarea.value || '';
        if (!text.trim()) { render([]); setStatus('clean', 'is-clean'); return; }

        setStatus('checking…', 'is-checking');
        var ctrl = new AbortController();
        inFlight = ctrl;
        fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken(),
            },
            body: JSON.stringify({ text: text, extras: readExtras() }),
            signal: ctrl.signal,
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data || !data.ok) {
                setStatus('spellcheck failed', 'is-error');
                return;
            }
            render(data.misspellings || []);
            var n = data.count || 0;
            if (countEl) countEl.textContent = n ? String(n) : '';
            setStatus(
                n === 0 ? 'clean' : n + ' issue' + (n === 1 ? '' : 's'),
                n === 0 ? 'is-clean' : ''
            );
        })
        .catch(function (err) {
            if (err && err.name === 'AbortError') return; // superseded
            setStatus('spellcheck failed', 'is-error');
        })
        .finally(function () { inFlight = null; });
    }

    function render(misspellings) {
        if (!list) return;
        list.innerHTML = '';
        misspellings.forEach(function (m) {
            // Single-row layout: word · suggestions · actions · line.
            // Everything inline so one issue = one compact line instead
            // of the three-row stack the initial pass shipped with.
            var li = document.createElement('li');
            li.className = 'spellcheck-item';
            li.dataset.offset = m.offset;
            li.dataset.word = m.word;

            var word = document.createElement('button');
            word.type = 'button';
            word.className = 'spellcheck-word';
            word.textContent = m.word;
            word.title = 'Jump to line ' + (m.line + 1);
            word.addEventListener('click', function () { jumpTo(m.offset, m.word.length); });
            li.appendChild(word);

            if (m.suggestions && m.suggestions.length) {
                var sugs = document.createElement('span');
                sugs.className = 'spellcheck-sugs';
                m.suggestions.slice(0, 5).forEach(function (s) {
                    var b = document.createElement('button');
                    b.type = 'button';
                    b.className = 'spellcheck-sug';
                    b.textContent = s;
                    b.title = 'Replace "' + m.word + '" with "' + s + '"';
                    b.addEventListener('click', function () { replaceAt(m, s); });
                    sugs.appendChild(b);
                });
                li.appendChild(sugs);
            }

            var actions = document.createElement('span');
            actions.className = 'spellcheck-actions';
            var ignore = document.createElement('button');
            ignore.type = 'button';
            ignore.className = 'spellcheck-action';
            ignore.textContent = '✕';
            ignore.title = 'Ignore for this session';
            ignore.addEventListener('click', function () { li.remove(); bumpCount(-1); });
            var add = document.createElement('button');
            add.type = 'button';
            add.className = 'spellcheck-action';
            add.textContent = '+dict';
            add.title = 'Always accept "' + m.word + '"';
            add.addEventListener('click', function () {
                addExtra(m.word);
                Array.prototype.forEach.call(
                    list.querySelectorAll('li[data-word="' + m.word.replace(/"/g, '\\"') + '"]'),
                    function (row) { row.remove(); bumpCount(-1); }
                );
            });
            actions.appendChild(ignore);
            actions.appendChild(add);
            li.appendChild(actions);

            var loc = document.createElement('span');
            loc.className = 'spellcheck-loc';
            loc.textContent = 'L' + (m.line + 1);
            li.appendChild(loc);

            list.appendChild(li);
        });
    }

    function bumpCount(delta) {
        if (!countEl) return;
        var n = Math.max(0, (parseInt(countEl.textContent, 10) || 0) + delta);
        countEl.textContent = n ? String(n) : '';
        setStatus(
            n === 0 ? 'clean' : n + ' issue' + (n === 1 ? '' : 's'),
            n === 0 ? 'is-clean' : ''
        );
    }

    function jumpTo(offset, length) {
        textarea.focus();
        textarea.setSelectionRange(offset, offset + length);
        // Scroll the selection into view. `selectionStart` was just set
        // above; `scrollIntoView` on a non-block element is nuanced, so
        // we compute the approximate scrollTop from line count.
        var before = textarea.value.slice(0, offset);
        var line = (before.match(/\n/g) || []).length;
        var lineHeight = parseFloat(getComputedStyle(textarea).lineHeight) || 22;
        textarea.scrollTop = Math.max(0, line * lineHeight - textarea.clientHeight / 2);
    }

    function replaceAt(m, replacement) {
        var before = textarea.value.slice(0, m.offset);
        var after = textarea.value.slice(m.offset + m.word.length);
        textarea.value = before + replacement + after;
        // Preserve caret near the replacement.
        textarea.focus();
        textarea.setSelectionRange(
            m.offset + replacement.length,
            m.offset + replacement.length
        );
        // Fire input so the editor's dirty-tracker + autosave kick in.
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function scheduleCheck() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(check, DEBOUNCE_MS);
    }

    textarea.addEventListener('input', scheduleCheck);
    // Initial pass after page load so the author sees existing issues.
    check();
})();
