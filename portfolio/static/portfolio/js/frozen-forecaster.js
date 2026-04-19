/* The Frozen Forecaster — TabICL vs XGBoost decision-boundary explorable.
 *
 * Single wide canvas. A vertical divider splits it: the LEFT half renders
 * TabICL's smooth Bayesian posterior, the RIGHT half renders XGBoost's
 * crisp 1-NN-like splits. Drag the divider to sweep the comparison across
 * the same scene.
 *
 * Why one canvas: the whole point of the demo is the contrast — making it
 * physical (one drag) reads stronger than two side-by-side panels, and it
 * halves the vertical footprint so the entire explorable fits above the fold.
 *
 * Stand-in classifiers (TabICL ≈ Gaussian KDE, XGBoost ≈ 1-NN) ship with the
 * page; a real precomputed TabICL grid drops in via the same evalGrid('tabicl')
 * interface — the renderer doesn't care.
 */
(function () {
    var root = document.getElementById('frozen-forecaster');
    if (!root) return;

    // ── Config ──────────────────────────────────────────────────────────
    // GRID matches the cached tile resolution from build_frozen_forecaster.py
    // (configs.json.tile_size). Canvas upscale handles the visual smoothing.
    var GRID = 64;
    var K_NEIGHBORS = 4;                      // K-NN for cached-config blend
    var DATA_URL = '/static/portfolio/data/frozen-forecaster/';
    var DOMAIN = { x0: -3, x1: 3, y0: -3, y1: 3 };
    var KDE_BANDWIDTH = 0.55;                 // fallback only; used until atlas loads
    var KDE_PRIOR = 0.05;
    var POINT_RADIUS = 7;
    var COLOR_A = [255, 199, 92];             // amber — class 0
    var COLOR_B = [111, 168, 255];            // accent blue — class 1
    var BG_DARK = [12, 22, 36];

    // ── State ───────────────────────────────────────────────────────────
    var points = [];
    var activeClass = 0;
    var probe = { x: 0.0, y: 0.0 };
    var dragging = null;                      // 'point' | 'probe' | 'divider'
    var dragIdx = -1;
    var splitFrac = 0.5;                      // divider position as fraction of canvas width

    // ── Cached-model lookup state (populated lazily after page load) ────
    // ffData is null until the atlas + configs.json load. Until then, we fall
    // back to the KDE/1-NN stand-ins so the demo is interactive on first paint.
    var ffData = null;
    var ffLastLookup = null;  // {nearestDist, K, N} for the fidelity readout

    // ── DOM ─────────────────────────────────────────────────────────────
    var canvas = document.getElementById('ff-canvas');
    var wrap = document.getElementById('ff-canvas-wrap');
    var divider = document.getElementById('ff-divider');
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';

    // ── Coord helpers ───────────────────────────────────────────────────
    function pxToDomain(px, py) {
        var r = canvas.getBoundingClientRect();
        var nx = (px - r.left) / r.width;
        var ny = (py - r.top) / r.height;
        return {
            x: DOMAIN.x0 + nx * (DOMAIN.x1 - DOMAIN.x0),
            y: DOMAIN.y1 - ny * (DOMAIN.y1 - DOMAIN.y0),
        };
    }
    function domainToCanvas(dx, dy) {
        var nx = (dx - DOMAIN.x0) / (DOMAIN.x1 - DOMAIN.x0);
        var ny = (DOMAIN.y1 - dy) / (DOMAIN.y1 - DOMAIN.y0);
        return { x: nx * canvas.width, y: ny * canvas.height };
    }

    // ── Classifiers (stand-ins; identical interface to a real precomputed grid) ──
    function kdeProb(x, y) {
        if (points.length === 0) return { p: 0.5, conf: 0 };
        var s0 = 0, s1 = 0;
        var h2 = 2 * KDE_BANDWIDTH * KDE_BANDWIDTH;
        for (var i = 0; i < points.length; i++) {
            var p = points[i];
            var d2 = (p.x - x) * (p.x - x) + (p.y - y) * (p.y - y);
            var w = Math.exp(-d2 / h2);
            if (p.c === 0) s0 += w; else s1 += w;
        }
        var total = s0 + s1;
        var p1 = (s1 + KDE_PRIOR) / (total + 2 * KDE_PRIOR);
        var conf = 1 - Math.exp(-total * 1.5);
        return { p: p1, conf: conf };
    }
    function nnProb(x, y) {
        if (points.length === 0) return { p: 0.5, conf: 0 };
        var bestD = Infinity, bestC = 0;
        for (var i = 0; i < points.length; i++) {
            var p = points[i];
            var d = (p.x - x) * (p.x - x) + (p.y - y) * (p.y - y);
            if (d < bestD) { bestD = d; bestC = p.c; }
        }
        return { p: bestC === 1 ? 1 : 0, conf: 1 };
    }
    function evalGridFallback(kind, out) {
        // KDE / 1-NN stand-in used until the cached atlas finishes loading.
        var fn = kind === 'tabicl' ? kdeProb : nnProb;
        var idx = 0;
        for (var j = 0; j < GRID; j++) {
            var dy = DOMAIN.y1 - (j + 0.5) / GRID * (DOMAIN.y1 - DOMAIN.y0);
            for (var i = 0; i < GRID; i++) {
                var dx = DOMAIN.x0 + (i + 0.5) / GRID * (DOMAIN.x1 - DOMAIN.x0);
                var r = fn(dx, dy);
                out[idx++] = r.p;
                out[idx++] = r.conf;
            }
        }
    }

    // ── Cached lookup: feature vector + K-NN + IDW blend ───────────────
    // Mirrors compute_features() in scripts/build_frozen_forecaster.py.
    // If you change one, change both — the lookup falls apart silently otherwise.
    function computeFeaturesJS(pts) {
        var n = pts.length;
        if (n === 0) return null;
        var n1 = 0;
        for (var i = 0; i < n; i++) if (pts[i].c === 1) n1++;
        var balance = n1 / n;
        var mx = 0, my = 0;
        for (var i = 0; i < n; i++) { mx += pts[i].x; my += pts[i].y; }
        mx /= n; my /= n;
        var vx = 0, vy = 0;
        for (var i = 0; i < n; i++) {
            vx += (pts[i].x - mx) * (pts[i].x - mx);
            vy += (pts[i].y - my) * (pts[i].y - my);
        }
        vx = Math.sqrt(vx / n) + 1e-6; vy = Math.sqrt(vy / n) + 1e-6;
        var c0x = 0, c0y = 0, c1x = 0, c1y = 0, n0c = 0, n1c = 0;
        for (var i = 0; i < n; i++) {
            if (pts[i].c === 0) { c0x += pts[i].x; c0y += pts[i].y; n0c++; }
            else { c1x += pts[i].x; c1y += pts[i].y; n1c++; }
        }
        if (n0c) { c0x /= n0c; c0y /= n0c; } else { c0x = mx; c0y = my; }
        if (n1c) { c1x /= n1c; c1y /= n1c; } else { c1x = mx; c1y = my; }
        var sep = Math.hypot(c1x - c0x, c1y - c0y);
        var mix = 0;
        if (n >= 2) {
            for (var i = 0; i < n; i++) {
                var bestD = Infinity, bestC = -1;
                for (var j = 0; j < n; j++) {
                    if (i === j) continue;
                    var dd = (pts[i].x - pts[j].x) * (pts[i].x - pts[j].x)
                           + (pts[i].y - pts[j].y) * (pts[i].y - pts[j].y);
                    if (dd < bestD) { bestD = dd; bestC = pts[j].c; }
                }
                if (bestC !== pts[i].c) mix++;
            }
            mix /= n;
        }
        var aspect = Math.min(vx / vy, vy / vx);
        return new Float32Array([
            Math.min(n / 100, 1),
            balance,
            mx / 3, my / 3,
            vx / 3, vy / 3,
            sep / 6,
            mix,
            aspect,
        ]);
    }

    function findKNearest(query, features, N, dim, K) {
        // Linear scan: 2000 × 9 = 18K floats; <0.5 ms in practice.
        var dists = new Float32Array(N);
        for (var k = 0; k < N; k++) {
            var d = 0;
            for (var i = 0; i < dim; i++) {
                var diff = query[i] - features[k * dim + i];
                d += diff * diff;
            }
            dists[k] = d;
        }
        // Partial sort — find K smallest by repeated min-pass.
        var idxs = new Array(K), used = new Uint8Array(N);
        var actualK = Math.min(K, N);
        for (var i = 0; i < actualK; i++) {
            var bestD = Infinity, bestIdx = -1;
            for (var k = 0; k < N; k++) {
                if (!used[k] && dists[k] < bestD) { bestD = dists[k]; bestIdx = k; }
            }
            used[bestIdx] = 1;
            idxs[i] = bestIdx;
        }
        // IDW weights (epsilon avoids inf when query exactly matches a cached config).
        var weights = new Float32Array(actualK);
        var sum = 0;
        for (var i = 0; i < actualK; i++) {
            weights[i] = 1 / (Math.sqrt(dists[idxs[i]]) + 0.02);
            sum += weights[i];
        }
        for (var i = 0; i < actualK; i++) weights[i] /= sum;
        ffLastLookup = { nearestDist: Math.sqrt(dists[idxs[0]]), K: actualK, N: N };
        return { idxs: idxs.slice(0, actualK), weights: weights };
    }

    function blendChannel(tileBuf, idxs, weights, G, channel) {
        // channel: 0 = TabICL (R), 1 = XGBoost (G).
        var out = new Float32Array(G * G);
        var stride = G * G * 2;
        for (var i = 0; i < idxs.length; i++) {
            var w = weights[i];
            var base = idxs[i] * stride + channel;
            for (var p = 0; p < G * G; p++) {
                out[p] += (tileBuf[base + p * 2] / 255) * w;
            }
        }
        return out;
    }

    function evalGridLookup(kind, out) {
        var feat = computeFeaturesJS(points);
        if (!feat) {
            // No points → uniform 0.5 (max entropy). Reset fidelity readout.
            ffLastLookup = null;
            for (var i = 0; i < GRID * GRID; i++) {
                out[i * 2] = 0.5;
                out[i * 2 + 1] = 0;
            }
            return;
        }
        var nn = findKNearest(feat, ffData.features, ffData.N, ffData.dim, K_NEIGHBORS);
        var channel = kind === 'tabicl' ? 0 : 1;
        var blended = blendChannel(ffData.tileBuf, nn.idxs, nn.weights, ffData.G, channel);
        // Pack into the [p, conf] interleaved layout the renderer expects.
        // For real outputs, conf is derived from |p - 0.5| so the renderer's
        // "fade to navy when uncertain" logic still produces the right look.
        for (var i = 0; i < GRID * GRID; i++) {
            var p = blended[i];
            out[i * 2] = p;
            out[i * 2 + 1] = Math.min(1, Math.abs(p - 0.5) * 2 + 0.05);
        }
    }

    function evalGrid(kind, out) {
        if (ffData) evalGridLookup(kind, out);
        else evalGridFallback(kind, out);
    }

    // ── Async loader for the precomputed atlas ─────────────────────────
    function loadImageData(url) {
        return new Promise(function (resolve, reject) {
            var img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = function () {
                var c = document.createElement('canvas');
                c.width = img.naturalWidth; c.height = img.naturalHeight;
                var cx = c.getContext('2d');
                cx.drawImage(img, 0, 0);
                resolve(cx.getImageData(0, 0, c.width, c.height));
            };
            img.onerror = reject;
            img.src = url;
        });
    }

    function loadFFData() {
        return Promise.all([
            fetch(DATA_URL + 'configs.json').then(function (r) {
                if (!r.ok) throw new Error('configs.json HTTP ' + r.status);
                return r.json();
            }),
            loadImageData(DATA_URL + 'atlas.png'),
        ]).then(function (parts) {
            var meta = parts[0], atlas = parts[1];
            var N = meta.n_configs, G = meta.tile_size, C = meta.atlas_cols;
            // Decode tiles into a packed Uint8Array(N * G * G * 2) — only the
            // R + G channels, since B is reserved/unused. ~16 MB at full N=2000.
            var tileBuf = new Uint8Array(N * G * G * 2);
            var aData = atlas.data, aW = atlas.width;
            for (var k = 0; k < N; k++) {
                var ci = k % C, cj = Math.floor(k / C);
                var x0 = ci * G, y0 = cj * G;
                for (var j = 0; j < G; j++) {
                    var aRow = (y0 + j) * aW;
                    for (var i = 0; i < G; i++) {
                        var aIdx = (aRow + x0 + i) * 4;
                        var tIdx = (k * G * G + j * G + i) * 2;
                        tileBuf[tIdx] = aData[aIdx];
                        tileBuf[tIdx + 1] = aData[aIdx + 1];
                    }
                }
            }
            // Feature matrix: N × dim Float32Array
            var dim = meta.feature_dim;
            var features = new Float32Array(N * dim);
            for (var k = 0; k < N; k++) {
                var f = meta.configs[k].f;
                for (var d = 0; d < dim; d++) features[k * dim + d] = f[d];
            }
            ffData = { meta: meta, tileBuf: tileBuf, features: features, N: N, G: G, dim: dim };
            // Re-render with real outputs now that the cache is hot.
            rerender();
        }).catch(function (err) {
            console.warn('[ff] cache load failed; staying on KDE fallback —', err.message);
        });
    }

    // ── Render ──────────────────────────────────────────────────────────
    var gridT = new Float32Array(GRID * GRID * 2);
    var gridX = new Float32Array(GRID * GRID * 2);
    var offT = document.createElement('canvas');
    var offX = document.createElement('canvas');
    offT.width = offX.width = GRID;
    offT.height = offX.height = GRID;
    var offCtxT = offT.getContext('2d');
    var offCtxX = offX.getContext('2d');
    var imgDataT = offCtxT.createImageData(GRID, GRID);
    var imgDataX = offCtxX.createImageData(GRID, GRID);

    function lerp(a, b, t) { return a + (b - a) * t; }
    function paintGrid(grid, imgData, ctxOff) {
        var d = imgData.data;
        var src = 0, dst = 0;
        for (var k = 0; k < GRID * GRID; k++) {
            var p1 = grid[src++], conf = grid[src++];
            var r = lerp(COLOR_A[0], COLOR_B[0], p1);
            var g = lerp(COLOR_A[1], COLOR_B[1], p1);
            var b = lerp(COLOR_A[2], COLOR_B[2], p1);
            // Blend toward backdrop by (1 - conf) so low-conf reads as dim navy.
            var alpha = 0.22 + 0.62 * conf;
            r = lerp(BG_DARK[0], r, alpha);
            g = lerp(BG_DARK[1], g, alpha);
            b = lerp(BG_DARK[2], b, alpha);
            d[dst++] = r | 0; d[dst++] = g | 0; d[dst++] = b | 0; d[dst++] = 255;
        }
        ctxOff.putImageData(imgData, 0, 0);
    }
    function drawDecisionLine(grid) {
        // Marching-squares-lite at p=0.5 — straddling cells get a thin rect outline.
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.34)';
        ctx.lineWidth = 1;
        var w = canvas.width / GRID, h = canvas.height / GRID;
        for (var j = 0; j < GRID - 1; j++) {
            for (var i = 0; i < GRID - 1; i++) {
                var idx = (j * GRID + i) * 2;
                var p00 = grid[idx];
                var p10 = grid[idx + 2];
                var p01 = grid[((j + 1) * GRID + i) * 2];
                var min = Math.min(p00, p10, p01);
                var max = Math.max(p00, p10, p01);
                if (min < 0.5 && max >= 0.5) {
                    ctx.strokeRect(i * w, j * h, w, h);
                }
            }
        }
    }
    function render() {
        var w = canvas.width, h = canvas.height;
        var splitX = Math.round(w * splitFrac);

        // Backdrop
        ctx.fillStyle = 'rgb(' + BG_DARK.join(',') + ')';
        ctx.fillRect(0, 0, w, h);

        // Paint surfaces
        paintGrid(gridT, imgDataT, offCtxT);
        paintGrid(gridX, imgDataX, offCtxX);

        // Left half: TabICL (clipped, full-canvas upscale)
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, splitX, h);
        ctx.clip();
        ctx.drawImage(offT, 0, 0, GRID, GRID, 0, 0, w, h);
        drawDecisionLine(gridT);
        ctx.restore();

        // Right half: XGBoost
        ctx.save();
        ctx.beginPath();
        ctx.rect(splitX, 0, w - splitX, h);
        ctx.clip();
        ctx.drawImage(offX, 0, 0, GRID, GRID, 0, 0, w, h);
        drawDecisionLine(gridX);
        ctx.restore();

        // Soft contrast wash near divider so eye finds it
        var grad = ctx.createLinearGradient(splitX - 24, 0, splitX + 24, 0);
        grad.addColorStop(0, 'rgba(0, 0, 0, 0)');
        grad.addColorStop(0.5, 'rgba(0, 0, 0, 0.22)');
        grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = grad;
        ctx.fillRect(splitX - 24, 0, 48, h);

        // Points
        for (var i = 0; i < points.length; i++) {
            var p = points[i];
            var pos = domainToCanvas(p.x, p.y);
            var col = p.c === 0 ? COLOR_A : COLOR_B;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
            ctx.fillStyle = 'rgb(' + col.join(',') + ')';
            ctx.fill();
            ctx.strokeStyle = 'rgba(8, 16, 28, 0.92)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Probe (white ring + dot)
        var ppos = domainToCanvas(probe.x, probe.y);
        ctx.beginPath();
        ctx.arc(ppos.x, ppos.y, 11, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(ppos.x, ppos.y, 3, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.95)';
        ctx.fill();

        // Sync DOM divider position
        divider.style.left = (splitFrac * 100) + '%';
    }

    // ── Probe readout ───────────────────────────────────────────────────
    var barTA = document.getElementById('ff-bar-tabicl-a');
    var barTB = document.getElementById('ff-bar-tabicl-b');
    var barXA = document.getElementById('ff-bar-xgb-a');
    var barXB = document.getElementById('ff-bar-xgb-b');
    var numT = document.getElementById('ff-num-tabicl');
    var numX = document.getElementById('ff-num-xgb');
    function probeFromGrid(grid) {
        // Sample p at the probe's domain coords by indexing into the rendered grid.
        // Works for both lookup and fallback paths since both populate gridT/gridX.
        var nx = (probe.x - DOMAIN.x0) / (DOMAIN.x1 - DOMAIN.x0);
        var ny = (DOMAIN.y1 - probe.y) / (DOMAIN.y1 - DOMAIN.y0);
        var i = Math.min(GRID - 1, Math.max(0, Math.floor(nx * GRID)));
        var j = Math.min(GRID - 1, Math.max(0, Math.floor(ny * GRID)));
        return grid[(j * GRID + i) * 2];
    }
    function updateProbeReadout() {
        var pT = probeFromGrid(gridT);
        var pX = probeFromGrid(gridX);
        barTA.style.width = ((1 - pT) * 100) + '%';
        barTB.style.width = (pT * 100) + '%';
        barXA.style.width = ((1 - pX) * 100) + '%';
        barXB.style.width = (pX * 100) + '%';
        var winT = Math.max(pT, 1 - pT);
        var winX = Math.max(pX, 1 - pX);
        var entropy = (pT > 0 && pT < 1) ? -(pT * Math.log2(pT) + (1 - pT) * Math.log2(1 - pT)) : 0;
        var entLabel = entropy > 0.85 ? ' · uncertain' : '';
        numT.textContent = 'P = ' + winT.toFixed(2) + entLabel;
        numX.textContent = 'P = ' + winX.toFixed(2);
    }
    var fidelityEl = document.getElementById('ff-fidelity');
    function updateFidelity() {
        if (!fidelityEl) return;
        if (!ffData) {
            fidelityEl.textContent = 'Loading real precomputed outputs…';
            fidelityEl.classList.add('ff-fidelity--loading');
            return;
        }
        fidelityEl.classList.remove('ff-fidelity--loading');
        if (ffLastLookup) {
            var d = ffLastLookup.nearestDist;
            var quality = d < 0.15 ? 'close match' : d < 0.4 ? 'rough match' : 'distant match';
            fidelityEl.textContent = 'Surface interpolated from K=' + ffLastLookup.K +
                ' of ' + ffLastLookup.N + ' real cached scenes · ' + quality + ' (d=' + d.toFixed(2) + ').';
        } else {
            fidelityEl.textContent = 'Drop a point — the surface comes from K-NN over ' +
                ffData.N + ' real precomputed scenes.';
        }
    }

    // ── Pipeline ────────────────────────────────────────────────────────
    var pendingFrame = false;
    var dirtyGrids = true;
    function rerender(opts) {
        if (opts && opts.gridsDirty === false) {
            // skip recompute (e.g. divider drag, probe drag with no point change)
        } else {
            dirtyGrids = true;
        }
        if (pendingFrame) return;
        pendingFrame = true;
        requestAnimationFrame(function () {
            if (dirtyGrids) {
                evalGrid('tabicl', gridT);
                evalGrid('xgb', gridX);
                dirtyGrids = false;
            }
            render();
            updateProbeReadout();
            updateFidelity();
            pendingFrame = false;
        });
    }

    // ── Interactions ────────────────────────────────────────────────────
    function findPointAt(evt) {
        var d = pxToDomain(evt.clientX, evt.clientY);
        var rect = canvas.getBoundingClientRect();
        var pxPerUnit = rect.width / (DOMAIN.x1 - DOMAIN.x0);
        var thresh = (POINT_RADIUS + 2) / pxPerUnit;
        for (var i = points.length - 1; i >= 0; i--) {
            var p = points[i];
            var dx = p.x - d.x, dy = p.y - d.y;
            if (dx * dx + dy * dy < thresh * thresh) return i;
        }
        return -1;
    }
    function probeHit(evt) {
        var rect = canvas.getBoundingClientRect();
        var ppos = domainToCanvas(probe.x, probe.y);
        var ppx = (evt.clientX - rect.left) - ppos.x * (rect.width / canvas.width);
        var ppy = (evt.clientY - rect.top) - ppos.y * (rect.height / canvas.height);
        return ppx * ppx + ppy * ppy < 16 * 16;
    }
    function onCanvasDown(evt) {
        evt.preventDefault();
        if (probeHit(evt)) {
            dragging = 'probe';
            return;
        }
        var idx = findPointAt(evt);
        if ((evt.button === 2 || (evt.shiftKey && idx >= 0)) && idx >= 0) {
            points.splice(idx, 1);
            rerender();
            return;
        }
        if (idx >= 0) {
            dragging = 'point'; dragIdx = idx;
            return;
        }
        var d = pxToDomain(evt.clientX, evt.clientY);
        points.push({ x: d.x, y: d.y, c: evt.shiftKey ? (1 - activeClass) : activeClass });
        dragging = 'point'; dragIdx = points.length - 1;
        rerender();
    }
    function onWindowMove(evt) {
        if (!dragging) return;
        if (dragging === 'divider') {
            var r = canvas.getBoundingClientRect();
            var f = (evt.clientX - r.left) / r.width;
            splitFrac = Math.max(0.04, Math.min(0.96, f));
            rerender({ gridsDirty: false });
            return;
        }
        var d = pxToDomain(evt.clientX, evt.clientY);
        d.x = Math.max(DOMAIN.x0, Math.min(DOMAIN.x1, d.x));
        d.y = Math.max(DOMAIN.y0, Math.min(DOMAIN.y1, d.y));
        if (dragging === 'probe') {
            probe.x = d.x; probe.y = d.y;
            rerender({ gridsDirty: false });
        } else {
            points[dragIdx].x = d.x;
            points[dragIdx].y = d.y;
            rerender();
        }
    }
    function onWindowUp() { dragging = null; dragIdx = -1; }

    canvas.addEventListener('mousedown', onCanvasDown);
    canvas.addEventListener('contextmenu', function (e) { e.preventDefault(); });
    divider.addEventListener('mousedown', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dragging = 'divider';
    });
    window.addEventListener('mousemove', onWindowMove);
    window.addEventListener('mouseup', onWindowUp);
    document.addEventListener('keydown', function (e) {
        if (document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
        if (e.key === '1') activeClass = 0;
        else if (e.key === '2') activeClass = 1;
    });

    // Touch support — single-finger drag for divider/probe/points.
    function touchToMouse(evt) {
        if (!evt.touches.length) return null;
        var t = evt.touches[0];
        return { clientX: t.clientX, clientY: t.clientY, button: 0, shiftKey: false, preventDefault: function () { evt.preventDefault(); } };
    }
    canvas.addEventListener('touchstart', function (e) { var m = touchToMouse(e); if (m) { e.preventDefault(); onCanvasDown(m); } }, { passive: false });
    divider.addEventListener('touchstart', function (e) { e.preventDefault(); e.stopPropagation(); dragging = 'divider'; }, { passive: false });
    window.addEventListener('touchmove', function (e) { var m = touchToMouse(e); if (m && dragging) { e.preventDefault(); onWindowMove(m); } }, { passive: false });
    window.addEventListener('touchend', onWindowUp);

    // ── Presets ─────────────────────────────────────────────────────────
    function preset(kind) {
        points = [];
        if (kind === 'moons') {
            for (var i = 0; i < 14; i++) {
                var t = Math.PI * (i / 13);
                points.push({ x: 1.4 * Math.cos(t) - 0.5, y: 1.4 * Math.sin(t) - 0.4, c: 0 });
                points.push({ x: 1.4 * Math.cos(t + Math.PI) + 0.5, y: 1.4 * Math.sin(t + Math.PI) + 0.4, c: 1 });
            }
        } else if (kind === 'circles') {
            for (var i = 0; i < 16; i++) {
                var t = 2 * Math.PI * (i / 16);
                points.push({ x: 0.7 * Math.cos(t), y: 0.7 * Math.sin(t), c: 0 });
                points.push({ x: 1.8 * Math.cos(t), y: 1.8 * Math.sin(t), c: 1 });
            }
        } else if (kind === 'xor') {
            for (var qx = -1; qx <= 1; qx += 2) for (var qy = -1; qy <= 1; qy += 2) {
                for (var k = 0; k < 4; k++) {
                    var jx = qx * 1.2 + (Math.random() - 0.5) * 0.6;
                    var jy = qy * 1.2 + (Math.random() - 0.5) * 0.6;
                    points.push({ x: jx, y: jy, c: (qx * qy > 0) ? 0 : 1 });
                }
            }
        } else if (kind === 'blobs') {
            var centers = [[-1.4, 1.0, 0], [1.4, 1.0, 0], [-1.4, -1.0, 1], [1.4, -1.0, 1]];
            for (var i = 0; i < centers.length; i++) {
                for (var k = 0; k < 6; k++) {
                    points.push({
                        x: centers[i][0] + (Math.random() - 0.5) * 0.7,
                        y: centers[i][1] + (Math.random() - 0.5) * 0.7,
                        c: centers[i][2],
                    });
                }
            }
        } else if (kind === 'outlier') {
            for (var k = 0; k < 4; k++) {
                points.push({ x: -1.5 + (Math.random() - 0.5) * 0.4, y: 1.5 + (Math.random() - 0.5) * 0.4, c: 0 });
                points.push({ x: 1.5 + (Math.random() - 0.5) * 0.4, y: -1.5 + (Math.random() - 0.5) * 0.4, c: 1 });
            }
            probe.x = 2.4; probe.y = 2.4;
        }
        rerender();
    }
    root.querySelectorAll('.ff-preset').forEach(function (b) {
        b.addEventListener('click', function () {
            root.querySelectorAll('.ff-preset').forEach(function (x) { x.classList.remove('active'); });
            if (b.dataset.preset !== 'clear') b.classList.add('active');
            preset(b.dataset.preset);
        });
    });

    // ── Boot ────────────────────────────────────────────────────────────
    var moonsBtn = root.querySelector('.ff-preset[data-preset="moons"]');
    if (moonsBtn) moonsBtn.classList.add('active');
    preset('moons');
    // Lazy-load the cached real-model atlas only when the user scrolls within
    // 500 px of the demo. Saves a 5 MB download for visitors who never reach
    // #demos. evalGrid() stays on the KDE/1-NN fallback until the atlas hydrates.
    if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
            if (entries[0].isIntersecting) {
                observer.disconnect();
                loadFFData();
            }
        }, { rootMargin: '500px 0px' });
        observer.observe(root);
    } else {
        setTimeout(loadFFData, 500);
    }
})();
