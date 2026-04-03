// Theme toggle interactivity
(function () {
    var toggles = document.querySelectorAll('.theme-toggle');
    if (!toggles.length) return;

    function updateAllIcons() {
        var isLight = document.documentElement.classList.contains('light-mode');
        document.querySelectorAll('.theme-toggle').forEach(function (t) {
            var moon = t.querySelector('.icon-moon');
            var sun = t.querySelector('.icon-sun');
            if (moon) moon.style.setProperty('display', isLight ? 'none' : 'block', 'important');
            if (sun) sun.style.setProperty('display', isLight ? 'block' : 'none', 'important');
        });
    }

    updateAllIcons();

    toggles.forEach(function (toggle) {
        toggle.addEventListener('click', function () {
            var isLight = document.documentElement.classList.toggle('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            updateAllIcons();
            window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: isLight ? 'light' : 'dark' } }));
        });
    });
})();
