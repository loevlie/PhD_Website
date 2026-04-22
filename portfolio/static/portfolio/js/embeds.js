// Blog-embed client behaviors.
// Loaded from blog_post.html whenever any embed marker is present in
// the post body. Each widget is self-gated: if its DOM isn't on the
// page the corresponding block is a no-op. Safe to load on any post.
//
// Timing: widgets that only touch static DOM (quiz, save-for-later,
// reading mode, audio, quote-share, hover cards, last-verified) run
// immediately. Widgets that depend on *other* async scripts — KaTeX
// rendering `$$…$$` (equation tooltips), vega-embed painting the
// plot spec — are deferred to the `load` event, which fires after
// every deferred script in the document has finished executing.

(function () {
    'use strict';

    // Run on window `load` so we run after KaTeX's auto-render has
    // processed the math and vega-embed has been attached to window.
    function onReady(fn) {
        if (document.readyState === 'complete') fn();
        else window.addEventListener('load', fn, { once: true });
    }

    // ── Quiz cards ──────────────────────────────────────────────
    document.querySelectorAll('.quiz-card').forEach(function (card) {
        var btn = card.querySelector('.quiz-check');
        var result = card.querySelector('.quiz-result');
        var explain = card.querySelector('.quiz-explain');
        if (!btn || !result) return;
        btn.addEventListener('click', function () {
            var chosen = card.querySelector('input[type=radio]:checked');
            if (!chosen) {
                result.hidden = false;
                result.textContent = 'Pick one first.';
                result.className = 'quiz-result';
                return;
            }
            card.querySelectorAll('.quiz-opt').forEach(function (o) {
                o.classList.remove('quiz-right', 'quiz-wrong');
            });
            var correct = chosen.dataset.correct === 'true';
            var chosenLabel = chosen.closest('.quiz-opt');
            if (chosenLabel) chosenLabel.classList.add(correct ? 'quiz-right' : 'quiz-wrong');
            result.hidden = false;
            result.textContent = correct ? '✓ Correct' : '✗ Not quite';
            result.className = 'quiz-result ' + (correct ? 'quiz-result--right' : 'quiz-result--wrong');
            if (explain) explain.hidden = false;
        });
    });

    // ── Equation annotated glossary (hover tooltips on symbols) ──
    // The handler wraps the LaTeX at render time with a `.katex` root
    // (KaTeX post-processes the $$…$$). We scan each .equation-annotated
    // for spans whose text content matches a key in its glossary, and
    // mark them with data-gloss for JS to surface on hover.
    //
    // Deferred to window.load so we run AFTER KaTeX's auto-render has
    // mutated the DOM — otherwise the `.katex` nodes don't exist yet
    // and the glossary selectors match nothing.
    //
    // Greek aliases: authors naturally type `theta=...` in the
    // glossary but KaTeX renders `\theta` as the Greek letter `θ`.
    // The GREEK table maps ASCII names to their rendered glyphs so
    // `theta`, `alpha`, etc. match. Both upper + lower case covered.
    var GREEK = {
        alpha:'α', beta:'β', gamma:'γ', delta:'δ', epsilon:'ε',
        zeta:'ζ', eta:'η', theta:'θ', iota:'ι', kappa:'κ',
        lambda:'λ', mu:'μ', nu:'ν', xi:'ξ', omicron:'ο',
        pi:'π', rho:'ρ', sigma:'σ', tau:'τ', upsilon:'υ',
        phi:'ϕ', chi:'χ', psi:'ψ', omega:'ω',
        Alpha:'Α', Beta:'Β', Gamma:'Γ', Delta:'Δ', Epsilon:'Ε',
        Zeta:'Ζ', Eta:'Η', Theta:'Θ', Iota:'Ι', Kappa:'Κ',
        Lambda:'Λ', Mu:'Μ', Nu:'Ν', Xi:'Ξ', Omicron:'Ο',
        Pi:'Π', Rho:'Ρ', Sigma:'Σ', Tau:'Τ', Upsilon:'Υ',
        Phi:'Φ', Chi:'Χ', Psi:'Ψ', Omega:'Ω',
    };
    onReady(function () {
        document.querySelectorAll('.equation-annotated').forEach(function (root) {
            var raw = root.getAttribute('data-glossary') || '{}';
            var glossary;
            try { glossary = JSON.parse(raw); } catch (e) { glossary = {}; }
            var terms = Object.keys(glossary);
            if (!terms.length) return;
            // Expand glossary with Greek-letter aliases: both the raw
            // term (e.g. "theta") and the rendered glyph ("θ") resolve
            // to the same explanation.
            var lookup = {};
            terms.forEach(function (t) {
                lookup[t] = glossary[t];
                if (GREEK[t]) lookup[GREEK[t]] = glossary[t];
            });
            var nodes = root.querySelectorAll('.katex .mord, .katex .mathnormal, .katex .mathit, .katex .mathbf');
            nodes.forEach(function (n) {
                var txt = (n.textContent || '').trim();
                if (lookup[txt]) {
                    n.classList.add('equation-symbol');
                    n.setAttribute('data-gloss', lookup[txt]);
                    return;
                }
                // Subscript / superscript variants: θ_1, x_t, β^2 — the
                // KaTeX leaf contains the BASE symbol plus its attached
                // sub/sup. Strip trailing digits, underscores, caret
                // markers so `θ_1` matches the `theta` glossary entry.
                var base = txt.replace(/[_^]?[0-9]+$/, '')
                              .replace(/[′′′]+$/, '')  // primes
                              .trim();
                if (base !== txt && lookup[base]) {
                    n.classList.add('equation-symbol');
                    n.setAttribute('data-gloss', lookup[base]);
                }
            });
        });

        // Portal-tooltip: on hover of any .equation-symbol, create a
        // `<div class="equation-tooltip">` appended to <body> with
        // position:fixed. Escapes every overflow parent (the old
        // `::after` tooltip got clipped by KaTeX's `.math-display`
        // overflow-x:auto wrapper).
        var tip = null;
        function showTip(el) {
            var text = el.getAttribute('data-gloss') || '';
            if (!text) return;
            tip = document.createElement('div');
            tip.className = 'equation-tooltip';
            tip.textContent = text;
            document.body.appendChild(tip);
            // Measure, then position above the symbol (fall back to
            // below if the viewport top is too close).
            var rect = el.getBoundingClientRect();
            var tw = tip.offsetWidth, th = tip.offsetHeight;
            var cx = rect.left + rect.width / 2;
            var left = Math.max(8, Math.min(cx - tw / 2, window.innerWidth - tw - 8));
            var top  = rect.top - th - 8;
            if (top < 8) top = rect.bottom + 8;  // not enough room above
            tip.style.left = left + 'px';
            tip.style.top  = top + 'px';
            // Next frame → trigger the CSS transition
            requestAnimationFrame(function () {
                if (tip) tip.classList.add('is-visible');
            });
        }
        function hideTip() {
            if (!tip) return;
            var t = tip;
            tip = null;
            t.remove();
        }
        document.addEventListener('mouseover', function (e) {
            var el = e.target && e.target.closest && e.target.closest('.equation-symbol');
            if (el && !tip) showTip(el);
        });
        document.addEventListener('mouseout', function (e) {
            var el = e.target && e.target.closest && e.target.closest('.equation-symbol');
            if (el) hideTip();
        });
        window.addEventListener('scroll', hideTip, { passive: true });
    });

    // ── Vega-Lite plots ─────────────────────────────────────────
    // Deferred to window.load so vega@5 / vega-lite@5 / vega-embed@6
    // (all `defer`-loaded from blog_post.html) have finished executing.
    onReady(function () {
        var vegaTargets = document.querySelectorAll('.vega-plot[data-spec]');
        if (!vegaTargets.length) return;
        // If the CDN scripts were blocked or we're offline, fail soft
        // with a readable message rather than silently rendering nothing.
        if (typeof window.vegaEmbed !== 'function') {
            vegaTargets.forEach(function (el) {
                el.textContent = 'Vega-Lite failed to load (network / CDN blocked).';
            });
            return;
        }
        vegaTargets.forEach(function (el) {
            var spec;
            try { spec = JSON.parse(el.getAttribute('data-spec') || '{}'); }
            catch (e) { el.textContent = 'Invalid Vega-Lite spec: ' + e.message; return; }
            // Dark-mode: Vega-Lite's "dark" theme looks good on Catppuccin.
            var isDark = document.documentElement.classList.contains('mocha')
                      || document.documentElement.classList.contains('macchiato')
                      || document.documentElement.classList.contains('frappe')
                      || document.documentElement.classList.contains('dark-mode');
            window.vegaEmbed(el, spec, {
                theme: isDark ? 'dark' : undefined,
                actions: false,     // hide the …/Export menu; authors opt in via spec if they want it
                renderer: 'svg',
            }).catch(function (err) {
                el.textContent = 'Plot error: ' + (err && err.message || err);
            });
        });
    });

    // ── Save-for-later (localStorage) ────────────────────────────
    (function () {
        var btn = document.querySelector('.save-for-later');
        if (!btn) return;
        var slug = btn.dataset.slug;
        if (!slug) return;
        var KEY = 'dl.saved';
        function read() {
            try { return JSON.parse(localStorage.getItem(KEY) || '[]'); }
            catch (e) { return []; }
        }
        function write(arr) { localStorage.setItem(KEY, JSON.stringify(arr)); }
        function refresh() {
            var saved = read().some(function (p) { return p.slug === slug; });
            btn.classList.toggle('is-saved', saved);
            btn.textContent = saved ? 'Saved' : 'Save';
        }
        btn.addEventListener('click', function () {
            var arr = read();
            var idx = arr.findIndex(function (p) { return p.slug === slug; });
            if (idx >= 0) {
                arr.splice(idx, 1);
            } else {
                arr.push({
                    slug: slug,
                    title: btn.dataset.title || slug,
                    date: btn.dataset.date || '',
                    saved_at: Date.now(),
                });
            }
            write(arr);
            refresh();
        });
        refresh();
    })();

    // ── Back-to-top button ──────────────────────────────────────
    // Appears on posts longer than two viewport heights. Fades in once
    // the reader has scrolled ~800px down and fades out near the top.
    // Zero-config — no button in the HTML needed; JS injects one if
    // the page looks like a blog post (has an <article>).
    (function () {
        var article = document.querySelector('article.is-explainer, article.is-paper-companion, article .blog-prose');
        if (!article) return;
        var doc = document.documentElement;
        // Only bother on posts that need it.
        if (doc.scrollHeight < window.innerHeight * 2) return;
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'back-to-top';
        btn.setAttribute('aria-label', 'Back to top');
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>';
        document.body.appendChild(btn);
        btn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        var onScroll = function () {
            btn.classList.toggle('is-visible', window.scrollY > 800);
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    })();

    // ── "How to cite" copy button ───────────────────────────────
    // Bottom-of-post card gets one button per post; click copies the
    // rendered <pre id="cite-bib-…"> text to clipboard and flashes
    // "Copied!" for ~1.4 s. Silent no-op if no cite-card on the page.
    document.querySelectorAll('.cite-copy').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var target = document.getElementById(btn.dataset.citeTarget);
            if (!target) return;
            var text = target.textContent;
            var done = function () {
                var original = btn.textContent;
                btn.textContent = 'Copied!';
                btn.classList.add('is-saved');
                setTimeout(function () {
                    btn.textContent = original;
                    btn.classList.remove('is-saved');
                }, 1400);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(done, function () {
                    btn.textContent = 'Copy failed';
                });
            } else {
                // Fallback for older browsers / insecure contexts
                var ta = document.createElement('textarea');
                ta.value = text; document.body.appendChild(ta);
                ta.select(); document.execCommand('copy'); ta.remove();
                done();
            }
        });
    });

    // ── Reading-mode toggle ─────────────────────────────────────
    (function () {
        var btn = document.querySelector('[data-reading-mode-toggle]');
        if (!btn) return;
        var KEY = 'dl.readingMode';
        function apply(on) {
            document.body.classList.toggle('reading-mode', on);
            btn.classList.toggle('is-active', on);
            btn.textContent = on ? 'Exit reading mode' : 'Reading mode';
        }
        apply(localStorage.getItem(KEY) === '1');
        btn.addEventListener('click', function () {
            var next = !document.body.classList.contains('reading-mode');
            localStorage.setItem(KEY, next ? '1' : '0');
            apply(next);
        });
    })();

    // ── Audio narration (Web Speech) ────────────────────────────
    // Two Chrome-specific quirks handled here:
    //   1. speechSynthesis.speak() silently stops after ~15 s on
    //      long utterances (known bug). Workaround: chunk the
    //      article into sentence-sized SpeechSynthesisUtterances
    //      and queue them; each chunk is under the timeout.
    //   2. Chrome also pauses the engine when the queue is between
    //      utterances (another bug). A 10 s pause/resume keep-alive
    //      tick keeps the engine warm while we're speaking.
    (function () {
        var btn = document.querySelector('.audio-narration');
        if (!btn || !('speechSynthesis' in window)) return;
        var keepAlive = null;
        var queue = [];
        var idx = 0;
        function resetUI() {
            btn.classList.remove('is-speaking');
            btn.textContent = '▶ Listen';
        }
        function stop() {
            window.speechSynthesis.cancel();
            if (keepAlive) { clearInterval(keepAlive); keepAlive = null; }
            queue = [];
            idx = 0;
            resetUI();
        }
        function speakNext() {
            if (idx >= queue.length) { stop(); return; }
            var u = new SpeechSynthesisUtterance(queue[idx]);
            u.rate = 1.02;
            u.onend = function () { idx++; speakNext(); };
            u.onerror = function (e) {
                // "interrupted" / "canceled" are fine — user stopped us.
                if (e && (e.error === 'interrupted' || e.error === 'canceled')) return;
                idx++; speakNext();
            };
            window.speechSynthesis.speak(u);
        }
        btn.addEventListener('click', function () {
            if (btn.classList.contains('is-speaking')) { stop(); return; }
            var article = document.querySelector('article .blog-prose')
                       || document.querySelector('article');
            if (!article) return;
            var raw = article.innerText.replace(/\s+/g, ' ').trim();
            // Split into sentence-sized chunks (max ~180 chars each) so
            // each individual utterance is short enough to dodge the
            // 15-second Chrome bug.
            var sentences = raw.match(/[^.!?]+[.!?]*\s*/g) || [raw];
            queue = [];
            var buf = '';
            sentences.forEach(function (s) {
                if ((buf + s).length > 180 && buf) {
                    queue.push(buf.trim());
                    buf = s;
                } else {
                    buf += s;
                }
            });
            if (buf.trim()) queue.push(buf.trim());
            if (!queue.length) return;
            idx = 0;
            btn.classList.add('is-speaking');
            btn.textContent = '■ Stop';
            // Keep-alive tick: Chrome pauses the engine between
            // utterances; pause+resume nudges it forward.
            keepAlive = setInterval(function () {
                if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) return;
                window.speechSynthesis.pause();
                window.speechSynthesis.resume();
            }, 10000);
            speakNext();
        });
        // If the user navigates away, kill the speech queue.
        window.addEventListener('beforeunload', stop);
    })();

    // ── Quote-to-share floating bubble ─────────────────────────
    (function () {
        var article = document.querySelector('article .blog-prose')
                    || document.querySelector('article');
        if (!article) return;
        var bubble = document.createElement('div');
        bubble.className = 'selection-share';
        bubble.innerHTML =
            '<button data-act="copy">Copy link</button>' +
            '<button data-act="tweet">Post →</button>';
        document.body.appendChild(bubble);
        var lastSelection = '';
        function hide() { bubble.classList.remove('is-visible'); }
        function position(rect) {
            var x = rect.left + rect.width / 2 + window.scrollX - bubble.offsetWidth / 2;
            var y = rect.top + window.scrollY - bubble.offsetHeight - 8;
            bubble.style.left = Math.max(8, x) + 'px';
            bubble.style.top = Math.max(8, y) + 'px';
        }
        document.addEventListener('selectionchange', function () {
            var sel = document.getSelection();
            if (!sel || sel.isCollapsed) { hide(); return; }
            var text = sel.toString().trim();
            if (text.length < 12) { hide(); return; }
            var range = sel.getRangeAt(0);
            // Only show when the selection is inside the article body.
            if (!article.contains(range.commonAncestorContainer)) { hide(); return; }
            lastSelection = text;
            position(range.getBoundingClientRect());
            bubble.classList.add('is-visible');
        });
        bubble.addEventListener('mousedown', function (e) { e.preventDefault(); });
        bubble.addEventListener('click', function (e) {
            var act = e.target && e.target.dataset && e.target.dataset.act;
            if (!act || !lastSelection) return;
            var url = location.origin + location.pathname
                    + '#:~:text=' + encodeURIComponent(lastSelection.slice(0, 120));
            if (act === 'copy') {
                navigator.clipboard.writeText(url).then(function () {
                    e.target.textContent = 'Copied!';
                    setTimeout(function () { e.target.textContent = 'Copy link'; }, 1200);
                });
            } else if (act === 'tweet') {
                var intent = 'https://twitter.com/intent/tweet?text='
                           + encodeURIComponent('"' + lastSelection.slice(0, 200) + '"')
                           + '&url=' + encodeURIComponent(location.origin + location.pathname);
                window.open(intent, '_blank', 'noopener');
            }
        });
    })();

    // ── Hover-preview cards on internal blog links ──────────────
    (function () {
        var article = document.querySelector('article .blog-prose');
        if (!article) return;
        var card = document.createElement('div');
        card.className = 'blog-hover-card';
        document.body.appendChild(card);
        var cache = {};
        var timer = null;

        function show(html, x, y) {
            card.innerHTML = html;
            // Re-measure after content update
            card.style.left = '-9999px'; card.style.top = '0';
            card.classList.add('is-visible');
            var w = card.offsetWidth, h = card.offsetHeight;
            var vw = window.innerWidth;
            var left = Math.max(8, Math.min(x, vw - w - 8));
            card.style.left = left + 'px';
            card.style.top = (y - h - 10) + 'px';
        }
        function hide() { card.classList.remove('is-visible'); }

        article.querySelectorAll('a[href^="/blog/"]').forEach(function (a) {
            var href = a.getAttribute('href');
            if (!href || href === location.pathname) return;  // don't preview current post
            a.addEventListener('mouseenter', function () {
                clearTimeout(timer);
                timer = setTimeout(function () {
                    var rect = a.getBoundingClientRect();
                    if (cache[href]) {
                        show(cache[href], rect.left + window.scrollX, rect.top + window.scrollY);
                        return;
                    }
                    // Probe the target post for its title + excerpt
                    fetch(href, { credentials: 'same-origin' })
                        .then(function (r) { return r.text(); })
                        .then(function (html) {
                            var doc = new DOMParser().parseFromString(html, 'text/html');
                            var title = (doc.querySelector('h1') || {}).textContent || href;
                            var desc = (doc.querySelector('meta[name=description]') || {}).content || '';
                            var date = (doc.querySelector('time') || {}).textContent || '';
                            cache[href] = (
                                '<span class="blog-hover-card-title">' + escapeHtml(title.trim()) + '</span>' +
                                (date ? '<span class="blog-hover-card-meta">' + escapeHtml(date.trim()) + '</span>' : '') +
                                (desc ? '<p class="blog-hover-card-excerpt">' + escapeHtml(desc.trim()) + '</p>' : '')
                            );
                            show(cache[href], rect.left + window.scrollX, rect.top + window.scrollY);
                        })
                        .catch(function () { /* silent; no preview is fine */ });
                }, 300);  // don't fetch on flybys
            });
            a.addEventListener('mouseleave', function () {
                clearTimeout(timer);
                hide();
            });
        });
        function escapeHtml(s) {
            return s.replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }
    })();

    // ── Last-verified freshness stamps ──────────────────────────
    // Any <span class="last-verified">YYYY-MM-DD</span> gets an
    // additional `last-verified--stale` class if the date is older
    // than 6 months, so readers see colour-coded confidence on
    // claims that age fast (SOTA numbers, library version notes).
    (function () {
        var spans = document.querySelectorAll('.last-verified');
        if (!spans.length) return;
        var STALE_MS = 1000 * 60 * 60 * 24 * 180;
        var now = Date.now();
        spans.forEach(function (el) {
            var txt = (el.textContent || '').trim();
            var m = /(\d{4})-(\d{2})-(\d{2})/.exec(txt);
            if (!m) return;
            var d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getTime();
            if (isFinite(d) && now - d > STALE_MS) {
                el.classList.add('last-verified--stale');
                el.title = 'Last verified ' + txt + ' — may be stale (>6 months old)';
            } else {
                el.title = 'Last verified ' + txt;
            }
        });
    })();

})();

// ─── Batch E: Ask-this-post widget ─────────────────────────────
// Blog-embed client behaviors.
// Self-gated — each block no-ops if its trigger element isn't on the
// page, so this file is safe to load on any blog post.

(function () {
    'use strict';

    // ── "Ask this post" floating chat bubble ────────────────────
    // Gated on `[data-ask-post]` in the reader-tools row. Opens a
    // bottom-right chat bubble, POSTs questions to /blog/<slug>/ask/,
    // streams the SSE response back into the bubble. Conversation
    // history per-post lives in sessionStorage so accidental reloads
    // don't erase the thread.
    //
    // Fallback ladder:
    //   · 503 from the endpoint → "Chat is offline right now."
    //   · 429 → "Rate limit reached …".
    //   · Any other failure → a generic "Something went wrong" note,
    //     the input stays enabled so the reader can retry.
    (function () {
        var askBtn = document.querySelector('[data-ask-post]');
        if (!askBtn) return;

        var slug = askBtn.dataset.slug;
        if (!slug) return;

        var STORAGE_KEY = 'dl.ask.' + slug;
        var bubble = null;
        var logEl = null;
        var inputEl = null;
        var sendEl = null;
        var isStreaming = false;
        var offline = false;

        function escapeHtml(s) {
            return String(s).replace(/[&<>"']/g, function (c) {
                return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
            });
        }

        function readHistory() {
            try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]'); }
            catch (e) { return []; }
        }
        function writeHistory(arr) {
            try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(arr)); }
            catch (e) { /* quota or private mode — non-fatal */ }
        }

        function appendMsg(role, text) {
            var m = document.createElement('div');
            m.className = 'ask-msg ask-msg--' + role;
            m.textContent = text;
            logEl.appendChild(m);
            logEl.scrollTop = logEl.scrollHeight;
            return m;
        }

        function appendSystem(text) {
            var m = document.createElement('div');
            m.className = 'ask-msg ask-msg--system';
            m.textContent = text;
            logEl.appendChild(m);
            logEl.scrollTop = logEl.scrollHeight;
            return m;
        }

        function buildBubble() {
            bubble = document.createElement('div');
            bubble.className = 'ask-bubble';
            bubble.setAttribute('role', 'dialog');
            bubble.setAttribute('aria-label', 'Ask about this post');
            bubble.innerHTML =
                '<header class="ask-bubble-head">' +
                    '<span class="ask-bubble-title">Ask about this post</span>' +
                    '<button type="button" class="ask-close" aria-label="Close">×</button>' +
                '</header>' +
                '<div class="ask-log" role="log" aria-live="polite"></div>' +
                '<form class="ask-form">' +
                    '<textarea class="ask-input" rows="1" placeholder="Ask a question…" aria-label="Your question"></textarea>' +
                    '<button type="submit" class="ask-send save-for-later">Send</button>' +
                '</form>';
            document.body.appendChild(bubble);

            logEl = bubble.querySelector('.ask-log');
            inputEl = bubble.querySelector('.ask-input');
            sendEl = bubble.querySelector('.ask-send');
            var form = bubble.querySelector('.ask-form');
            var closeBtn = bubble.querySelector('.ask-close');

            closeBtn.addEventListener('click', function () {
                bubble.classList.remove('is-open');
            });

            // Autosize the textarea up to ~5 lines before it starts scrolling.
            inputEl.addEventListener('input', function () {
                inputEl.style.height = 'auto';
                inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
            });

            // Enter → send, Shift+Enter → newline. Matches every other chat UI.
            inputEl.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    form.dispatchEvent(new Event('submit', { cancelable: true }));
                }
            });

            form.addEventListener('submit', function (e) {
                e.preventDefault();
                if (isStreaming) return;
                var q = (inputEl.value || '').trim();
                if (!q) return;
                inputEl.value = '';
                inputEl.style.height = 'auto';
                sendQuestion(q);
            });

            // Rehydrate.
            readHistory().forEach(function (m) {
                if (m.role === 'user' || m.role === 'assistant') {
                    appendMsg(m.role, m.content);
                }
            });
            if (!logEl.children.length) {
                appendSystem('Ask anything about this post — I\'ll answer from what\'s written here.');
            }
        }

        function openBubble() {
            if (!bubble) buildBubble();
            bubble.classList.add('is-open');
            setTimeout(function () { inputEl && inputEl.focus(); }, 50);
        }

        function sendQuestion(question) {
            isStreaming = true;
            sendEl.disabled = true;

            var history = readHistory();
            var userMsg = { role: 'user', content: question };
            history.push(userMsg);
            writeHistory(history);
            appendMsg('user', question);

            // Pre-create the assistant bubble; we'll fill text as SSE arrives.
            // `.ask-msg--pending` gives us the three-dot typing pulse until
            // the first token arrives (see embeds.css); dropped inside the
            // onToken handler below.
            var assistantEl = appendMsg('assistant', '');
            assistantEl.classList.add('is-streaming', 'ask-msg--pending');
            var assistantText = '';
            var gotFirstToken = false;

            function finish(finalText, errMsg) {
                isStreaming = false;
                sendEl.disabled = false;
                assistantEl.classList.remove('is-streaming', 'ask-msg--pending');
                if (errMsg) {
                    assistantEl.classList.add('ask-msg--error');
                    assistantEl.textContent = errMsg;
                    return;
                }
                // Persist the final assistant message.
                var h2 = readHistory();
                h2.push({ role: 'assistant', content: finalText });
                writeHistory(h2);
            }

            fetch('/blog/' + slug + '/ask/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
                body: JSON.stringify({
                    question: question,
                    history: history.slice(0, -1),  // exclude the just-pushed user msg; server re-adds
                }),
                credentials: 'same-origin',
            }).then(function (res) {
                if (res.status === 503) {
                    offline = true;
                    askBtn.setAttribute('title', 'Chat offline');
                    finish('', 'Chat is offline right now — check back later.');
                    return;
                }
                if (res.status === 429) {
                    finish('', 'Rate limit reached (' + 20 + '/day). Try again tomorrow.');
                    return;
                }
                if (!res.ok) {
                    finish('', 'Something went wrong (status ' + res.status + '). Try again.');
                    return;
                }
                if (!res.body || !res.body.getReader) {
                    // Browser lacks streaming support — fall back to text.
                    return res.text().then(function (txt) {
                        // Parse any SSE frames out of the blob.
                        parseSSE(txt, function (evt) {
                            if (evt.delta) {
                                if (!gotFirstToken) {
                                    assistantEl.classList.remove('ask-msg--pending');
                                    gotFirstToken = true;
                                }
                                assistantText += evt.delta;
                                assistantEl.textContent = assistantText;
                            }
                            if (evt.error) { finish('', 'Something went wrong. Try again.'); }
                        });
                        if (assistantText) finish(assistantText);
                    });
                }
                var reader = res.body.getReader();
                var dec = new TextDecoder();
                var buf = '';
                function pump() {
                    return reader.read().then(function (r) {
                        if (r.done) {
                            if (assistantText) finish(assistantText);
                            else finish('', 'No response. Try again.');
                            return;
                        }
                        buf += dec.decode(r.value, { stream: true });
                        var parts = buf.split('\n\n');
                        buf = parts.pop();  // last chunk may be partial
                        parts.forEach(function (frame) {
                            frame.split('\n').forEach(function (line) {
                                if (!line.startsWith('data:')) return;
                                var payload = line.slice(5).trim();
                                if (!payload) return;
                                try {
                                    var evt = JSON.parse(payload);
                                    if (evt.delta) {
                                        if (!gotFirstToken) {
                                            assistantEl.classList.remove('ask-msg--pending');
                                            gotFirstToken = true;
                                        }
                                        assistantText += evt.delta;
                                        assistantEl.textContent = assistantText;
                                        logEl.scrollTop = logEl.scrollHeight;
                                    } else if (evt.error) {
                                        finish(assistantText, 'Something went wrong. Try again.');
                                    }
                                } catch (e) { /* malformed frame — skip */ }
                            });
                        });
                        return pump();
                    });
                }
                return pump();
            }).catch(function () {
                finish('', 'Network error. Try again.');
            });
        }

        // Used only by the no-streaming fallback path.
        function parseSSE(blob, cb) {
            blob.split('\n\n').forEach(function (frame) {
                frame.split('\n').forEach(function (line) {
                    if (!line.startsWith('data:')) return;
                    try { cb(JSON.parse(line.slice(5).trim())); }
                    catch (e) { /* skip */ }
                });
            });
        }

        askBtn.addEventListener('click', function () {
            openBubble();
        });
    })();

})();
