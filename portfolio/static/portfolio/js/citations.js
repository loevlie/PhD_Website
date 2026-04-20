/* citations.js — Distill-style hover citation popovers.
 *
 * Attach to any element with class .ref and a data-key attribute:
 *   <cite class="ref" data-key="loevlie2023">[1]</cite>
 *
 * Two-tier progressive enhancement:
 *
 *   Tier 1 (modern browsers — Chrome 139+ / Edge 139+):
 *     Upgrade each <cite> to a <button popovertarget interestfor>
 *     paired with a <div popover="hint"> sibling. Hover/focus
 *     opens the popover via native browser behavior — zero JS event
 *     handling, native a11y semantics, dismisses on Esc and outside-
 *     click for free. CSS anchor positioning would be the natural
 *     pair but can be a follow-up; we use absolute positioning here.
 *
 *   Tier 2 (everyone else):
 *     The original mouseenter/mouseleave + click handlers, manual
 *     positioning. Kept verbatim for Firefox + Safari + older Chromium
 *     until they ship the Popover hint type (Safari shipped popover=auto
 *     but not popover=hint as of Safari 18).
 *
 * Both tiers source data from `/static/portfolio/data/citations.json`.
 */

(function () {
    const MANIFEST_URL = '/static/portfolio/data/citations.json';
    let manifestPromise = null;

    function loadManifest() {
        if (manifestPromise) return manifestPromise;
        manifestPromise = fetch(MANIFEST_URL, { cache: 'force-cache' })
            .then(r => (r.ok ? r.json() : {}))
            .catch(() => ({}));
        return manifestPromise;
    }

    function entryFromElement(el, manifest) {
        const key = el.getAttribute('data-key') || '';
        const fromManifest = manifest[key] || {};
        return {
            key,
            title: el.dataset.title || fromManifest.title || '',
            authors: el.dataset.authors || fromManifest.authors || '',
            venue: el.dataset.venue || fromManifest.venue || '',
            url: el.dataset.url || fromManifest.url || '',
            bibtex: el.dataset.bibtex || fromManifest.bibtex || '',
        };
    }

    function popoverHTML(entry) {
        return `
            ${entry.title ? `<div class="cite-title">${entry.title}</div>` : ''}
            ${entry.authors ? `<div class="cite-authors">${entry.authors}</div>` : ''}
            ${entry.venue ? `<div class="cite-venue">${entry.venue}</div>` : ''}
            <div class="cite-actions">
                ${entry.url ? `<a href="${entry.url}" target="_blank" rel="noopener">Open</a>` : ''}
                ${entry.bibtex ? `<button type="button" data-action="copy-bib">Copy BibTeX</button>` : ''}
            </div>
        `;
    }

    function attachCopy(popover, bibtex) {
        const btn = popover.querySelector('[data-action="copy-bib"]');
        if (!btn || !bibtex) return;
        btn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(bibtex);
                const before = btn.textContent;
                btn.textContent = 'Copied';
                setTimeout(() => { btn.textContent = before; }, 1400);
            } catch (e) {
                btn.textContent = 'Copy failed';
            }
        });
    }

    /* ===== Tier 1: native Popover + interestfor ============================ */

    function supportsInterestFor() {
        // `interestfor` is a button attribute that triggers popover on hover/focus.
        // Detect it via `interestForElement` IDL on HTMLButtonElement.
        return 'interestForElement' in HTMLButtonElement.prototype
            || 'interestFor' in HTMLButtonElement.prototype;
    }

    function upgradeNative(refs, manifest) {
        let id = 0;
        refs.forEach(ref => {
            id += 1;
            const popoverId = `cite-pop-${id}`;
            const entry = entryFromElement(ref, manifest);
            if (!entry.title && !entry.authors) return;

            // Replace <cite> with a <button> carrying the same visual styling
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = ref.className;          // keep .ref styling
            btn.setAttribute('data-key', entry.key);
            btn.setAttribute('popovertarget', popoverId);
            btn.setAttribute('interestfor', popoverId);
            btn.textContent = ref.textContent;

            // The popover lives as a sibling <div popover="hint">
            const pop = document.createElement('div');
            pop.id = popoverId;
            pop.setAttribute('popover', 'hint');     // hover-triggered, light-dismiss
            pop.className = 'cite-popover cite-popover--native';
            pop.innerHTML = popoverHTML(entry);
            attachCopy(pop, entry.bibtex);

            ref.replaceWith(btn);
            btn.after(pop);
        });
    }

    /* ===== Tier 2: classic JS fallback ===================================== */

    function position(popover, anchor) {
        const ar = anchor.getBoundingClientRect();
        const pr = popover.getBoundingClientRect();
        const margin = 8;
        let top = window.scrollY + ar.bottom + margin;
        if (ar.bottom + pr.height + margin > window.innerHeight) {
            top = window.scrollY + ar.top - pr.height - margin;
        }
        let left = window.scrollX + ar.left + ar.width / 2 - pr.width / 2;
        const maxLeft = window.scrollX + window.innerWidth - pr.width - margin;
        const minLeft = window.scrollX + margin;
        left = Math.max(minLeft, Math.min(left, maxLeft));
        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
    }

    function buildPopover(entry) {
        const el = document.createElement('div');
        el.className = 'cite-popover';
        el.setAttribute('role', 'tooltip');
        el.innerHTML = popoverHTML(entry);
        attachCopy(el, entry.bibtex);
        return el;
    }

    function attachJsFallback(refs, manifest) {
        let active = null;
        let activeAnchor = null;

        function hide() {
            if (!active) return;
            active.classList.remove('is-visible');
            setTimeout(() => active && active.remove(), 150);
            active = null;
            activeAnchor = null;
        }

        function show(anchor) {
            hide();
            const entry = entryFromElement(anchor, manifest);
            if (!entry.title && !entry.authors) return;
            const pop = buildPopover(entry);
            document.body.appendChild(pop);
            position(pop, anchor);
            requestAnimationFrame(() => pop.classList.add('is-visible'));
            active = pop;
            activeAnchor = anchor;
        }

        refs.forEach(ref => {
            ref.setAttribute('tabindex', '0');
            ref.setAttribute('aria-label',
                'Citation ' + (ref.getAttribute('data-key') || '') + '. Press Enter to open.');
            ref.addEventListener('mouseenter', () => show(ref));
            ref.addEventListener('focus', () => show(ref));
            ref.addEventListener('mouseleave', () => {
                setTimeout(() => { if (active && !active.matches(':hover')) hide(); }, 150);
            });
            ref.addEventListener('blur', hide);
            ref.addEventListener('click', (e) => {
                e.preventDefault();
                if (active && activeAnchor === ref) hide();
                else show(ref);
            });
        });

        document.addEventListener('click', (e) => {
            if (active && !e.target.closest('.cite-popover, cite.ref, .cite-ref')) hide();
        });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
        window.addEventListener('scroll', () => {
            if (active && activeAnchor) position(active, activeAnchor);
        }, { passive: true });
        window.addEventListener('resize', () => {
            if (active && activeAnchor) position(active, activeAnchor);
        });
    }

    /* ===== Init ============================================================ */

    function init() {
        const refs = Array.from(document.querySelectorAll('cite.ref[data-key], .cite-ref[data-key]'));
        if (!refs.length) return;
        loadManifest().then(manifest => {
            if (supportsInterestFor()) {
                upgradeNative(refs, manifest);
            } else {
                attachJsFallback(refs, manifest);
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
