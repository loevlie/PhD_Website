/**
 * Three.js Brain Axial Slice Visualization
 * Loads pre-generated brain slice textures and stacks them.
 * Animates spreading apart to show MIL bag decomposition.
 */
import * as THREE from 'three';

(function() {
    var container = document.getElementById('brain-slice-demo');
    if (!container) return;

    var width = Math.min(container.clientWidth, 500);
    var height = Math.min(width * 0.85, 420);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(30, width / height, 0.1, 100);
    camera.position.set(0, 2.8, 5);
    camera.lookAt(0, 0.2, 0);

    var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);
    renderer.domElement.style.borderRadius = '8px';

    scene.add(new THREE.AmbientLight(0xffffff, 1.0));

    var NUM_SLICES = 14;
    var SLICE_GAP = 0.1;
    var POSITIVE_IDX = 10;
    var slices = [];
    var sliceGroup = new THREE.Group();
    var loader = new THREE.TextureLoader();
    var loaded = 0;

    // Brain size envelope (smaller at bottom/top)
    function sliceScale(i) {
        var t = (i + 0.5) / NUM_SLICES;
        return 0.4 + Math.sin(t * Math.PI) * 0.9;
    }

    for (var i = 0; i < NUM_SLICES; i++) {
        (function(idx) {
            var padded = idx < 10 ? '0' + idx : '' + idx;
            var url = '/static/portfolio/images/blog/brain/slice_' + padded + '.png';

            loader.load(url, function(texture) {
                texture.minFilter = THREE.LinearFilter;
                texture.magFilter = THREE.LinearFilter;

                var scale = sliceScale(idx);
                var geo = new THREE.PlaneGeometry(scale, scale);
                var mat = new THREE.MeshBasicMaterial({
                    map: texture,
                    transparent: true,
                    side: THREE.DoubleSide,
                    alphaTest: 0.05,
                    depthWrite: true,
                });

                var mesh = new THREE.Mesh(geo, mat);
                mesh.rotation.x = -Math.PI / 2;
                mesh.position.y = idx * SLICE_GAP;
                mesh.userData = { index: idx, positive: idx === POSITIVE_IDX, baseY: idx * SLICE_GAP };

                slices[idx] = mesh;
                sliceGroup.add(mesh);

                loaded++;
                if (loaded === NUM_SLICES) startAnimation();
            });
        })(i);
    }

    var totalHeight = (NUM_SLICES - 1) * SLICE_GAP;
    sliceGroup.position.y = -totalHeight / 2;
    scene.add(sliceGroup);

    // Arrow — positioned next to the brain stack
    var arrowX = -0.9;
    var arrowBottom = -totalHeight / 2 - 0.1;
    var arrowLen = totalHeight + 0.3;
    var arrowObj = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(arrowX, arrowBottom, 0), arrowLen, 0x6c7086, 0.08, 0.06);
    scene.add(arrowObj);

    // Labels
    function makeLabel(text) {
        var c = document.createElement('canvas');
        c.width = 200; c.height = 48;
        var cx = c.getContext('2d');
        cx.font = '500 22px Inter, sans-serif';
        cx.fillStyle = '#7c7f93';
        cx.textAlign = 'center';
        cx.textBaseline = 'middle';
        cx.fillText(text, 100, 24);
        var tex = new THREE.CanvasTexture(c);
        var mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false });
        var sprite = new THREE.Sprite(mat);
        sprite.scale.set(0.65, 0.19, 1);
        return sprite;
    }

    var bottomLabel = makeLabel('Bottom');
    bottomLabel.position.set(arrowX, arrowBottom - 0.2, 0);
    scene.add(bottomLabel);

    var topLabel = makeLabel('Top');
    topLabel.position.set(arrowX, arrowBottom + arrowLen + 0.15, 0);
    scene.add(topLabel);

    // "Finding" label
    var findingLabel = makeLabel('← Finding');
    findingLabel.visible = false;
    scene.add(findingLabel);

    // Animation
    var spread = 0, targetSpread = 0, time = 0, animPhase = 0, phaseTimer = 0;
    var animStarted = false;

    function startAnimation() {
        // Sort slices by index for consistent rendering
        slices.sort(function(a, b) { return a.userData.index - b.userData.index; });
        animStarted = true;
    }

    function animate() {
        requestAnimationFrame(animate);
        if (!animStarted) { renderer.render(scene, camera); return; }

        time += 0.016;
        phaseTimer += 0.016;

        if (animPhase === 0 && phaseTimer > 2) { animPhase = 1; targetSpread = 1; phaseTimer = 0; }
        else if (animPhase === 1 && Math.abs(spread - targetSpread) < 0.01) { animPhase = 2; phaseTimer = 0; }
        else if (animPhase === 2 && phaseTimer > 4) { animPhase = 3; targetSpread = 0; phaseTimer = 0; }
        else if (animPhase === 3 && Math.abs(spread - targetSpread) < 0.01) { animPhase = 0; phaseTimer = 0; }

        spread += (targetSpread - spread) * 0.035;

        for (var i = 0; i < slices.length; i++) {
            if (!slices[i]) continue;
            var mesh = slices[i];
            var offset = (mesh.userData.index - NUM_SLICES / 2) * spread * 0.2;
            mesh.position.y = mesh.userData.baseY + offset;

            // Positive slice glow effect
            if (mesh.userData.positive && spread > 0.5) {
                mesh.material.opacity = 0.85 + Math.sin(time * 2.5) * 0.15;
            } else {
                mesh.material.opacity = 1;
            }
        }

        // Finding label
        if (spread > 0.6 && slices[POSITIVE_IDX]) {
            findingLabel.visible = true;
            findingLabel.position.set(
                1.0,
                sliceGroup.position.y + slices[POSITIVE_IDX].position.y + 0.05,
                0
            );
        } else {
            findingLabel.visible = false;
        }

        // Gentle rotation
        sliceGroup.rotation.y = Math.sin(time * 0.15) * 0.4;

        renderer.render(scene, camera);
    }
    animate();

    window.addEventListener('resize', function() {
        width = Math.min(container.clientWidth, 500);
        height = Math.min(width * 0.85, 420);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height);
    });
})();
