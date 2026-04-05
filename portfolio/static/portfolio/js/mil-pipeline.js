/**
 * MIL Forward Pass Pipeline Visualization
 * Shows: Brain Slices → Encoder → Embedding Vectors → Mean Pool → Single Vector → Classifier → Label
 */
(function() {
    var container = document.getElementById('mil-pipeline-demo');
    if (!container) return;

    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    container.appendChild(canvas);

    var DPR = Math.min(window.devicePixelRatio, 2);
    var W = 0, H = 0;

    // Load brain slice thumbnails
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

    // Fake embedding values per slice (3D vectors)
    var embeddings = [
        [0.21, -0.54, 0.12],
        [0.18, -0.48, 0.09],
        [-0.33, 0.61, -0.15],
        [0.82, 0.73, -0.91],  // positive slice — different pattern
        [-0.27, -0.39, 0.22],
    ];

    // Mean of embeddings
    function computeMean() {
        var m = [0, 0, 0];
        for (var i = 0; i < embeddings.length; i++) {
            for (var j = 0; j < 3; j++) m[j] += embeddings[i][j];
        }
        for (var j = 0; j < 3; j++) m[j] = Math.round((m[j] / embeddings.length) * 100) / 100;
        return m;
    }

    var isMobile = false;

    function resize() {
        W = Math.min(container.clientWidth, 860);
        isMobile = W < 500;
        H = isMobile ? Math.min(W * 0.7, 280) : Math.min(W * 0.5, 360);
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
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
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

    var time = 0;

    function draw() {
        if (isMobile) { drawMobile(); return; }
        ctx.clearRect(0, 0, W, H);

        var bgBlock = getCtp('mantle');
        var borderCol = getCtp('surface0');
        var textCol = getCtp('subtext0');
        var labelCol = getCtp('text');
        var accentCol = getCtp('lavender');
        var blueCol = getCtp('blue');
        var redCol = getCtp('red');
        var greenCol = getCtp('green');
        var mauveCol = getCtp('mauve');

        var cycleDuration = 14;
        var t = (time % cycleDuration) / cycleDuration * 7;

        var padY = H * 0.08;
        var padX = W * 0.01;
        var midY = H / 2;
        var rowH = (H - padY * 2) / NUM_SLICES;
        var fontSize = Math.max(8, Math.min(12, W * 0.015));
        var monoSize = Math.max(7, Math.min(10, W * 0.012));
        var labelSize = Math.max(8, Math.min(11, W * 0.013));

        // Column X positions
        var colSlice = padX;
        var colSliceW = W * 0.08;
        var colEnc = W * 0.14;
        var colEncW = W * 0.10;
        var colEmb = W * 0.29;
        var colEmbW = W * 0.18;
        var colPool = W * 0.52;
        var colPoolW = W * 0.08;
        var colMean = W * 0.64;
        var colMeanW = W * 0.18;
        var colCls = W * 0.84;
        var colClsW = W * 0.08;
        var colOut = W * 0.93;

        // ── Slices ──
        var sliceAlpha = Math.min(1, t * 2);
        ctx.globalAlpha = sliceAlpha;
        var sliceSize = Math.min(colSliceW, rowH * 0.85);
        for (var i = 0; i < NUM_SLICES; i++) {
            var sy = padY + rowH * i + (rowH - sliceSize) / 2;
            var sx = colSlice + (colSliceW - sliceSize) / 2;
            if (sliceImgs[i] && sliceImgs[i].complete) {
                ctx.drawImage(sliceImgs[i], sx, sy, sliceSize, sliceSize);
            }
            if (i === 3) { // positive
                ctx.strokeStyle = redCol; ctx.lineWidth = 2;
                ctx.strokeRect(sx - 1, sy - 1, sliceSize + 2, sliceSize + 2);
            }
        }
        ctx.globalAlpha = 1;

        // Label
        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Instances (xᵢⱼ)', colSlice + colSliceW / 2, H - 4);

        // ── Encoder ──
        var encAlpha = Math.min(1, Math.max(0, (t - 0.3) * 1.5));
        ctx.globalAlpha = encAlpha;

        // Funnel shape
        ctx.fillStyle = bgBlock; ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5;
        var encTopPad = H * 0.05;
        ctx.beginPath();
        ctx.moveTo(colEnc, padY - encTopPad);
        ctx.lineTo(colEnc + colEncW, padY + H * 0.15);
        ctx.lineTo(colEnc + colEncW, H - padY - H * 0.15);
        ctx.lineTo(colEnc, H - padY + encTopPad);
        ctx.closePath();
        ctx.fill(); ctx.stroke();

        ctx.fillStyle = mauveCol;
        ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif';
        ctx.fillText('Encoder', colEnc + colEncW / 2, midY - 2);
        ctx.fillStyle = textCol;
        ctx.font = monoSize + 'px JetBrains Mono, monospace';
        ctx.fillText('f(xᵢⱼ)', colEnc + colEncW / 2, midY + 12);
        ctx.globalAlpha = 1;

        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.fillText('Encoder', colEnc + colEncW / 2, H - 4);

        // Arrows: slices → encoder
        var a1 = Math.min(1, Math.max(0, (t - 0.5) * 1.2));
        for (var i = 0; i < NUM_SLICES; i++) {
            var sy = padY + rowH * (i + 0.5);
            drawArrowLine(colSlice + colSliceW + 2, sy, colEnc - 3, sy, borderCol, a1 * 0.4);
        }

        // ── Embedding Vectors ──
        var embAlpha = Math.min(1, Math.max(0, (t - 1.5) * 1.2));
        ctx.globalAlpha = embAlpha;

        for (var i = 0; i < NUM_SLICES; i++) {
            var vy = padY + rowH * i + (rowH - rowH * 0.65) / 2;
            var vh = rowH * 0.65;
            var vx = colEmb;

            drawRoundedRect(vx, vy, colEmbW, vh, 4);
            ctx.fillStyle = bgBlock; ctx.fill();
            ctx.strokeStyle = (i === 3) ? redCol : borderCol;
            ctx.lineWidth = (i === 3) ? 1.5 : 1;
            ctx.stroke();

            ctx.fillStyle = (i === 3) ? redCol : blueCol;
            ctx.font = monoSize + 'px JetBrains Mono, monospace';
            ctx.textAlign = 'center';
            ctx.fillText(formatVec(embeddings[i]), vx + colEmbW / 2, vy + vh / 2 + 3);
        }
        ctx.globalAlpha = 1;

        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Embeddings (hᵢⱼ)', colEmb + colEmbW / 2, H - 4);

        // Arrows: encoder → embeddings
        var a2 = Math.min(1, Math.max(0, (t - 1.2) * 1.2));
        for (var i = 0; i < NUM_SLICES; i++) {
            var sy = padY + rowH * (i + 0.5);
            drawArrowLine(colEnc + colEncW + 2, sy, colEmb - 3, sy, borderCol, a2 * 0.4);
        }

        // ── Mean Pooling ──
        var poolAlpha = Math.min(1, Math.max(0, (t - 3) * 1.2));
        ctx.globalAlpha = poolAlpha;

        ctx.fillStyle = bgBlock; ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(colPool, padY);
        ctx.lineTo(colPool + colPoolW, midY - 16);
        ctx.lineTo(colPool + colPoolW, midY + 16);
        ctx.lineTo(colPool, H - padY);
        ctx.closePath();
        ctx.fill(); ctx.stroke();

        ctx.fillStyle = greenCol;
        ctx.font = 'bold ' + Math.max(8, fontSize - 1) + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Mean', colPool + colPoolW / 2, midY - 1);
        ctx.fillText('Pool', colPool + colPoolW / 2, midY + 11);
        ctx.globalAlpha = 1;

        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.fillText('Aggregate', colPool + colPoolW / 2, H - 4);

        // Arrows: embeddings → pool
        var a3 = Math.min(1, Math.max(0, (t - 2.7) * 1.2));
        for (var i = 0; i < NUM_SLICES; i++) {
            var sy = padY + rowH * (i + 0.5);
            drawArrowLine(colEmb + colEmbW + 2, sy, colPool - 3, sy, borderCol, a3 * 0.4);
        }

        // ── Mean Vector ──
        var meanAlpha = Math.min(1, Math.max(0, (t - 3.8) * 1.5));
        ctx.globalAlpha = meanAlpha;
        var meanVec = computeMean();
        var mvH = rowH * 0.8;
        var mvY = midY - mvH / 2;

        drawRoundedRect(colMean, mvY, colMeanW, mvH, 5);
        ctx.fillStyle = bgBlock; ctx.fill();
        ctx.strokeStyle = mauveCol; ctx.lineWidth = 2; ctx.stroke();

        ctx.fillStyle = mauveCol;
        ctx.font = 'bold ' + monoSize + 'px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText(formatVec(meanVec), colMean + colMeanW / 2, midY + 3);
        ctx.globalAlpha = 1;

        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.fillText('Bag Embedding (z)', colMean + colMeanW / 2, H - 4);

        // Arrow: pool → mean
        var a4 = Math.min(1, Math.max(0, (t - 3.5) * 1.2));
        drawArrowLine(colPool + colPoolW + 2, midY, colMean - 3, midY, borderCol, a4 * 0.5);

        // ── Classifier ──
        var clsAlpha = Math.min(1, Math.max(0, (t - 4.5) * 1.5));
        ctx.globalAlpha = clsAlpha;

        var clsH = rowH * 1.2;
        var clsY = midY - clsH / 2;
        drawRoundedRect(colCls, clsY, colClsW, clsH, 5);
        ctx.fillStyle = bgBlock; ctx.fill();
        ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5; ctx.stroke();

        ctx.fillStyle = accentCol;
        ctx.font = 'bold ' + Math.max(8, fontSize - 1) + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('g(z)', colCls + colClsW / 2, midY + 4);
        ctx.globalAlpha = 1;

        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.fillText('Classifier', colCls + colClsW / 2, H - 4);

        // Arrow: mean → classifier
        var a5 = Math.min(1, Math.max(0, (t - 4.3) * 1.2));
        drawArrowLine(colMean + colMeanW + 2, midY, colCls - 3, midY, borderCol, a5 * 0.5);

        // ── Output ──
        var outAlpha = Math.min(1, Math.max(0, (t - 5.2) * 1.5));
        ctx.globalAlpha = outAlpha;

        drawArrowLine(colCls + colClsW + 2, midY, colOut - 3, midY, borderCol, outAlpha * 0.5);

        var badgeW = W * 0.065;
        var badgeH = 26;
        drawRoundedRect(colOut, midY - badgeH / 2, badgeW, badgeH, 6);
        ctx.fillStyle = redCol; ctx.fill();

        ctx.fillStyle = '#fff';
        ctx.font = 'bold ' + Math.max(9, fontSize - 1) + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Y=1', colOut + badgeW / 2, midY + 4);
        ctx.globalAlpha = 1;

        ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif';
        ctx.fillText('Ŷ', colOut + badgeW / 2, H - 4);
    }

    // ── Mobile: show 3 stages at a time ──
    function drawMobile() {
        ctx.clearRect(0, 0, W, H);

        var bgBlock = getCtp('mantle');
        var borderCol = getCtp('surface0');
        var textCol = getCtp('subtext0');
        var blueCol = getCtp('blue');
        var redCol = getCtp('red');
        var greenCol = getCtp('green');
        var mauveCol = getCtp('mauve');
        var accentCol = getCtp('lavender');

        var padY = H * 0.08;
        var padX = W * 0.02;
        var midY = H / 2;
        var labelSize = Math.max(8, W * 0.022);
        var fontSize = Math.max(8, W * 0.025);
        var monoSize = Math.max(7, W * 0.02);
        var rowH = (H - padY * 2 - 20) / NUM_SLICES;

        // 3 windows: [0,1,2], [2,3,4], [4,5,6]
        var windowDuration = 4;
        var totalDuration = windowDuration * 3 + 1;
        var cycleTime = time % totalDuration;
        var windowIdx = Math.min(2, Math.floor(cycleTime / windowDuration));
        var wt = (cycleTime - windowIdx * windowDuration) / windowDuration;

        var stageStart = windowIdx * 2;
        var stages = [stageStart, stageStart + 1, Math.min(stageStart + 2, 6)];

        var gap = W * 0.03;
        var colW = (W - gap * 4) / 3;

        var stageNames = ['Instances (xᵢⱼ)', 'Encoder', 'Embeddings (hᵢⱼ)', 'Aggregate', 'Bag Embedding (z)', 'Classifier', 'Ŷ'];

        for (var si = 0; si < 3; si++) {
            var s = stages[si];
            var sx = gap + si * (colW + gap);
            var alpha = Math.min(1, Math.max(0, (wt * 3 - si * 0.5) * 1.5));

            ctx.globalAlpha = alpha;

            if (s === 0) {
                // Slices
                var sliceSize = Math.min(colW * 0.6, rowH * 0.85);
                for (var i = 0; i < NUM_SLICES; i++) {
                    var sy = padY + rowH * i + (rowH - sliceSize) / 2;
                    var ix = sx + (colW - sliceSize) / 2;
                    if (sliceImgs[i] && sliceImgs[i].complete) ctx.drawImage(sliceImgs[i], ix, sy, sliceSize, sliceSize);
                    if (i === 3) { ctx.strokeStyle = redCol; ctx.lineWidth = 2; ctx.strokeRect(ix - 1, sy - 1, sliceSize + 2, sliceSize + 2); }
                }
            } else if (s === 1) {
                // Encoder funnel
                ctx.fillStyle = bgBlock; ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(sx, padY); ctx.lineTo(sx + colW, padY + (H - padY * 2) * 0.2);
                ctx.lineTo(sx + colW, padY + (H - padY * 2) * 0.8); ctx.lineTo(sx, H - padY - 20);
                ctx.closePath(); ctx.fill(); ctx.stroke();
                ctx.fillStyle = mauveCol; ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif'; ctx.textAlign = 'center';
                ctx.fillText('Encoder', sx + colW / 2, midY - 2);
                ctx.fillStyle = textCol; ctx.font = monoSize + 'px JetBrains Mono, monospace';
                ctx.fillText('f(xᵢⱼ)', sx + colW / 2, midY + 14);
            } else if (s === 2) {
                // Embeddings
                for (var i = 0; i < NUM_SLICES; i++) {
                    var vy = padY + rowH * i + rowH * 0.15;
                    var vh = rowH * 0.7;
                    drawRoundedRect(sx, vy, colW, vh, 4);
                    ctx.fillStyle = bgBlock; ctx.fill();
                    ctx.strokeStyle = (i === 3) ? redCol : borderCol; ctx.lineWidth = (i === 3) ? 1.5 : 1; ctx.stroke();
                    ctx.fillStyle = (i === 3) ? redCol : blueCol;
                    ctx.font = monoSize + 'px JetBrains Mono, monospace'; ctx.textAlign = 'center';
                    ctx.fillText(formatVecShort(embeddings[i]), sx + colW / 2, vy + vh / 2 + 3);
                }
            } else if (s === 3) {
                // Mean pool funnel
                ctx.fillStyle = bgBlock; ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.moveTo(sx, padY); ctx.lineTo(sx + colW, midY - 14);
                ctx.lineTo(sx + colW, midY + 14); ctx.lineTo(sx, H - padY - 20);
                ctx.closePath(); ctx.fill(); ctx.stroke();
                ctx.fillStyle = greenCol; ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif'; ctx.textAlign = 'center';
                ctx.fillText('Mean', sx + colW / 2, midY - 1);
                ctx.fillText('Pool', sx + colW / 2, midY + 13);
            } else if (s === 4) {
                // Bag vector
                var mvH = 32;
                drawRoundedRect(sx, midY - mvH / 2, colW, mvH, 5);
                ctx.fillStyle = bgBlock; ctx.fill();
                ctx.strokeStyle = mauveCol; ctx.lineWidth = 2; ctx.stroke();
                ctx.fillStyle = mauveCol; ctx.font = 'bold ' + monoSize + 'px JetBrains Mono, monospace'; ctx.textAlign = 'center';
                ctx.fillText(formatVecShort(computeMean()), sx + colW / 2, midY + 4);
            } else if (s === 5) {
                // Classifier
                var bh = 40;
                drawRoundedRect(sx, midY - bh / 2, colW, bh, 5);
                ctx.fillStyle = bgBlock; ctx.fill();
                ctx.strokeStyle = borderCol; ctx.lineWidth = 1.5; ctx.stroke();
                ctx.fillStyle = accentCol; ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif'; ctx.textAlign = 'center';
                ctx.fillText('g(z)', sx + colW / 2, midY + 5);
            } else if (s === 6) {
                // Output
                var bw = Math.min(colW * 0.8, 55); var bh = 28;
                drawRoundedRect(sx + (colW - bw) / 2, midY - bh / 2, bw, bh, 6);
                ctx.fillStyle = redCol; ctx.fill();
                ctx.fillStyle = '#fff'; ctx.font = 'bold ' + fontSize + 'px Inter, sans-serif'; ctx.textAlign = 'center';
                ctx.fillText('Y=1', sx + colW / 2, midY + 5);
            }

            // Label
            ctx.globalAlpha = alpha;
            ctx.fillStyle = textCol; ctx.font = '600 ' + labelSize + 'px Inter, sans-serif'; ctx.textAlign = 'center';
            ctx.fillText(stageNames[s], sx + colW / 2, H - 6);

            // Arrow to next
            if (si < 2) {
                var aAlpha = Math.min(1, Math.max(0, (wt * 3 - (si + 0.3) * 0.5) * 1.5)) * 0.5;
                drawArrowLine(sx + colW + 2, midY, sx + colW + gap - 2, midY, borderCol, aAlpha);
            }

            ctx.globalAlpha = 1;
        }

        // Progress dots
        for (var d = 0; d < 3; d++) {
            ctx.beginPath(); ctx.arc(W / 2 + (d - 1) * 14, H - 16, 3, 0, Math.PI * 2);
            ctx.fillStyle = d === windowIdx ? getCtp('lavender') : borderCol; ctx.fill();
        }
    }

    function formatVecShort(v) {
        return '[' + v.map(function(n) { return n.toFixed(1); }).join(', ') + ']';
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
