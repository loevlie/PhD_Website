/* math-glossary.js — Hover/focus on a notation symbol inside an
 * explainer post and get a small popover defining what it means.
 *
 * Authoring (in markdown):
 *   <span class="g" data-g="Σ">Σ</span> denotes the sum.
 *   <span class="g" data-g="θ">θ</span> are the parameters.
 *
 * Or, even cheaper, the JS auto-wraps single italic-letter spans
 * inside .blog-prose so any KaTeX-rendered variable (which becomes
 * <span class="mord mathnormal">θ</span>) becomes a glossary anchor
 * if and only if its symbol is in the manifest.
 *
 * Glossary lives at /static/portfolio/data/notation.json:
 *   { "θ": {"name": "theta", "meaning": "model parameters"}, ... }
 *
 * Two-tier rendering matches citations.js:
 *   Tier 1 (Chrome 139+): native <button popovertarget interestfor>
 *   Tier 2 (everyone): JS hover handler with absolute positioning
 *
 * Empty manifest → silent no-op.
 */
(function () {
    if (window.__mathGlossaryMounted) return;
    window.__mathGlossaryMounted = true;

    let manifestPromise = null;
    function loadManifest() {
        if (manifestPromise) return manifestPromise;
        manifestPromise = fetch('/static/portfolio/data/notation.json', { cache: 'force-cache' })
            .then(r => (r.ok ? r.json() : {}))
            .catch(() => ({}));
        return manifestPromise;
    }

    function supportsInterestFor() {
        // Disabled for the same reason as citations.js: the native
        // `interestfor` + `popover="hint"` combination dismisses the
        // popover as soon as interest ends, which can fire before the
        // user reaches the content. Keep everyone on the JS fallback
        // (with popover-hover keep-alive) until the spec settles.
        return false;
    }

    function popoverContent(entry) {
        return `
            <div class="cite-title">${entry.symbol || ''}${entry.name ? ' &middot; <span class="g-pop-name">' + entry.name + '</span>' : ''}</div>
            ${entry.meaning ? `<div class="cite-authors">${entry.meaning}</div>` : ''}
            ${entry.example ? `<div class="cite-venue">${entry.example}</div>` : ''}
        `;
    }

    function resolveEntry(span, manifest) {
        // Prefer an inline `data-def` attribute (per-post notation
        // entries carry the definition directly) so the popover works
        // even when the symbol isn't in the global manifest.
        const sym = span.dataset.g || span.textContent.trim();
        const inlineDef = span.dataset.def || '';
        if (inlineDef) {
            return { symbol: sym, name: '', meaning: inlineDef, example: '' };
        }
        const entry = manifest[sym];
        if (!entry) return null;
        entry.symbol = sym;
        return entry;
    }

    function attachNative(spans, manifest) {
        let id = 0;
        spans.forEach(span => {
            const entry = resolveEntry(span, manifest);
            if (!entry) return;
            id += 1;
            const popoverId = `g-pop-${id}`;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'g g-anchor';
            btn.setAttribute('popovertarget', popoverId);
            btn.setAttribute('interestfor', popoverId);
            btn.textContent = span.textContent;
            const pop = document.createElement('div');
            pop.id = popoverId;
            pop.setAttribute('popover', 'hint');
            pop.className = 'cite-popover cite-popover--native g-popover';
            pop.innerHTML = popoverContent(entry);
            span.replaceWith(btn);
            btn.after(pop);
        });
    }

    function attachJsFallback(spans, manifest) {
        let active = null, anchor = null;
        let hideTimer = null;

        function cancelHide() {
            if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        }
        function scheduleHide() {
            cancelHide();
            hideTimer = setTimeout(() => {
                if (!active) return;
                const popHovered = active.matches(':hover');
                const anchorHovered = anchor && anchor.matches(':hover');
                if (!popHovered && !anchorHovered) hide();
            }, 250);
        }
        function hide() {
            cancelHide();
            if (!active) return;
            active.classList.remove('is-visible');
            setTimeout(() => active && active.remove(), 150);
            active = null; anchor = null;
        }
        function show(el) {
            const entry = resolveEntry(el, manifest);
            if (!entry) return;
            hide();
            const pop = document.createElement('div');
            pop.className = 'cite-popover g-popover';
            pop.innerHTML = popoverContent(entry);
            document.body.appendChild(pop);
            const ar = el.getBoundingClientRect();
            pop.style.top = (window.scrollY + ar.bottom + 8) + 'px';
            pop.style.left = (window.scrollX + ar.left) + 'px';
            requestAnimationFrame(() => pop.classList.add('is-visible'));
            active = pop; anchor = el;
            // Keep-alive on popover hover — lets the user reach any
            // links / buttons inside without the hide timer firing.
            pop.addEventListener('mouseenter', cancelHide);
            pop.addEventListener('mouseleave', scheduleHide);
        }
        spans.forEach(span => {
            if (!resolveEntry(span, manifest)) return;
            span.classList.add('g-anchor');
            span.setAttribute('tabindex', '0');
            span.addEventListener('mouseenter', () => { cancelHide(); show(span); });
            span.addEventListener('mouseleave', scheduleHide);
            span.addEventListener('focus', () => { cancelHide(); show(span); });
            span.addEventListener('blur', hide);
        });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
    }

    function init() {
        const explicit = Array.from(document.querySelectorAll('.blog-prose .g'));
        if (!explicit.length) return;
        loadManifest().then(manifest => {
            const present = explicit.filter(s => resolveEntry(s, manifest));
            if (!present.length) return;
            if (supportsInterestFor()) attachNative(present, manifest);
            else attachJsFallback(present, manifest);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
