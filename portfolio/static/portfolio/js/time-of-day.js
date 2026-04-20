/* time-of-day.js — set a data-tod attribute on <html> based on local
 * hour. CSS in variables.css then shifts the accent hue cooler at dawn,
 * warmer at dusk. Subtle but novel; almost no sites do this.
 *
 * Buckets:
 *   05–09  dawn    (cooler hue, more violet)
 *   09–17  day     (canonical accent)
 *   17–21  dusk    (warmer hue, more rose)
 *   21–05  night   (deeper, slightly desaturated)
 *
 * Re-evaluated on page load + every 30 minutes (covers idle tabs).
 * User can pin via localStorage 'tod' = 'auto' | bucket name.
 */
(function () {
    if (window.__todMounted) return;
    window.__todMounted = true;

    function bucket(hour) {
        if (hour >= 5  && hour <  9)  return 'dawn';
        if (hour >= 9  && hour < 17)  return 'day';
        if (hour >= 17 && hour < 21)  return 'dusk';
        return 'night';
    }
    function apply() {
        const override = localStorage.getItem('tod');
        const auto = bucket(new Date().getHours());
        const value = (override && override !== 'auto') ? override : auto;
        document.documentElement.setAttribute('data-tod', value);
    }
    apply();
    setInterval(apply, 30 * 60 * 1000);
})();
