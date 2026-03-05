import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const canvas = document.getElementById('np-canvas');
if (canvas) {
    const container = canvas.parentElement;
    const width = container.clientWidth;
    const height = 500;
    canvas.width = width;
    canvas.height = height;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    function getSceneBg() {
        return getComputedStyle(document.documentElement).getPropertyValue('--bg-tertiary').trim() || '#243442';
    }
    scene.background = new THREE.Color(getSceneBg());

    window.addEventListener('themechange', () => {
        scene.background = new THREE.Color(getSceneBg());
    });

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 0, 14);

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.5;
    controls.enablePan = false;
    controls.minDistance = 8;
    controls.maxDistance = 22;

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const dir1 = new THREE.DirectionalLight(0xffffff, 0.9);
    dir1.position.set(5, 5, 5);
    scene.add(dir1);
    const dir2 = new THREE.DirectionalLight(0xffffff, 0.4);
    dir2.position.set(-3, -2, -4);
    scene.add(dir2);

    // ── Generate 55-atom Mackay Icosahedron ──
    // Exact geometry matching ASE's Icosahedron('Au', nshells=3).
    // Real structure has atoms at 3 distinct radii:
    //   Shell 0: r=0 (1 atom)
    //   Shell 1: r=a (12 vertex atoms)
    //   Shell 2 edges: r=a*√((5+√5)/2)·(1/φ) ≈ 1.702a (30 edge midpoints)
    //   Shell 2 verts: r=2a (12 vertex atoms)

    const phi = (1 + Math.sqrt(5)) / 2;

    // 12 icosahedral vertex unit vectors
    const rawVerts = [
        [0, 1, phi], [0, -1, phi], [0, 1, -phi], [0, -1, -phi],
        [1, phi, 0], [-1, phi, 0], [1, -phi, 0], [-1, -phi, 0],
        [phi, 0, 1], [-phi, 0, 1], [phi, 0, -1], [-phi, 0, -1]
    ];
    const vertLen = Math.sqrt(1 + phi * phi);
    const icoUnit = rawVerts.map(v => [v[0]/vertLen, v[1]/vertLen, v[2]/vertLen]);

    // Scale factor for rendering (r1 = shell 1 radius)
    const r1 = 2.0;

    // Shell 0: center
    const positions = [[0, 0, 0]];

    // Shell 1: 12 vertices at r1
    for (const u of icoUnit) {
        positions.push([u[0]*r1, u[1]*r1, u[2]*r1]);
    }

    // Shell 2: 12 vertex atoms at 2*r1 (same directions as shell 1)
    for (const u of icoUnit) {
        positions.push([u[0]*2*r1, u[1]*2*r1, u[2]*2*r1]);
    }

    // Shell 2: 30 edge midpoint atoms (sum of adjacent vertex vectors, scaled by r1)
    // These are NOT normalized — they sit at their natural radius
    const faces = [
        [0,1,8],[0,1,9],[0,4,8],[0,4,5],[0,5,9],
        [3,2,10],[3,2,11],[3,6,10],[3,6,7],[3,7,11],
        [1,6,8],[1,7,9],[2,4,10],[2,5,11],
        [8,4,10],[8,6,10],[9,5,11],[9,7,11],
        [6,1,7],[4,2,5]
    ];

    const edgeSet = new Set();
    for (const f of faces) {
        const edges = [[f[0],f[1]], [f[1],f[2]], [f[0],f[2]]];
        for (const [a,b] of edges) {
            const key = Math.min(a,b) + ',' + Math.max(a,b);
            if (edgeSet.has(key)) continue;
            edgeSet.add(key);
            // Sum of vertex vectors (not midpoint, not normalized)
            positions.push([
                (icoUnit[a][0] + icoUnit[b][0]) * r1,
                (icoUnit[a][1] + icoUnit[b][1]) * r1,
                (icoUnit[a][2] + icoUnit[b][2]) * r1
            ]);
        }
    }

    const totalAtoms = positions.length; // 55

    // ── Bond-Centric Model (BCM) for Cohesive Energy ──
    // From CANELa_NP (Loevlie et al., Acc. Chem. Res. 2023)
    const CE_BULK = { Au: -3.64, Pd: -4.20 }; // eV/atom, PBE-D3
    const GAMMAS = {
        Au: { Au: 1.0, Pd: 2.9452404114642707 },
        Pd: { Pd: 1.0, Au: -0.9452404114642707 },
    };
    const CB = 12; // bulk FCC coordination number

    function pairDist(a, b) {
        return Math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2);
    }

    // Find bond cutoff from distance gap (NN bonds cluster, then gap to 2nd NN)
    const allDists = [];
    for (let i = 0; i < totalAtoms; i++)
        for (let j = i + 1; j < totalAtoms; j++)
            allDists.push(pairDist(positions[i], positions[j]));
    allDists.sort((a, b) => a - b);

    let bondCutoff = r1 * 1.15; // fallback
    for (let k = 1; k < allDists.length; k++) {
        if (allDists[k] - allDists[k-1] > 0.3 * r1) {
            bondCutoff = (allDists[k] + allDists[k-1]) / 2;
            break;
        }
    }

    const bonds = [];
    const cn = new Array(totalAtoms).fill(0);
    for (let i = 0; i < totalAtoms; i++) {
        for (let j = i + 1; j < totalAtoms; j++) {
            if (pairDist(positions[i], positions[j]) <= bondCutoff) {
                bonds.push([i, j]);
                cn[i]++;
                cn[j]++;
            }
        }
    }

    /**
     * BCM cohesive energy (BCM_Sandbox.py formula):
     *   CE = (1/(2N)) Σ_{bonds(i,j)} [γ(A,B)·CE_bulk(A)/CN(i)·√(CN(i)/12)
     *                                 + γ(B,A)·CE_bulk(B)/CN(j)·√(CN(j)/12)]
     */
    function calcCE(symbols) {
        // BCM formula: CE = (1/2N) Σ_{directed bonds} [γ(A,B)·CE_bulk(A)/CN(i)·√(CN(i)/12) + ...]
        // Our bond list has unique (undirected) bonds; each appears once.
        // The directed sum counts each undirected bond twice with identical terms,
        // so: sum_directed = 2 * sum_undirected → CE = sum_undirected / N
        let numSum = 0;
        for (const [i, j] of bonds) {
            const A = symbols[i], B = symbols[j];
            numSum += GAMMAS[A][B] * (CE_BULK[A] / cn[i]) * Math.sqrt(cn[i] / CB)
                    + GAMMAS[B][A] * (CE_BULK[B] / cn[j]) * Math.sqrt(cn[j] / CB);
        }
        return numSum / totalAtoms;
    }

    function getSymbols(pdCoreFlag) {
        return positions.map((_, i) => {
            const isCore = i < 13;
            return pdCoreFlag ? (isCore ? 'Pd' : 'Au') : (isCore ? 'Au' : 'Pd');
        });
    }

    // ── Three.js rendering ──
    const auColor = new THREE.Color(0xFFD700);
    const pdColor = new THREE.Color(0xB0B0B0);
    const sphereGeo = new THREE.SphereGeometry(0.42, 24, 16);

    const mesh = new THREE.InstancedMesh(sphereGeo, new THREE.MeshStandardMaterial({
        metalness: 0.7,
        roughness: 0.25,
    }), totalAtoms);

    const dummy = new THREE.Object3D();
    positions.forEach((pos, i) => {
        dummy.position.set(pos[0], pos[1], pos[2]);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
    });

    let pdCore = true;
    const ceDisplay = document.getElementById('np-ce');

    function updateColors() {
        const coreColor = pdCore ? pdColor : auColor;
        const shellColor = pdCore ? auColor : pdColor;
        for (let i = 0; i < 13; i++) mesh.setColorAt(i, coreColor);
        for (let i = 13; i < totalAtoms; i++) mesh.setColorAt(i, shellColor);
        mesh.instanceColor.needsUpdate = true;

        if (ceDisplay) {
            const ce = calcCE(getSymbols(pdCore));
            const label = pdCore ? 'Pd-core / Au-shell' : 'Au-core / Pd-shell';
            ceDisplay.textContent = `${label}: CE = ${ce.toFixed(3)} eV/atom`;
        }
    }
    updateColors();
    scene.add(mesh);

    const toggleBtn = document.getElementById('np-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            pdCore = !pdCore;
            updateColors();
            toggleBtn.textContent = pdCore ? 'Swap to Au-core' : 'Swap to Pd-core';
        });
    }

    function animate() {
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    const ro = new ResizeObserver(() => {
        const w = container.clientWidth;
        renderer.setSize(w, 500);
        camera.aspect = w / 500;
        camera.updateProjectionMatrix();
    });
    ro.observe(container);
}
