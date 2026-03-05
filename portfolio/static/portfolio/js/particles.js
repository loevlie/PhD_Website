// Particle canvas background for hero section
(function () {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;

    // Disable on mobile / touch devices for performance
    if (window.matchMedia('(max-width: 768px)').matches || 'ontouchstart' in window) {
        canvas.style.display = 'none';
        return;
    }

    const ctx = canvas.getContext('2d');
    let width, height, particles, mouse, animId;
    const PARTICLE_COUNT = 60;
    const CONNECT_DIST = 120;
    const MOUSE_RADIUS = 150;

    mouse = { x: -9999, y: -9999 };

    function getAccentColor() {
        return getComputedStyle(document.documentElement).getPropertyValue('--accent-light').trim();
    }

    function hexToRgb(hex) {
        var r = parseInt(hex.slice(1, 3), 16);
        var g = parseInt(hex.slice(3, 5), 16);
        var b = parseInt(hex.slice(5, 7), 16);
        return { r: r, g: g, b: b };
    }

    var accentRgb = hexToRgb(getAccentColor() || '#5eead4');

    window.addEventListener('themechange', function () {
        accentRgb = hexToRgb(getAccentColor() || '#5eead4');
    });

    function resize() {
        const hero = canvas.parentElement;
        width = canvas.width = hero.offsetWidth;
        height = canvas.height = hero.offsetHeight;
    }

    function createParticles() {
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                r: Math.random() * 2 + 1,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            // Mouse parallax push
            const dx = p.x - mouse.x;
            const dy = p.y - mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < MOUSE_RADIUS) {
                const force = (MOUSE_RADIUS - dist) / MOUSE_RADIUS * 0.6;
                p.x += dx / dist * force;
                p.y += dy / dist * force;
            }

            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(' + accentRgb.r + ', ' + accentRgb.g + ', ' + accentRgb.b + ', 0.35)';
            ctx.fill();

            // Connect nearby particles
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const ddx = p.x - p2.x;
                const ddy = p.y - p2.y;
                const d = Math.sqrt(ddx * ddx + ddy * ddy);
                if (d < CONNECT_DIST) {
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = 'rgba(' + accentRgb.r + ', ' + accentRgb.g + ', ' + accentRgb.b + ', ' + (0.15 * (1 - d / CONNECT_DIST)) + ')';
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                }
            }
        }
        animId = requestAnimationFrame(draw);
    }

    canvas.parentElement.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        mouse.x = e.clientX - rect.left;
        mouse.y = e.clientY - rect.top;
    });

    canvas.parentElement.addEventListener('mouseleave', () => {
        mouse.x = -9999;
        mouse.y = -9999;
    });

    window.addEventListener('resize', () => {
        resize();
        createParticles();
    });

    resize();
    createParticles();
    draw();
})();
