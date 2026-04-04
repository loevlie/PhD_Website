/**
 * MIL Forward Pass Pipeline Visualization
 * Desktop: full horizontal pipeline
 * Mobile: 3 stages at a time, auto-advancing
 */
(function() {
    var container = document.getElementById('mil-pipeline-demo');
    if (!container) return;

    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    container.appendChild(canvas);

    var DPR = Math.min(window.devicePixelRatio, 2);
    var W = 0, H = 0;
    var isMobile = false;

    var NUM_SLICES = 5;
    var sliceImgs = [];
    var loadedCount = 0;
    var sliceIndices = [3, 6, 8, 10, 12];

    sliceIndices.forEach(function(idx, i) {
        var img = new Image();
        var padded = idx < 10 ? '0' + idx : '' + idx;
        img.src = '/static/portfolio/images/blog/brain/slice_' + padded + '.png';
        img.onload = function() { loadedCount++; };
        sliceImgs[i] = img;
    });

    function getCtp(name) {
        return getComputedStyle(document.documentElement).getPropertyValue('--ctp-' + name).trim() || '#888';
    }

    var embeddings = [
        [0.21, -0.54, 0.12],
        [0.18, -0.48, 0.09],
        [-0.33, 0.61, -0.15],
        [0.82, 0.73, -0.91],
        [-0.27, -0.39, 0.22],
    ];

    function computeMean() {
        var m = [0, 0, 0];
        for (var i = 0; i < embeddings.length; i++)
            for (var j = 0; j < 3; j++) m[j] += embeddings[i][j];
        for (var j = 0; j < 3; j++) m[j] = Math.round((m[j] / embeddings.length) * 100) / 100;
        return m;
    }

    function resize() {
        W = Math.min(container.clientWidth, 860);
        isMobile = W < 500;
        H = isMobile ? Math.min(W * 0.75, 300) : Math.min(W * 0.5, 360);
        canvas.width = W * DPR;
        canvas.height = H * DPR;
        canvas.style.width = W + 'px';
        canvas.style.height = H + 'px';
        ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    }

    function drawRoundedRect(x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }

    function drawArrowLine(x1, y1, x2, y2, color, alpha) {
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = color; ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
        ctx.setLineDash([]);
        var angle = Math.atan2(y2 - y1, x2 - x1);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - 6 * Math.cos(angle - 0.4), y2 - 6 * Math.sin(angle - 0.4));
        ctx.lineTo(x2 - 6 * Math.cos(angle + 0.4), y2 - 6 * Math.sin(angle + 0.4));
        ctx.closePath(); ctx.fill();
        ctx.restore();
    }

    function formatVec(v) {
        return '[' + v.map(function(n) { return n >= 0 ? ' ' + n.toFixed(2) : n.toFixed(2); }).join(', ') + ']';
    }

    function formatVecShort(v) {
        return '[' + v.map(function(n) { return n.toFixed(1); }).join(', ') + ']';
    }

    var time = 0;

    // Mobile: 4 "windows" of 3 stages each
    // 0: Slices → Encoder → Embeddings
    // 1: Embeddings → MeanPool → BagVec
    // 2: BagVec → Classifier → Output
    var MOBILE_WINDOWS = 3;
    var MOBILE_WINDOW_DURATION = 3; // seconds per window

    // ── DRAWING FUNCTIONS FOR EACH STAGE ──
    // Each takes a bounding box (x, y, w, h) and an alpha

    function drawSlices(x, y, w, h, alpha, fontSize, monoSize) {
        ctx.globalAlpha = alpha;
        var sliceSize = Math.min(w * 0.8, h / NUM_SLICES * 0.85);
        var rowH = h / NUM_SLICES;
        var redCol = getCtp('red');
        for (var i = 0; i < NUM_SLICES; i++) {
            var sy = y + rowH * i + (rowH - sliceSize) / 2;
            var sx = x + (w - sliceSize) / 2;
            if (sliceImgs[i] && sliceImgs[i].complete)
                ctx.drawImage(sliceImgs[i], sx, sy, sliceSize, sliceSize);
            if (i === 3) {
                ctx.strokeStyle = redCol; ctx.lineWidth = 2;
                ctx.strokeRect(sx - 1, sy - 1, sliceSize + 2, sliceSize + 2);
            }
        }
        ctx.globalAlpha = 1;
    }

    function drawEncoder(x, y, w, h, alpha, fontSize, monoSize) {
        ctx.globalAlpha = alpha;
        var bgBlock = getCtp('mantle'); var borderCol = getCtp('surface0');
        var mauveCol = getCtp('mauve'); var textCol = getCtp('subtext0');
        ctx.fillStyle = bgBlock; ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5;
        var pad = h * 0.05;
        ctx.beginPath();
        ctx.moveTo(x, y - pad);
        ctx.lineTo(x + w, y + h * 0.18);
        ctx.lineTo(x + w, y + h * 0.82);
        ctx.lineTo(x, y + h + pad);
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = mauveCol;
        ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Encoder', x + w / 2, y + h / 2 - 2);
        ctx.fillStyle = textCol;
        ctx.font = monoSize + 'px JetBrains Mono, monospace';
        ctx.fillText('f(xᵢⱼ)', x + w / 2, y + h / 2 + 13);
        ctx.globalAlpha = 1;
    }

    function drawEmbeddings(x, y, w, h, alpha, fontSize, monoSize) {
        ctx.globalAlpha = alpha;
        var bgBlock = getCtp('mantle'); var borderCol = getCtp('surface0');
        var blueCol = getCtp('blue'); var redCol = getCtp('red');
        var rowH = h / NUM_SLICES;
        for (var i = 0; i < NUM_SLICES; i++) {
            var vy = y + rowH * i + rowH * 0.15;
            var vh = rowH * 0.7;
            drawRoundedRect(x, vy, w, vh, 4);
            ctx.fillStyle = bgBlock; ctx.fill();
            ctx.strokeStyle = (i === 3) ? redCol : borderCol;
            ctx.lineWidth = (i === 3) ? 1.5 : 1;
            ctx.stroke();
            ctx.fillStyle = (i === 3) ? redCol : blueCol;
            ctx.font = monoSize + 'px JetBrains Mono, monospace';
            ctx.textAlign = 'center';
            var vec = isMobile ? formatVecShort(embeddings[i]) : formatVec(embeddings[i]);
            ctx.fillText(vec, x + w / 2, vy + vh / 2 + 3);
        }
        ctx.globalAlpha = 1;
    }

    function drawMeanPool(x, y, w, h, alpha, fontSize) {
        ctx.globalAlpha = alpha;
        var bgBlock = getCtp('mantle'); var borderCol = getCtp('surface0');
        var greenCol = getCtp('green');
        ctx.fillStyle = bgBlock; ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5;
        var midY = y + h / 2;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + w, midY - 14);
        ctx.lineTo(x + w, midY + 14);
        ctx.lineTo(x, y + h);
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = greenCol;
        ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Mean', x + w / 2, midY - 1);
        ctx.fillText('Pool', x + w / 2, midY + 12);
        ctx.globalAlpha = 1;
    }

    function drawBagVec(x, y, w, h, alpha, monoSize) {
        ctx.globalAlpha = alpha;
        var bgBlock = getCtp('mantle'); var mauveCol = getCtp('mauve');
        var midY = y + h / 2;
        var vh = Math.min(36, h * 0.3);
        drawRoundedRect(x, midY - vh / 2, w, vh, 5);
        ctx.fillStyle = bgBlock; ctx.fill();
        ctx.strokeStyle = mauveCol; ctx.lineWidth = 2; ctx.stroke();
        ctx.fillStyle = mauveCol;
        ctx.font = 'bold ' + monoSize + 'px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        var vec = isMobile ? formatVecShort(computeMean()) : formatVec(computeMean());
        ctx.fillText(vec, x + w / 2, midY + 4);
        ctx.globalAlpha = 1;
    }

    function drawClassifier(x, y, w, h, alpha, fontSize) {
        ctx.globalAlpha = alpha;
        var bgBlock = getCtp('mantle'); var borderCol = getCtp('surface0');
        var accentCol = getCtp('lavender');
        var midY = y + h / 2;
        var bh = Math.min(50, h * 0.35);
        drawRoundedRect(x, midY - bh / 2, w, bh, 5);
        ctx.fillStyle = bgBlock; ctx.fill();
        ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5; ctx.stroke();
        ctx.fillStyle = accentCol;
        ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('g(z)', x + w / 2, midY + 4);
        ctx.globalAlpha = 1;
    }

    function drawOutput(x, y, w, h, alpha, fontSize) {
        ctx.globalAlpha = alpha;
        var redCol = getCtp('red');
        var midY = y + h / 2;
        var bw = Math.min(w, 60);
        var bh = 28;
        drawRoundedRect(x + (w - bw) / 2, midY - bh / 2, bw, bh, 6);
        ctx.fillStyle = redCol; ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Y=1', x + w / 2, midY + 5);
        ctx.globalAlpha = 1;
    }

    // ── LABELS ──
    var stageLabels = ['Instances', 'Encoder', 'Embeddings', 'Aggregate', 'Bag Vector', 'Classifier', 'Ŷ'];
    var drawFns = [drawSlices, drawEncoder, drawEmbeddings, drawMeanPool, drawBagVec, drawClassifier, drawOutput];

    function draw() {
        ctx.clearRect(0, 0, W, H);
        var borderCol = getCtp('surface0');
        var textCol = getCtp('subtext0');
        var padY = H * 0.08;
        var labelH = 18;
        var contentH = H - padY - labelH - 4;
        var fontSize = Math.max(8, Math.min(12, W * 0.015));
        var monoSize = Math.max(7, Math.min(10, W * 0.012));
        var labelSize = Math.max(8, Math.min(11, W * 0.014));

        if (!isMobile) {
            // ── DESKTOP: full horizontal ──
            var cycleDuration = 10;
            var t = (time % cycleDuration) / cycleDuration * 7;
            var numCols = 7;
            var gap = W * 0.015;
            var colW = (W - gap * (numCols + 1)) / numCols;
            var stageAlphas = [];
            for (var s = 0; s < numCols; s++) {
                stageAlphas[s] = Math.min(1, Math.max(0, (t - s * 0.8) * 1.5));
            }

            for (var s = 0; s < numCols; s++) {
                var sx = gap + s * (colW + gap);
                drawFns[s](sx, padY, colW, contentH, stageAlphas[s], fontSize, monoSize);

                // Label
                ctx.fillStyle = textCol;
                ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(stageLabels[s], sx + colW / 2, H - 4);

                // Arrow to next
                if (s < numCols - 1) {
                    var arrowAlpha = Math.min(stageAlphas[s], stageAlphas[s + 1]) * 0.5;
                    drawArrowLine(sx + colW + 2, padY + contentH / 2, sx + colW + gap - 2, padY + contentH / 2, borderCol, arrowAlpha);
                }
            }
        } else {
            // ── MOBILE: 3 stages at a time, auto-advancing ──
            var windowDuration = MOBILE_WINDOW_DURATION;
            var totalDuration = windowDuration * MOBILE_WINDOWS + 1; // +1 for pause
            var cycleTime = time % totalDuration;
            var windowIdx = Math.min(MOBILE_WINDOWS - 1, Math.floor(cycleTime / windowDuration));
            var windowT = (cycleTime - windowIdx * windowDuration) / windowDuration;

            // Which 3 stages to show
            var stageStart = windowIdx * 2; // 0,2,4
            var stages = [stageStart, stageStart + 1, stageStart + 2];
            // Clamp
            stages = stages.map(function(s) { return Math.min(s, 6); });
            // Deduplicate
            var uniqueStages = [];
            stages.forEach(function(s) { if (uniqueStages.indexOf(s) === -1) uniqueStages.push(s); });

            var numShow = uniqueStages.length;
            var gap = W * 0.03;
            var colW = (W - gap * (numShow + 1)) / numShow;

            for (var si = 0; si < numShow; si++) {
                var s = uniqueStages[si];
                var sx = gap + si * (colW + gap);
                var alpha = Math.min(1, Math.max(0, (windowT * 3 - si * 0.6) * 1.5));

                drawFns[s](sx, padY, colW, contentH, alpha, fontSize, monoSize);

                ctx.fillStyle = textCol;
                ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(stageLabels[s], sx + colW / 2, H - 4);

                if (si < numShow - 1) {
                    var nextS = uniqueStages[si + 1];
                    var nextSx = gap + (si + 1) * (colW + gap);
                    var arrowAlpha = Math.min(1, Math.max(0, (windowT * 3 - (si + 0.5) * 0.6) * 1.5)) * 0.5;
                    drawArrowLine(sx + colW + 2, padY + contentH / 2, nextSx - 2, padY + contentH / 2, borderCol, arrowAlpha);
                }
            }

            // Progress dots
            var dotY = H - labelH + 6;
            for (var d = 0; d < MOBILE_WINDOWS; d++) {
                ctx.beginPath();
                ctx.arc(W / 2 + (d - 1) * 14, dotY, 3, 0, Math.PI * 2);
                ctx.fillStyle = d === windowIdx ? getCtp('lavender') : borderCol;
                ctx.fill();
            }
        }
    }

    function animate() {
        requestAnimationFrame(animate);
        time += 0.016;
        draw();
    }

    window.addEventListener('resize', function() { resize(); });
    resize();
    animate();

    new MutationObserver(function() { draw(); }).observe(
        document.documentElement, { attributes: true, attributeFilter: ['class'] }
    );
})();
