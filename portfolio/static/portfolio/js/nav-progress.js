/* Top progress bar for navigation feedback.
 *
 * Why: most clicks are <150ms (Speculation Rules prerender + same-origin
 * cache), so we delay reveal so the bar never flashes on instant nav.
 * On a real cold load (Render free-tier wake, slow connection), the bar
 * appears within 150ms and inches forward on an eased curve until the
 * new page commits — pageshow hides + resets it (covers BFCache too).
 *
 * No deps, no library. Inline-friendly: the entire module is one IIFE
 * that registers globally on first parse.
 */
(function () {
    'use strict';
    if (window.__navProgressMounted) return;
    window.__navProgressMounted = true;

    // Inject styles once. Inline keeps the module self-contained — no
    // external CSS file means this can be added/removed without touching
    // any stylesheet pipeline. Uses CSS variables that already exist on
    // both portfolio (--accent-color) and blog (--ctp-lavender) bases,
    // with a literal fallback for cold-start before vars apply.
    var style = document.createElement('style');
    style.textContent =
        '#nav-progress{position:fixed;top:0;left:0;right:0;height:2px;' +
        'z-index:9999;pointer-events:none;opacity:0;' +
        'transition:opacity 200ms ease;background:transparent;}' +
        '#nav-progress-fill{height:100%;width:100%;transform:scaleX(0);' +
        'transform-origin:0 50%;transition:transform 200ms ease-out;' +
        'background:linear-gradient(90deg,' +
        'var(--accent-color,var(--ctp-lavender,#7287fd)) 0%,' +
        'var(--accent-light,var(--ctp-mauve,#cba6f7)) 100%);' +
        'box-shadow:0 0 8px var(--accent-color,var(--ctp-lavender,#7287fd));}';
    (document.head || document.documentElement).appendChild(style);

    var REVEAL_DELAY_MS = 150;   // skip prerender / cached / instant nav
    var TRICKLE_INTERVAL_MS = 200;
    var bar, fill, revealTimer, trickleTimer, progress;

    function ensureMounted() {
        if (bar) return;
        bar = document.createElement('div');
        bar.id = 'nav-progress';
        bar.setAttribute('aria-hidden', 'true');
        fill = document.createElement('div');
        fill.id = 'nav-progress-fill';
        bar.appendChild(fill);
        document.body.appendChild(bar);
    }

    function setProgress(p) {
        progress = Math.max(0, Math.min(1, p));
        if (fill) fill.style.transform = 'scaleX(' + progress + ')';
    }

    function start() {
        ensureMounted();
        clearTimeout(revealTimer);
        clearInterval(trickleTimer);
        bar.style.opacity = '0';
        setProgress(0.08);
        // Delay reveal so the bar doesn't flash on instant prerender hits.
        revealTimer = setTimeout(function () {
            bar.style.opacity = '1';
        }, REVEAL_DELAY_MS);
        // Eased trickle: each tick advances toward 0.9 by a fraction of
        // the remaining gap. Caps short of 100% so the final jump only
        // happens once the new page actually commits.
        trickleTimer = setInterval(function () {
            var remaining = 0.9 - progress;
            if (remaining <= 0.01) return;
            setProgress(progress + remaining * 0.12);
        }, TRICKLE_INTERVAL_MS);
    }

    function done() {
        if (!bar) return;
        clearTimeout(revealTimer);
        clearInterval(trickleTimer);
        setProgress(1);
        // Brief flash at 100% before fading.
        setTimeout(function () {
            bar.style.opacity = '0';
            setTimeout(function () { setProgress(0); }, 200);
        }, 80);
    }

    // Internal-link click handler. Excludes:
    //   - external (different origin)
    //   - new tab (target=_blank, ctrl/cmd/shift, middle-click)
    //   - downloads
    //   - hash-only anchors (same page)
    //   - explicit opt-out via data-no-progress
    function onClick(e) {
        if (e.defaultPrevented) return;
        if (e.button !== 0) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var a = e.target.closest('a[href]');
        if (!a) return;
        if (a.target && a.target !== '' && a.target !== '_self') return;
        if (a.hasAttribute('download')) return;
        if (a.hasAttribute('data-no-progress')) return;
        var href = a.getAttribute('href');
        if (!href || href.charAt(0) === '#') return;
        var url;
        try { url = new URL(a.href, window.location.href); }
        catch (_) { return; }
        if (url.origin !== window.location.origin) return;
        // Same path + only hash difference → no real navigation
        if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return;
        start();
    }

    document.addEventListener('click', onClick, true);

    // Reset on pageshow — covers both fresh loads and BFCache restores.
    window.addEventListener('pageshow', done);
    // Defensive: if a navigation is cancelled mid-flight, hide the bar.
    window.addEventListener('pagehide', function () { /* leave running until pageshow */ });
})();
