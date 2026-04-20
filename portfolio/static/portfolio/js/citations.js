/* citations.js — Distill-style hover citation popovers.
 *
 * Attach to any element with class .ref and a data-key attribute:
 *   <cite class="ref" data-key="loevlie2023">[1]</cite>
 *
 * On hover/focus, looks up the key in the citations manifest and
 * shows a popover with title/authors/venue + a Copy BibTeX button.
 *
 * Manifest format (served at /static/portfolio/data/citations.json):
 *   {
 *     "loevlie2023": {
 *       "title": "Demystifying the Chemical Ordering...",
 *       "authors": "D.J. Loevlie, B. Ferreira, G. Mpourmpakis",
 *       "venue": "Acc. Chem. Res. 2023",
 *       "url": "https://doi.org/10.1021/acs.accounts.2c00646",
 *       "bibtex": "@article{loevlie2023..."
 *     },
 *     ...
 *   }
 *
 * If the manifest can't be loaded (offline / 404), falls back to
 * showing whatever data-* attributes are inlined on the <cite> tag.
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

    function buildPopover(entry) {
        const el = document.createElement('div');
        el.className = 'cite-popover';
        el.setAttribute('role', 'tooltip');
        el.innerHTML = `
            ${entry.title ? `<div class="cite-title">${entry.title}</div>` : ''}
            ${entry.authors ? `<div class="cite-authors">${entry.authors}</div>` : ''}
            ${entry.venue ? `<div class="cite-venue">${entry.venue}</div>` : ''}
            <div class="cite-actions">
                ${entry.url ? `<a href="${entry.url}" target="_blank" rel="noopener">Open</a>` : ''}
                ${entry.bibtex ? `<button type="button" data-action="copy-bib">Copy BibTeX</button>` : ''}
            </div>
        `;
        const copyBtn = el.querySelector('[data-action="copy-bib"]');
        if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
                try {
                    await navigator.clipboard.writeText(entry.bibtex);
                    copyBtn.textContent = 'Copied';
                    setTimeout(() => { copyBtn.textContent = 'Copy BibTeX'; }, 1400);
                } catch (e) {
                    copyBtn.textContent = 'Copy failed';
                }
            });
        }
        return el;
    }

    function position(popover, anchor) {
        const ar = anchor.getBoundingClientRect();
        const pr = popover.getBoundingClientRect();
        const margin = 8;
        // Prefer below; flip up if overflow.
        let top = window.scrollY + ar.bottom + margin;
        if (ar.bottom + pr.height + margin > window.innerHeight) {
            top = window.scrollY + ar.top - pr.height - margin;
        }
        // Center on the anchor; clamp to viewport.
        let left = window.scrollX + ar.left + ar.width / 2 - pr.width / 2;
        const maxLeft = window.scrollX + window.innerWidth - pr.width - margin;
        const minLeft = window.scrollX + margin;
        left = Math.max(minLeft, Math.min(left, maxLeft));
        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
    }

    function init() {
        const refs = document.querySelectorAll('cite.ref[data-key], .cite-ref[data-key]');
        if (!refs.length) return;
        loadManifest().then(manifest => {
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
                ref.addEventListener('mouseleave', (e) => {
                    // Defer so users can move into the popover without it disappearing.
                    setTimeout(() => {
                        if (active && !active.matches(':hover')) hide();
                    }, 150);
                });
                ref.addEventListener('blur', hide);
                ref.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (active && activeAnchor === ref) { hide(); }
                    else { show(ref); }
                });
            });

            // Dismiss on outside click / Esc.
            document.addEventListener('click', (e) => {
                if (active && !e.target.closest('.cite-popover, cite.ref, .cite-ref')) hide();
            });
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') hide();
            });
            // Reposition on scroll/resize while visible.
            window.addEventListener('scroll', () => {
                if (active && activeAnchor) position(active, activeAnchor);
            }, { passive: true });
            window.addEventListener('resize', () => {
                if (active && activeAnchor) position(active, activeAnchor);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
