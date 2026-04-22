// Link hover preview.
//
// Shows a small popover with the destination URL when the reader
// hovers over an external link in a blog post. Useful because readers
// often want to know where they're about to go before clicking —
// especially for posts with lots of arxiv / github citations. The
// native browser "title" tooltip has a ~500 ms delay and styles like
// an OS dialog; this is instant and themed.
//
// Scoped to `.blog-prose a[href^="http"]` so we don't compete with:
//   * citations.js           — <cite class="ref"> has its own popover
//   * footnote sidenotes     — already show inline
//   * editor nav / site nav  — not in blog-prose
//
// Self-initialising: one popover element reused across links.

(function () {
    'use strict';

    var prose = document.querySelector('.blog-prose');
    if (!prose) return;

    var pop = null;
    var active = null;
    var hideTimer = null;

    function ensurePopover() {
        if (pop) return pop;
        pop = document.createElement('div');
        pop.className = 'link-hover-pop';
        pop.setAttribute('role', 'tooltip');
        pop.style.cssText = [
            'position: absolute',
            'z-index: 40',
            'pointer-events: none',
            'max-width: min(420px, 70vw)',
            'padding: 6px 10px',
            'font-size: 0.75rem',
            'font-family: ui-monospace, SFMono-Regular, Menlo, monospace',
            'background: var(--ctp-mantle, #1e1e2e)',
            'color: var(--ctp-text, #cdd6f4)',
            'border: 1px solid var(--ctp-surface1, #45475a)',
            'border-radius: 6px',
            'box-shadow: 0 8px 20px -4px rgba(0,0,0,0.35)',
            'opacity: 0',
            'transition: opacity 80ms ease-out',
            'white-space: nowrap',
            'overflow: hidden',
            'text-overflow: ellipsis',
        ].join(';');
        document.body.appendChild(pop);
        return pop;
    }

    function format(href) {
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
        var top = window.scrollY + r.bottom + 6;
        var left = window.scrollX + r.left;
        // Keep within viewport: clamp against right edge so long URLs
        // don't clip off-screen on narrow viewports.
        var maxLeft = window.scrollX + document.documentElement.clientWidth
                    - pop.offsetWidth - 12;
        if (left > maxLeft) left = Math.max(window.scrollX + 8, maxLeft);
        pop.style.top = top + 'px';
        pop.style.left = left + 'px';
    }

    function show(anchor) {
        if (active === anchor) return;
        active = anchor;
        clearTimeout(hideTimer);
        ensurePopover();
        pop.textContent = format(anchor.href);
        pop.style.opacity = '0';
        pop.style.top = '-9999px';
        // Position after the text is in so offsetWidth reflects content.
        requestAnimationFrame(function () {
            position(anchor);
            pop.style.opacity = '1';
        });
    }

    function hide() {
        active = null;
        if (!pop) return;
        // Small delay so a flick across two adjacent links doesn't
        // fade twice.
        hideTimer = setTimeout(function () {
            if (!active && pop) pop.style.opacity = '0';
        }, 60);
    }

    // Event delegation — one listener, any future dynamic links get
    // the hover for free.
    prose.addEventListener('mouseover', function (ev) {
        var a = ev.target.closest('a[href]');
        if (!a || !prose.contains(a)) return;
        if (!/^https?:\/\//i.test(a.getAttribute('href') || '')) return;
        // Skip links that already have their own popover (citations,
        // footnote back-refs, etc.).
        if (a.classList.contains('ref') || a.classList.contains('footnote-ref')
            || a.classList.contains('footnote-backref')
            || a.closest('cite.ref, .cite-ref, .sidenote')) return;
        show(a);
    });
    prose.addEventListener('mouseout', function (ev) {
        var a = ev.target.closest('a[href]');
        if (!a) return;
        // Only hide when leaving the link itself, not moving between
        // children of the link.
        var to = ev.relatedTarget;
        if (to && a.contains(to)) return;
        hide();
    });
    window.addEventListener('scroll', function () { if (active) position(active); }, { passive: true });
    window.addEventListener('resize', function () { if (active) position(active); });
})();
