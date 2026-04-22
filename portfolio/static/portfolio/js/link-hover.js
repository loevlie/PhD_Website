// Link hover preview.
//
// Shows a popover when the reader hovers over an external link in a
// blog post:
//   * arxiv / github / wiki URLs  → rich embed card (lazy-fetched from
//                                   /embed/card/?url=…), same shape the
//                                   author would get with a
//                                   `<div data-*>` marker.
//   * anything else              → small tooltip with hostname + path.
//
// Scoped to `.blog-prose a[href^="http"]` so we don't compete with:
//   * citations.js           — <cite class="ref"> has its own popover
//   * footnote backrefs      — already inline sidenotes on explainers
//   * editor/site chrome     — not in blog-prose
//
// Network model:
//   * Fetch on hover-intent (120 ms delay) so quick flicks past a link
//     don't trigger requests.
//   * Per-URL in-memory cache so re-hovering the same link is instant.
//   * AbortController on hide so in-flight fetches from a prior hover
//     don't paint over the current one.

(function () {
    'use strict';

    var prose = document.querySelector('.blog-prose');
    if (!prose) return;

    // Patterns mirror portfolio/editor_assist/smart_paste.py. Only the
    // shape-detection — the actual rendering happens server-side.
    var RICH_URL_RE =
        /^https?:\/\/(arxiv\.org\/(abs|pdf)\/|(?:[a-z]{2}\.)?wikipedia\.org\/wiki\/|github\.com\/[^\/]+\/[^\/?#]+\/?(?:[?#]|$))/i;

    var pop = null;            // single shared popover element
    var popIsRich = false;     // is the current content the rich card?
    var active = null;         // current anchor
    var showTimer = null;
    var hideTimer = null;
    var inflight = null;
    var richCache = Object.create(null);  // url → html string

    function ensurePopover() {
        if (pop) return pop;
        pop = document.createElement('div');
        pop.className = 'link-hover-pop';
        pop.setAttribute('role', 'tooltip');
        // Mouse moving onto the popover keeps it open (so the reader
        // can interact with a rich card's internal links if desired).
        pop.addEventListener('mouseenter', function () {
            clearTimeout(hideTimer);
        });
        pop.addEventListener('mouseleave', hide);
        document.body.appendChild(pop);
        return pop;
    }

    function formatPlainText(href) {
        try {
            var u = new URL(href);
            var path = u.pathname + u.search + u.hash;
            if (path === '/') path = '';
            return u.hostname + path;
        } catch (e) {
            return href;
        }
    }

    function position(anchor) {
        var r = anchor.getBoundingClientRect();
        var vw = document.documentElement.clientWidth;
        var popW = pop.offsetWidth;
        var top = window.scrollY + r.bottom + 8;
        // Prefer left-aligning the popover with the link; clamp to the
        // viewport so wide rich cards never clip off-screen.
        var left = window.scrollX + r.left;
        var maxLeft = window.scrollX + vw - popW - 12;
        if (left > maxLeft) left = Math.max(window.scrollX + 8, maxLeft);
        pop.style.top = top + 'px';
        pop.style.left = left + 'px';
    }

    function applyPlain(text) {
        pop.classList.remove('is-rich');
        pop.classList.add('is-plain');
        pop.textContent = text;
        popIsRich = false;
    }

    function applyRich(html) {
        pop.classList.remove('is-plain');
        pop.classList.add('is-rich');
        pop.innerHTML = html;
        popIsRich = true;
    }

    function fetchRich(anchor, href) {
        if (richCache[href] !== undefined) {
            return Promise.resolve(richCache[href]);
        }
        if (inflight) inflight.abort();
        var ctrl = new AbortController();
        inflight = ctrl;
        return fetch('/embed/card/?url=' + encodeURIComponent(href), {
            credentials: 'same-origin',
            signal: ctrl.signal,
        }).then(function (r) {
            if (r.status === 204) { richCache[href] = null; return null; }
            if (!r.ok) return null;
            return r.text().then(function (html) {
                richCache[href] = html;
                return html;
            });
        }).catch(function (e) {
            if (e && e.name === 'AbortError') return null;
            return null;
        }).finally(function () {
            if (inflight === ctrl) inflight = null;
        });
    }

    function show(anchor) {
        if (active === anchor) return;
        active = anchor;
        clearTimeout(hideTimer);
        ensurePopover();

        var href = anchor.href;
        var isRich = RICH_URL_RE.test(href);

        // Paint the plain hostname immediately so the reader gets
        // instant feedback; upgrade to the rich card when it arrives.
        applyPlain(formatPlainText(href));
        pop.style.opacity = '0';
        pop.style.top = '-9999px';
        requestAnimationFrame(function () {
            if (active !== anchor) return;
            position(anchor);
            pop.style.opacity = '1';
        });

        if (!isRich) return;

        fetchRich(anchor, href).then(function (html) {
            if (active !== anchor || !html) return;
            applyRich(html);
            requestAnimationFrame(function () { position(anchor); });
        });
    }

    function hide() {
        clearTimeout(showTimer);
        active = null;
        if (inflight) { inflight.abort(); inflight = null; }
        if (!pop) return;
        hideTimer = setTimeout(function () {
            if (!active && pop) {
                pop.style.opacity = '0';
                // Reset content so the next show() doesn't flash the
                // previous link's card.
                setTimeout(function () {
                    if (!active) applyPlain('');
                }, 120);
            }
        }, 120);
    }

    prose.addEventListener('mouseover', function (ev) {
        var a = ev.target.closest('a[href]');
        if (!a || !prose.contains(a)) return;
        var href = a.getAttribute('href') || '';
        if (!/^https?:\/\//i.test(href)) return;
        if (a.classList.contains('ref') || a.classList.contains('footnote-ref')
            || a.classList.contains('footnote-backref')
            || a.closest('cite.ref, .cite-ref, .sidenote')) return;
        // Small hover-intent delay — avoids firing on quick flicks past
        // a link during normal reading-scroll.
        clearTimeout(showTimer);
        showTimer = setTimeout(function () { show(a); }, 120);
    });
    prose.addEventListener('mouseout', function (ev) {
        var a = ev.target.closest('a[href]');
        if (!a) return;
        var to = ev.relatedTarget;
        if (to && (a.contains(to) || (pop && pop.contains(to)))) return;
        hide();
    });
    window.addEventListener('scroll', function () {
        if (active) position(active);
    }, { passive: true });
    window.addEventListener('resize', function () {
        if (active) position(active);
    });
})();
