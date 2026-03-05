// Theme toggle interactivity
(function () {
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) return;

    var iconMoon = toggle.querySelector('.icon-moon');
    var iconSun = toggle.querySelector('.icon-sun');

    function updateIcons() {
        var isLight = document.documentElement.classList.contains('light-mode');
        if (iconMoon) iconMoon.style.setProperty('display', isLight ? 'none' : 'block', 'important');
        if (iconSun) iconSun.style.setProperty('display', isLight ? 'block' : 'none', 'important');
    }

    // Set correct icon on load
    updateIcons();

    toggle.addEventListener('click', function () {
        var isLight = document.documentElement.classList.toggle('light-mode');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        updateIcons();
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: isLight ? 'light' : 'dark' } }));
    });
})();
