/* Code-block copy button.
 *
 * Walks all <pre><code> blocks inside .blog-prose, wraps each in a
 * positioned container, and adds a hover-revealed "Copy" button in the
 * top-right corner. Uses the modern Clipboard API; falls back to a
 * hidden-textarea + execCommand for older browsers.
 *
 * No dependencies. Idempotent — safe to call repeatedly.
 */
(function () {
    function inject() {
        var blocks = document.querySelectorAll('.blog-prose pre > code, .blog-prose .highlight pre');
        blocks.forEach(function (codeEl) {
            var pre = codeEl.tagName === 'PRE' ? codeEl : codeEl.parentElement;
            if (!pre || pre.dataset.copyWrapped === '1') return;
            // The pygments output is .highlight > pre > code; we want
            // the wrapper to be the .highlight div if present, else the pre.
            var host = pre.closest('.highlight') || pre;
            if (host.dataset.copyWrapped === '1') return;
            host.dataset.copyWrapped = '1';
            host.style.position = host.style.position || 'relative';

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'code-copy-btn';
            btn.setAttribute('aria-label', 'Copy code to clipboard');
            btn.textContent = 'Copy';
            btn.addEventListener('click', function () {
                var text = (codeEl.textContent || pre.textContent || '').trim();
                if (!text) return;
                var done = function () {
                    btn.textContent = 'Copied';
                    btn.classList.add('is-copied');
                    setTimeout(function () {
                        btn.textContent = 'Copy';
                        btn.classList.remove('is-copied');
                    }, 1400);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(done).catch(fallback);
                } else {
                    fallback();
                }
                function fallback() {
                    var ta = document.createElement('textarea');
                    ta.value = text;
                    ta.style.position = 'fixed';
                    ta.style.opacity = '0';
                    document.body.appendChild(ta);
                    ta.select();
                    try { document.execCommand('copy'); done(); } catch (e) {}
                    document.body.removeChild(ta);
                }
            });
            host.appendChild(btn);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inject);
    } else {
        inject();
    }
})();
