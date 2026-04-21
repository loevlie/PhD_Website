// Portfolio theme toggle (light/dark). See ./README.md for the full
// vocabulary — localStorage key `theme`, html class `dark-mode`, and
// the companion pre-paint script that runs in the <head>.
(function () {
    var toggles = document.querySelectorAll('.theme-toggle');
    if (!toggles.length) return;

    function updateAllIcons() {
        var isDark = document.documentElement.classList.contains('dark-mode');
        document.querySelectorAll('.theme-toggle').forEach(function (t) {
            var moon = t.querySelector('.icon-moon');
            var sun = t.querySelector('.icon-sun');
            // Moon icon means "switch TO dark" — show in light mode.
            // Sun icon means "switch TO light" — show in dark mode.
            if (moon) moon.style.setProperty('display', isDark ? 'none' : 'block', 'important');
            if (sun) sun.style.setProperty('display', isDark ? 'block' : 'none', 'important');
        });
    }

    updateAllIcons();

    toggles.forEach(function (toggle) {
        toggle.addEventListener('click', function () {
            var isDark = document.documentElement.classList.toggle('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            updateAllIcons();
            window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: isDark ? 'dark' : 'light' } }));
        });
    });
})();
