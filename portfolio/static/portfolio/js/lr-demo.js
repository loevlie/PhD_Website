/**
 * Interactive Logistic Regression Demo
 * Drag 2 red and 2 blue dots. A linear decision boundary is drawn if separable.
 */
(function() {
    var container = document.getElementById('lr-interactive-demo');
    if (!container) return;

    // Create canvas
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    container.appendChild(canvas);

    // Create status text
    var status = document.createElement('div');
    status.className = 'lr-demo-status';
    status.textContent = 'Drag the dots to explore linear separability';
    container.appendChild(status);

    // State
    var points = [
        { x: -1.5, y:  1.0, cls: 0 },  // red
        { x: -1.0, y: -1.0, cls: 0 },  // red
        { x:  1.5, y:  0.5, cls: 1 },  // blue
        { x:  1.0, y: -0.5, cls: 1 },  // blue
    ];
    var dragging = null;
    var hovered = null;
    var RANGE = 3.5;
    var DOT_RADIUS = 10;

    function resize() {
        var rect = container.getBoundingClientRect();
        var size = Math.min(rect.width, 400);
        canvas.width = size * window.devicePixelRatio;
        canvas.height = size * window.devicePixelRatio;
        canvas.style.width = size + 'px';
        canvas.style.height = size + 'px';
        ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
        draw();
    }

    function toScreen(v) {
        var w = parseFloat(canvas.style.width);
        var h = parseFloat(canvas.style.height);
        return {
            x: (v.x + RANGE) / (2 * RANGE) * w,
            y: (RANGE - v.y) / (2 * RANGE) * h
        };
    }

    function toWorld(sx, sy) {
        var w = parseFloat(canvas.style.width);
        var h = parseFloat(canvas.style.height);
        return {
            x: (sx / w) * 2 * RANGE - RANGE,
            y: RANGE - (sy / h) * 2 * RANGE
        };
    }

    // Check if linearly separable and find boundary
    // Using simple perceptron for 4 points
    function findBoundary() {
        var lr = 0.1;
        var w = [0, 0];
        var b = 0;
        var maxIter = 1000;
        var converged = false;

        for (var iter = 0; iter < maxIter; iter++) {
            var errors = 0;
            for (var i = 0; i < points.length; i++) {
                var p = points[i];
                var pred = w[0] * p.x + w[1] * p.y + b;
                var label = p.cls === 1 ? 1 : -1;
                if (pred * label <= 0) {
                    w[0] += lr * label * p.x;
                    w[1] += lr * label * p.y;
                    b += lr * label;
                    errors++;
                }
            }
            if (errors === 0) { converged = true; break; }
        }

        // Verify
        if (converged) {
            for (var i = 0; i < points.length; i++) {
                var p = points[i];
                var pred = w[0] * p.x + w[1] * p.y + b;
                var label = p.cls === 1 ? 1 : -1;
                if (pred * label <= 0) { converged = false; break; }
            }
        }

        return { w: w, b: b, separable: converged };
    }

    function getColors() {
        var isDark = document.documentElement.classList.contains('mocha') ||
                     document.documentElement.classList.contains('frappe') ||
                     document.documentElement.classList.contains('macchiato');
        return {
            bg: getComputedStyle(document.documentElement).getPropertyValue('--ctp-crust').trim(),
            grid: isDark ? 'rgba(205, 214, 244, 0.07)' : 'rgba(76, 79, 105, 0.08)',
            axis: isDark ? 'rgba(205, 214, 244, 0.15)' : 'rgba(76, 79, 105, 0.15)',
            red: getComputedStyle(document.documentElement).getPropertyValue('--ctp-red').trim(),
            blue: getComputedStyle(document.documentElement).getPropertyValue('--ctp-blue').trim(),
            green: getComputedStyle(document.documentElement).getPropertyValue('--ctp-green').trim(),
            yellow: getComputedStyle(document.documentElement).getPropertyValue('--ctp-yellow').trim(),
            text: getComputedStyle(document.documentElement).getPropertyValue('--ctp-overlay0').trim(),
        };
    }

    function draw() {
        var w = parseFloat(canvas.style.width);
        var h = parseFloat(canvas.style.height);
        var c = getColors();

        // Background
        ctx.fillStyle = c.bg;
        ctx.fillRect(0, 0, w, h);

        // Grid lines
        ctx.strokeStyle = c.grid;
        ctx.lineWidth = 1;
        for (var i = -3; i <= 3; i++) {
            var s = toScreen({ x: i, y: 0 });
            ctx.beginPath(); ctx.moveTo(s.x, 0); ctx.lineTo(s.x, h); ctx.stroke();
            s = toScreen({ x: 0, y: i });
            ctx.beginPath(); ctx.moveTo(0, s.y); ctx.lineTo(w, s.y); ctx.stroke();
        }

        // Axes
        ctx.strokeStyle = c.axis;
        ctx.lineWidth = 1.5;
        var origin = toScreen({ x: 0, y: 0 });
        ctx.beginPath(); ctx.moveTo(0, origin.y); ctx.lineTo(w, origin.y); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(origin.x, 0); ctx.lineTo(origin.x, h); ctx.stroke();

        // Axis labels
        ctx.fillStyle = c.text;
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('x₁', w - 12, origin.y - 8);
        ctx.fillText('x₂', origin.x + 14, 14);

        // Decision boundary
        var result = findBoundary();
        if (result.w[0] !== 0 || result.w[1] !== 0) {
            ctx.lineWidth = 2;
            ctx.setLineDash(result.separable ? [] : [6, 4]);
            ctx.strokeStyle = result.separable ? c.green : c.yellow;

            // Draw line across canvas
            var bw = result.w, bb = result.b;
            if (Math.abs(bw[1]) > Math.abs(bw[0])) {
                // y = -(w0*x + b) / w1
                var x1 = -RANGE, x2 = RANGE;
                var y1 = -(bw[0] * x1 + bb) / bw[1];
                var y2 = -(bw[0] * x2 + bb) / bw[1];
                var s1 = toScreen({ x: x1, y: y1 });
                var s2 = toScreen({ x: x2, y: y2 });
                ctx.beginPath(); ctx.moveTo(s1.x, s1.y); ctx.lineTo(s2.x, s2.y); ctx.stroke();
            } else {
                // x = -(w1*y + b) / w0
                var y1 = -RANGE, y2 = RANGE;
                var x1 = -(bw[1] * y1 + bb) / bw[0];
                var x2 = -(bw[1] * y2 + bb) / bw[0];
                var s1 = toScreen({ x: x1, y: y1 });
                var s2 = toScreen({ x: x2, y: y2 });
                ctx.beginPath(); ctx.moveTo(s1.x, s1.y); ctx.lineTo(s2.x, s2.y); ctx.stroke();
            }
            ctx.setLineDash([]);

            // If not separable, draw X marks on misclassified
            if (!result.separable) {
                for (var i = 0; i < points.length; i++) {
                    var p = points[i];
                    var pred = bw[0] * p.x + bw[1] * p.y + bb;
                    var label = p.cls === 1 ? 1 : -1;
                    if (pred * label <= 0) {
                        var s = toScreen(p);
                        ctx.strokeStyle = c.yellow;
                        ctx.lineWidth = 2.5;
                        var xr = 16;
                        ctx.beginPath(); ctx.moveTo(s.x - xr, s.y - xr); ctx.lineTo(s.x + xr, s.y + xr); ctx.stroke();
                        ctx.beginPath(); ctx.moveTo(s.x + xr, s.y - xr); ctx.lineTo(s.x - xr, s.y + xr); ctx.stroke();
                    }
                }
            }
        }

        // Draw dots
        for (var i = 0; i < points.length; i++) {
            var p = points[i];
            var s = toScreen(p);
            var isHover = hovered === i || dragging === i;
            var r = isHover ? DOT_RADIUS + 3 : DOT_RADIUS;

            // Glow
            if (isHover) {
                ctx.beginPath();
                ctx.arc(s.x, s.y, r + 6, 0, Math.PI * 2);
                ctx.fillStyle = (p.cls === 0 ? c.red : c.blue).replace(')', ', 0.15)').replace('rgb', 'rgba');
                ctx.fill();
            }

            // Dot
            ctx.beginPath();
            ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
            ctx.fillStyle = p.cls === 0 ? c.red : c.blue;
            ctx.fill();

            // Border
            ctx.strokeStyle = 'rgba(0,0,0,0.2)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // Status
        if (result.separable) {
            status.textContent = '✓ Linearly separable — decision boundary found';
            status.style.color = c.green;
        } else {
            status.textContent = '✗ Not linearly separable';
            status.style.color = c.yellow;
        }
    }

    // Interaction
    function getMousePos(e) {
        var rect = canvas.getBoundingClientRect();
        var touch = e.touches ? e.touches[0] : e;
        return { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
    }

    function findPoint(mx, my) {
        for (var i = points.length - 1; i >= 0; i--) {
            var s = toScreen(points[i]);
            var dx = mx - s.x, dy = my - s.y;
            if (dx * dx + dy * dy < (DOT_RADIUS + 8) * (DOT_RADIUS + 8)) return i;
        }
        return null;
    }

    function onDown(e) {
        e.preventDefault();
        var pos = getMousePos(e);
        dragging = findPoint(pos.x, pos.y);
    }

    function onMove(e) {
        var pos = getMousePos(e);
        if (dragging !== null) {
            e.preventDefault();
            var world = toWorld(pos.x, pos.y);
            points[dragging].x = Math.max(-RANGE + 0.3, Math.min(RANGE - 0.3, world.x));
            points[dragging].y = Math.max(-RANGE + 0.3, Math.min(RANGE - 0.3, world.y));
            draw();
        } else {
            var h = findPoint(pos.x, pos.y);
            if (h !== hovered) { hovered = h; canvas.style.cursor = h !== null ? 'grab' : 'default'; draw(); }
        }
    }

    function onUp() {
        dragging = null;
        canvas.style.cursor = hovered !== null ? 'grab' : 'default';
    }

    canvas.addEventListener('mousedown', onDown);
    canvas.addEventListener('mousemove', onMove);
    canvas.addEventListener('mouseup', onUp);
    canvas.addEventListener('mouseleave', function() { dragging = null; hovered = null; draw(); });

    canvas.addEventListener('touchstart', onDown, { passive: false });
    canvas.addEventListener('touchmove', onMove, { passive: false });
    canvas.addEventListener('touchend', onUp);

    // Init
    window.addEventListener('resize', resize);
    resize();

    // Re-draw on theme change
    var observer = new MutationObserver(function() { draw(); });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
})();
