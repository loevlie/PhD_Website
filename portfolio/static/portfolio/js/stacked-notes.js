/* stacked-notes.js — Andy Matuschak-style URL-driven side-by-side
 * column stacking for blog posts.
 *
 * Activated on /blog/<slug>/ pages only. Behavior:
 *
 *   - Click an internal blog link (with no modifier keys) → instead of
 *     navigating, fetches the target post's HTML, extracts <article>,
 *     and pushes it as a new column to the right of the current view.
 *
 *   - URL state persists via history.pushState as `?stack=slug2,slug3`.
 *     Refreshing or sharing the URL restores all stacked columns.
 *
 *   - Each column has a close button (×) and an Esc-to-close shortcut
 *     when focused. Clicking outside any column collapses the rightmost.
 *
 *   - On phones (<900 px), stacking falls back to normal navigation —
 *     side-by-side doesn't fit and "Back" is the better mental model.
 *
 *   - Modifier keys (⌘/Ctrl/Shift/Middle-click) still navigate normally
 *     so the "open in new tab" muscle memory works.
 */
(function () {
    if (window.__stackedNotesMounted) return;
    window.__stackedNotesMounted = true;

    const NARROW_BREAKPOINT = 900;
    const COLUMN_WIDTH = 540;

    // Only activate on individual blog post pages
    if (!/^\/blog\/[^/?]+\/?(\?|$)/.test(window.location.pathname + window.location.search)) {
        // Allow ?stack= on the homepage / blog index too — but skip if not
        // a recognized blog-context root. For simplicity: scope to /blog/<slug>/.
        if (!/^\/blog\/[^/?]+\/?$/.test(window.location.pathname)) return;
    }
    if (window.innerWidth < NARROW_BREAKPOINT) return;

    /* ---------- DOM scaffolding ----------------------------------- */
    function ensureContainer() {
        let stack = document.getElementById('blog-stack');
        if (stack) return stack;
        const main = document.querySelector('article') || document.querySelector('main') || document.body;
        // Wrap the existing main column inside a flex stack container.
        stack = document.createElement('div');
        stack.id = 'blog-stack';
        stack.className = 'blog-stack';
        main.parentNode.insertBefore(stack, main);
        const root = document.createElement('div');
        root.className = 'blog-stack-column blog-stack-root';
        root.dataset.slug = window.location.pathname.match(/^\/blog\/([^/]+)\//)[1];
        root.appendChild(main);
        stack.appendChild(root);
        return stack;
    }

    function makeColumn(slug, articleHTML) {
        const col = document.createElement('div');
        col.className = 'blog-stack-column blog-stack-column--pushed';
        col.dataset.slug = slug;
        col.innerHTML = `
            <button type="button" class="blog-stack-close" aria-label="Close column">×</button>
            <div class="blog-stack-content"></div>
        `;
        col.querySelector('.blog-stack-content').innerHTML = articleHTML;
        col.querySelector('.blog-stack-close').addEventListener('click', () => {
            popColumn(col);
        });
        return col;
    }

    /* ---------- URL <-> column sync ------------------------------- */
    function getStackParam() {
        const u = new URL(window.location.href);
        const s = u.searchParams.get('stack');
        return s ? s.split(',').filter(Boolean) : [];
    }
    function setStackParam(slugs) {
        const u = new URL(window.location.href);
        if (slugs.length) u.searchParams.set('stack', slugs.join(','));
        else u.searchParams.delete('stack');
        history.replaceState({ stack: slugs }, '', u.toString());
    }

    /* ---------- Push/pop ------------------------------------------ */
    async function pushSlug(slug) {
        const stack = ensureContainer();
        // Prevent duplicates
        if (stack.querySelector(`.blog-stack-column[data-slug="${slug}"]`)) return;

        // Optimistic placeholder
        const placeholder = document.createElement('div');
        placeholder.className = 'blog-stack-column blog-stack-column--loading';
        placeholder.dataset.slug = slug;
        placeholder.innerHTML = '<div class="blog-stack-content"><p class="loading-msg">Loading…</p></div>';
        stack.appendChild(placeholder);
        scrollToColumn(placeholder);

        try {
            const r = await fetch(`/blog/${slug}/`, { credentials: 'same-origin' });
            if (!r.ok) throw new Error(r.statusText);
            const html = await r.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const article = doc.querySelector('article');
            if (!article) throw new Error('No <article> in response');
            const col = makeColumn(slug, article.outerHTML);
            placeholder.replaceWith(col);
            scrollToColumn(col);
            renderMath(col);
            wireLinksIn(col);
        } catch (e) {
            placeholder.querySelector('.blog-stack-content').innerHTML =
                `<p class="loading-msg">Couldn't load post: ${e.message}. <a href="/blog/${slug}/">Open normally</a>.</p>`;
        }
        syncURL();
    }

    function popColumn(col) {
        col.classList.add('is-closing');
        setTimeout(() => {
            col.remove();
            syncURL();
        }, 180);
    }

    function syncURL() {
        const slugs = Array.from(document.querySelectorAll('.blog-stack-column--pushed, .blog-stack-column--loading'))
            .map(c => c.dataset.slug);
        setStackParam(slugs);
    }

    function scrollToColumn(col) {
        const stack = document.getElementById('blog-stack');
        if (!stack) return;
        // Defer to next frame so layout is settled
        requestAnimationFrame(() => {
            col.scrollIntoView({ behavior: 'smooth', inline: 'end', block: 'nearest' });
        });
    }

    function renderMath(col) {
        if (window.renderMathInElement) {
            try {
                window.renderMathInElement(col, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
                        { left: '$', right: '$', display: false },
                    ],
                    throwOnError: false,
                });
            } catch (e) { /* swallow */ }
        }
    }

    /* ---------- Link interception --------------------------------- */
    const BLOG_LINK_RE = /^\/blog\/([^/?#]+)\/?(?:[?#]|$)/;

    function wireLinksIn(scope) {
        scope.querySelectorAll('a[href^="/blog/"]').forEach(a => {
            if (a.dataset.stackedWired) return;
            a.dataset.stackedWired = '1';
            a.addEventListener('click', (e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1) return;
                const m = a.getAttribute('href').match(BLOG_LINK_RE);
                if (!m) return;
                const targetSlug = m[1];
                // Skip if it's the editor or a special path
                if (targetSlug === 'new' || targetSlug === 'feed' || targetSlug === 'preview' || targetSlug === 'upload-image') return;
                // Skip if it's the SAME post as any open column
                if (document.querySelector(`.blog-stack-column[data-slug="${targetSlug}"]`)) {
                    e.preventDefault();
                    const existing = document.querySelector(`.blog-stack-column[data-slug="${targetSlug}"]`);
                    scrollToColumn(existing);
                    return;
                }
                e.preventDefault();
                pushSlug(targetSlug);
            });
        });
    }

    /* ---------- Init ---------------------------------------------- */
    function init() {
        ensureContainer();
        wireLinksIn(document);

        // Restore stacked columns from URL
        getStackParam().forEach(slug => pushSlug(slug));

        // Esc closes the rightmost column
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape') return;
            const cols = document.querySelectorAll('.blog-stack-column--pushed, .blog-stack-column--loading');
            if (!cols.length) return;
            popColumn(cols[cols.length - 1]);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
