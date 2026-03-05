let pipeline = null;
let pipelineLoading = false;

const dropZone = document.getElementById('depth-drop-zone');
const fileInput = document.getElementById('depth-file-input');
const depthStatus = document.getElementById('depth-status');
const depthSpinner = document.getElementById('depth-spinner');
const comparisonContainer = document.getElementById('depth-comparison');
const originalCanvas = document.getElementById('depth-original');
const depthCanvas = document.getElementById('depth-result');
const sliderHandle = document.getElementById('depth-slider-handle');
const depthOverlay = document.getElementById('depth-overlay');

if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) processImage(file);
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) processImage(file);
    });
}

async function loadPipeline() {
    if (pipeline) return pipeline;
    if (pipelineLoading) {
        while (pipelineLoading) await new Promise(r => setTimeout(r, 100));
        return pipeline;
    }
    pipelineLoading = true;
    showStatus('Loading depth model (~27 MB)...');
    const { pipeline: createPipeline } = await import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@3');
    pipeline = await createPipeline('depth-estimation', 'onnx-community/depth-anything-v2-small', {
        dtype: 'q8',
        device: 'wasm',
    });
    pipelineLoading = false;
    return pipeline;
}

function showStatus(text) {
    if (depthStatus) depthStatus.textContent = text;
    if (depthSpinner) depthSpinner.style.display = 'flex';
}

function hideStatus() {
    if (depthSpinner) depthSpinner.style.display = 'none';
    if (depthStatus) depthStatus.textContent = '';
}

async function processImage(file) {
    showStatus('Loading depth model (~27 MB)...');
    if (comparisonContainer) comparisonContainer.style.display = 'none';

    // Use createImageBitmap to handle EXIF rotation correctly
    const bitmap = await createImageBitmap(file);
    const imgW = bitmap.width;
    const imgH = bitmap.height;

    // Scale to fit the card
    const cardWidth = comparisonContainer.parentElement.clientWidth
        - 2 * parseInt(getComputedStyle(comparisonContainer.parentElement).paddingLeft || '24');
    const maxW = Math.max(cardWidth, 200);
    const scale = Math.min(1, maxW / imgW);
    const w = Math.round(imgW * scale);
    const h = Math.round(imgH * scale);

    // Draw original (EXIF-corrected) onto the original canvas
    originalCanvas.width = w;
    originalCanvas.height = h;
    depthCanvas.width = w;
    depthCanvas.height = h;
    const ctx = originalCanvas.getContext('2d');
    ctx.drawImage(bitmap, 0, 0, w, h);

    // Create a corrected blob to pass to the pipeline (avoids EXIF issues)
    const inputCanvas = document.createElement('canvas');
    inputCanvas.width = imgW;
    inputCanvas.height = imgH;
    inputCanvas.getContext('2d').drawImage(bitmap, 0, 0);
    bitmap.close();

    try {
        const pipe = await loadPipeline();
        showStatus('Running depth estimation...');

        // Pass the EXIF-corrected canvas as a blob URL
        const inputBlob = await new Promise(r => inputCanvas.toBlob(r));
        const inputUrl = URL.createObjectURL(inputBlob);

        const result = await pipe(inputUrl);
        URL.revokeObjectURL(inputUrl);
        const depthImage = result.depth;

        const dCtx = depthCanvas.getContext('2d');
        const depthImg = new Image();
        const blob = await depthImage.toBlob();
        const depthUrl = URL.createObjectURL(blob);
        depthImg.onload = () => {
            dCtx.drawImage(depthImg, 0, 0, w, h);
            URL.revokeObjectURL(depthUrl);

            // Size comparison container to match image
            comparisonContainer.style.display = 'block';
            comparisonContainer.style.width = w + 'px';
            comparisonContainer.style.height = h + 'px';
            depthCanvas.style.width = w + 'px';
            depthCanvas.style.height = h + 'px';
            originalCanvas.style.width = w + 'px';
            originalCanvas.style.height = h + 'px';

            if (depthOverlay) depthOverlay.style.width = '50%';
            hideStatus();
        };
        depthImg.src = depthUrl;
    } catch (err) {
        console.error(err);
        showStatus('Error: ' + err.message);
        if (depthSpinner) depthSpinner.style.display = 'none';
    }
}

// Slider interaction
if (comparisonContainer && sliderHandle) {
    let dragging = false;

    const updateSlider = (clientX) => {
        const rect = comparisonContainer.getBoundingClientRect();
        let x = clientX - rect.left;
        x = Math.max(0, Math.min(x, rect.width));
        const pct = (x / rect.width) * 100;
        if (depthOverlay) depthOverlay.style.width = pct + '%';
    };

    comparisonContainer.addEventListener('mousedown', (e) => {
        dragging = true;
        updateSlider(e.clientX);
    });
    comparisonContainer.addEventListener('touchstart', (e) => {
        dragging = true;
        updateSlider(e.touches[0].clientX);
    }, { passive: true });

    document.addEventListener('mousemove', (e) => {
        if (dragging) updateSlider(e.clientX);
    });
    document.addEventListener('touchmove', (e) => {
        if (dragging) updateSlider(e.touches[0].clientX);
    }, { passive: true });

    document.addEventListener('mouseup', () => { dragging = false; });
    document.addEventListener('touchend', () => { dragging = false; });
}
