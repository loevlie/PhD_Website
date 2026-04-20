/* First-party privacy analytics beacon.
 *
 * Sends a single pageview record on load, then a scroll-depth + dwell
 * update on unload via sendBeacon (which keeps working during page exit).
 *
 * Respects the user's stated preferences:
 *   - navigator.doNotTrack === '1' → silent no-op
 *   - navigator.globalPrivacyControl true → silent no-op
 *   - localStorage 'analytics-opt-out' truthy → silent no-op
 *
 * Server-side also gates on Sec-GPC and DNT headers, so this is
 * defense-in-depth.
 */
(function () {
    if (navigator.doNotTrack === '1' || navigator.doNotTrack === 'yes') return;
    if (navigator.globalPrivacyControl === true) return;
    try {
        if (localStorage.getItem('analytics-opt-out')) return;
    } catch (e) {}

    // Don't track admin, the insights dashboard, or the editor itself
    if (location.pathname.startsWith('/admin/')) return;
    if (location.pathname.startsWith('/site/insights')) return;
    if (/\/edit\/?$/.test(location.pathname)) return;

    var startTs = Date.now();
    var pvId = null;
    var maxScrollPct = 0;

    function viewportSize() {
        return {
            w: window.innerWidth || document.documentElement.clientWidth || 0,
            h: window.innerHeight || document.documentElement.clientHeight || 0,
        };
    }

    function recordPageview() {
        var vp = viewportSize();
        var fd = new FormData();
        fd.append('path', location.pathname);
        fd.append('referrer', document.referrer || '');
        fd.append('viewport_w', String(vp.w));
        fd.append('viewport_h', String(vp.h));

        // Use fetch so we can read the response (the pageview id) and
        // update later. sendBeacon doesn't return a body.
        fetch('/a/p', {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            keepalive: true,
        }).then(function (r) {
            if (r.status === 200) return r.json();
            return null;
        }).then(function (data) {
            if (data && data.id) pvId = data.id;
        }).catch(function () {});
    }

    function trackScroll() {
        var docH = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight
        );
        var winH = window.innerHeight || document.documentElement.clientHeight;
        var scrolled = window.scrollY + winH;
        var pct = docH > 0 ? Math.round((scrolled / docH) * 100) : 0;
        if (pct > maxScrollPct) maxScrollPct = Math.min(100, pct);
    }

    function flushUpdate() {
        if (!pvId) return;  // pageview hasn't returned yet — drop
        var dwellMs = Date.now() - startTs;
        var fd = new FormData();
        fd.append('id', String(pvId));
        fd.append('scroll_depth', String(maxScrollPct));
        fd.append('dwell_ms', String(dwellMs));
        // sendBeacon survives the page unload event
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/a/u', fd);
        } else {
            fetch('/a/u', { method: 'POST', body: fd, keepalive: true });
        }
    }

    // Fire pageview after first paint so it doesn't compete with TTI
    if (document.readyState === 'complete') {
        recordPageview();
    } else {
        window.addEventListener('load', recordPageview, { once: true });
    }

    // Track scroll depth (debounced via rAF)
    var ticking = false;
    window.addEventListener('scroll', function () {
        if (!ticking) {
            window.requestAnimationFrame(function () {
                trackScroll();
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });

    // Send the update beacon on unload AND on visibility change (mobile
    // Safari fires visibilitychange when the user backgrounds the tab
    // but doesn't always fire pagehide).
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'hidden') flushUpdate();
    });
    window.addEventListener('pagehide', flushUpdate);
})();
