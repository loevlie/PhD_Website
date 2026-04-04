/**
 * Interactive MIL Mean Pooling Demo
 * 4 bags (2 negative, 2 positive) with 3 instances each.
 * Instances colored by true class. Bag means colored by bag label.
 */
(function() {
    var container = document.getElementById('mil-interactive-demo');
    if (!container) return;

    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    container.appendChild(canvas);

    var legend = document.createElement('div');
    legend.className = 'mil-demo-legend';
    container.appendChild(legend);

    var status = document.createElement('div');
    status.className = 'mil-demo-status';
    container.appendChild(status);

    var bags = [
        { label: 0, instances: [
            { x: -2.0, y:  1.5, positive: false },
            { x: -1.5, y:  0.5, positive: false },
            { x: -2.5, y:  0.8, positive: false },
        ]},
        { label: 0, instances: [
            { x: -1.8, y: -1.2, positive: false },
            { x: -2.3, y: -0.5, positive: false },
            { x: -1.2, y: -1.8, positive: false },
        ]},
        { label: 1, instances: [
            { x:  1.0, y:  1.8, positive: false },
            { x:  1.5, y:  0.8, positive: false },
            { x:  2.2, y:  2.0, positive: true  },
        ]},
        { label: 1, instances: [
            { x:  1.5, y: -0.5, positive: false },
            { x:  0.8, y: -1.5, positive: false },
            { x:  2.0, y: -0.2, positive: true  },
        ]},
    ];

    var RANGE = 3.5;
    var DOT_R = 8;
    var MEAN_R = 11;
    var dragging = null;
    var hovered = null;

    function resize() {
        var rect = container.getBoundingClientRect();
        var size = Math.min(rect.width, 500);
        canvas.width = size * window.devicePixelRatio;
        canvas.height = size * window.devicePixelRatio;
        canvas.style.width = size + 'px';
        canvas.style.height = size + 'px';
        ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
        draw();
    }

    function toScreen(v) {
        var w = parseFloat(canvas.style.width), h = parseFloat(canvas.style.height);
        return { x: (v.x + RANGE) / (2 * RANGE) * w, y: (RANGE - v.y) / (2 * RANGE) * h };
    }

    function toWorld(sx, sy) {
        var w = parseFloat(canvas.style.width), h = parseFloat(canvas.style.height);
        return { x: (sx / w) * 2 * RANGE - RANGE, y: RANGE - (sy / h) * 2 * RANGE };
    }

    function bagMean(bag) {
        var mx = 0, my = 0;
        bag.instances.forEach(function(p) { mx += p.x; my += p.y; });
        return { x: mx / bag.instances.length, y: my / bag.instances.length };
    }

    function findBoundary() {
        var means = bags.map(function(b) { return { pt: bagMean(b), label: b.label }; });
        var lr = 0.1, w = [0, 0], b = 0, converged = false;
        for (var iter = 0; iter < 2000; iter++) {
            var errors = 0;
            for (var i = 0; i < means.length; i++) {
                var pred = w[0] * means[i].pt.x + w[1] * means[i].pt.y + b;
                var lbl = means[i].label === 1 ? 1 : -1;
                if (pred * lbl <= 0) { w[0] += lr * lbl * means[i].pt.x; w[1] += lr * lbl * means[i].pt.y; b += lr * lbl; errors++; }
            }
            if (errors === 0) { converged = true; break; }
        }
        if (converged) {
            for (var i = 0; i < means.length; i++) {
                var pred = w[0] * means[i].pt.x + w[1] * means[i].pt.y + b;
                if ((means[i].label === 1 ? 1 : -1) * pred <= 0) { converged = false; break; }
            }
        }
        return { w: w, b: b, separable: converged };
    }

    function getCtp(name) { return getComputedStyle(document.documentElement).getPropertyValue('--ctp-' + name).trim(); }

    function draw() {
        var w = parseFloat(canvas.style.width), h = parseFloat(canvas.style.height);
        var isDark = !document.documentElement.classList.contains('latte');

        var bgColor = getCtp('crust');
        var gridColor = isDark ? 'rgba(205,214,244,0.06)' : 'rgba(76,79,105,0.07)';
        var axisColor = isDark ? 'rgba(205,214,244,0.12)' : 'rgba(76,79,105,0.12)';
        var textColor = getCtp('overlay0');
        var greenColor = getCtp('green');
        var yellowColor = getCtp('yellow');
        var redColor = getCtp('red');
        var blueColor = getCtp('blue');

        // Background
        ctx.fillStyle = bgColor;
        ctx.fillRect(0, 0, w, h);

        // Grid
        ctx.strokeStyle = gridColor; ctx.lineWidth = 1;
        for (var i = -3; i <= 3; i++) {
            var s = toScreen({ x: i, y: 0 });
            ctx.beginPath(); ctx.moveTo(s.x, 0); ctx.lineTo(s.x, h); ctx.stroke();
            s = toScreen({ x: 0, y: i });
            ctx.beginPath(); ctx.moveTo(0, s.y); ctx.lineTo(w, s.y); ctx.stroke();
        }

        // Axes
        ctx.strokeStyle = axisColor; ctx.lineWidth = 1.5;
        var o = toScreen({ x: 0, y: 0 });
        ctx.beginPath(); ctx.moveTo(0, o.y); ctx.lineTo(w, o.y); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(o.x, 0); ctx.lineTo(o.x, h); ctx.stroke();
        ctx.fillStyle = textColor; ctx.font = '11px Inter, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('x₁', w - 12, o.y - 8); ctx.fillText('x₂', o.x + 14, 14);

        // Decision boundary
        var result = findBoundary();
        if (result.w[0] !== 0 || result.w[1] !== 0) {
            ctx.lineWidth = 2;
            ctx.setLineDash(result.separable ? [] : [6, 4]);
            ctx.strokeStyle = result.separable ? greenColor : yellowColor;
            var bw = result.w, bb = result.b;
            if (Math.abs(bw[1]) > Math.abs(bw[0])) {
                var x1 = -RANGE, x2 = RANGE;
                var s1 = toScreen({ x: x1, y: -(bw[0]*x1+bb)/bw[1] }), s2 = toScreen({ x: x2, y: -(bw[0]*x2+bb)/bw[1] });
            } else {
                var y1 = -RANGE, y2 = RANGE;
                var s1 = toScreen({ x: -(bw[1]*y1+bb)/bw[0], y: y1 }), s2 = toScreen({ x: -(bw[1]*y2+bb)/bw[0], y: y2 });
            }
            ctx.beginPath(); ctx.moveTo(s1.x, s1.y); ctx.lineTo(s2.x, s2.y); ctx.stroke();
            ctx.setLineDash([]);
        }

        // Lines from instances to their bag mean
        bags.forEach(function(bag) {
            var mean = bagMean(bag);
            var ms = toScreen(mean);
            var lineColor = bag.label === 1 ? redColor : blueColor;
            ctx.strokeStyle = lineColor; ctx.globalAlpha = 0.15; ctx.lineWidth = 1;
            bag.instances.forEach(function(inst) {
                var is = toScreen(inst);
                ctx.beginPath(); ctx.moveTo(is.x, is.y); ctx.lineTo(ms.x, ms.y); ctx.stroke();
            });
            ctx.globalAlpha = 1.0;
        });

        // Draw instances — colored by class
        bags.forEach(function(bag, bi) {
            bag.instances.forEach(function(inst, ii) {
                var s = toScreen(inst);
                var isH = (hovered && hovered.bag === bi && hovered.inst === ii) || (dragging && dragging.bag === bi && dragging.inst === ii);
                var r = isH ? DOT_R + 3 : DOT_R;
                var color = inst.positive ? redColor : blueColor;

                if (isH) {
                    ctx.beginPath(); ctx.arc(s.x, s.y, r + 6, 0, Math.PI * 2);
                    ctx.fillStyle = color + '22'; ctx.fill();
                }

                ctx.beginPath(); ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
                ctx.fillStyle = color; ctx.fill();
                ctx.strokeStyle = isDark ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.12)';
                ctx.lineWidth = 1; ctx.stroke();
            });
        });

        // Draw bag means — colored by bag label
        bags.forEach(function(bag, bi) {
            var mean = bagMean(bag);
            var s = toScreen(mean);
            var color = bag.label === 1 ? redColor : blueColor;
            var r = MEAN_R;

            ctx.save();
            ctx.translate(s.x, s.y);
            ctx.rotate(Math.PI / 4);
            ctx.fillStyle = color;
            ctx.fillRect(-r / 1.4, -r / 1.4, r * 1.4, r * 1.4);
            ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.2)';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(-r / 1.4, -r / 1.4, r * 1.4, r * 1.4);
            ctx.restore();

            // Bag label
            ctx.fillStyle = textColor;
            ctx.font = 'bold 11px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(bag.label === 1 ? 'Bag +' : 'Bag −', s.x, s.y - r - 6);
        });

        // Status
        if (result.separable) {
            status.textContent = '✓ Mean-pooled bag embeddings are linearly separable';
            status.style.color = greenColor;
        } else {
            status.textContent = '✗ Mean pooling fails — bag embeddings not separable';
            status.style.color = yellowColor;
        }

        legend.innerHTML =
            '<span style="color:' + blueColor + '">● negative instance</span>' +
            '<span style="color:' + redColor + '">  ● positive instance</span>' +
            '<span style="color:' + textColor + '">  ◆ bag mean embedding</span>';
    }

    // Interaction
    function getMousePos(e) {
        var rect = canvas.getBoundingClientRect();
        var touch = e.touches ? e.touches[0] : e;
        return { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
    }

    function findInstance(mx, my) {
        for (var bi = bags.length - 1; bi >= 0; bi--)
            for (var ii = bags[bi].instances.length - 1; ii >= 0; ii--) {
                var s = toScreen(bags[bi].instances[ii]);
                var dx = mx - s.x, dy = my - s.y;
                if (dx*dx + dy*dy < (DOT_R+8)*(DOT_R+8)) return { bag: bi, inst: ii };
            }
        return null;
    }

    function onDown(e) { e.preventDefault(); dragging = findInstance(getMousePos(e).x, getMousePos(e).y); }
    function onMove(e) {
        var pos = getMousePos(e);
        if (dragging) {
            e.preventDefault();
            var world = toWorld(pos.x, pos.y);
            var inst = bags[dragging.bag].instances[dragging.inst];
            inst.x = Math.max(-RANGE+0.3, Math.min(RANGE-0.3, world.x));
            inst.y = Math.max(-RANGE+0.3, Math.min(RANGE-0.3, world.y));
            draw();
        } else {
            var h = findInstance(pos.x, pos.y);
            if (JSON.stringify(h) !== JSON.stringify(hovered)) { hovered = h; canvas.style.cursor = h ? 'grab' : 'default'; draw(); }
        }
    }
    function onUp() { dragging = null; canvas.style.cursor = hovered ? 'grab' : 'default'; }

    canvas.addEventListener('mousedown', onDown);
    canvas.addEventListener('mousemove', onMove);
    canvas.addEventListener('mouseup', onUp);
    canvas.addEventListener('mouseleave', function() { dragging = null; hovered = null; draw(); });
    canvas.addEventListener('touchstart', onDown, { passive: false });
    canvas.addEventListener('touchmove', onMove, { passive: false });
    canvas.addEventListener('touchend', onUp);

    window.addEventListener('resize', resize);
    resize();
    new MutationObserver(function() { draw(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
})();
