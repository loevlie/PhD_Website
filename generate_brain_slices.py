"""Generate realistic-looking brain axial slice images for the Three.js demo."""
import math
import random
from PIL import Image, ImageDraw, ImageFilter

SIZE = 512
OUT_DIR = 'portfolio/static/portfolio/images/blog/brain'

random.seed(42)

def brain_shape(t, angle):
    """Return radius at angle for brain at level t (0=bottom, 1=top)."""
    # Base envelope: smaller at bottom/top, widest at ~0.45
    envelope = math.sin(t * math.pi) ** 0.8
    base_r = 0.15 + envelope * 0.33

    # Wider left-right than front-back
    lr_ratio = 1.0 + 0.15 * math.cos(angle)  # wider at sides (0 and PI)
    fb_ratio = 0.88  # narrower front-to-back

    r = base_r * (lr_ratio if abs(math.cos(angle)) > 0.3 else fb_ratio * lr_ratio)

    # Occipital bulge (back of head, angle ~ PI)
    if angle > math.pi * 0.7 and angle < math.pi * 1.3:
        r *= 1.05

    # Frontal narrowing (front, angle ~ 0 or 2PI)
    if angle < 0.3 or angle > math.pi * 1.7:
        r *= 0.92

    # Sulci (bumpy surface)
    r += 0.008 * math.sin(angle * 13 + t * 5)
    r += 0.005 * math.sin(angle * 21 + t * 8)

    return r


def draw_brain_slice(t, positive=False):
    """Draw a single axial brain slice at level t."""
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = SIZE // 2, SIZE // 2

    if t < 0.05 or t > 0.95:
        return img  # Too small to draw

    # Skull outline
    skull_points = []
    for i in range(120):
        a = i / 120 * 2 * math.pi
        r = brain_shape(t, a) * 1.08
        skull_points.append((cx + r * SIZE * math.cos(a), cy - r * SIZE * math.sin(a)))
    draw.polygon(skull_points, fill=(20, 20, 25, 255))

    # CSF layer (thin bright ring)
    csf_points = []
    for i in range(120):
        a = i / 120 * 2 * math.pi
        r = brain_shape(t, a) * 1.02
        csf_points.append((cx + r * SIZE * math.cos(a), cy - r * SIZE * math.sin(a)))
    draw.polygon(csf_points, fill=(30, 30, 35, 255))

    # Grey matter (outer cortex)
    gm_points = []
    for i in range(120):
        a = i / 120 * 2 * math.pi
        r = brain_shape(t, a)
        gm_points.append((cx + r * SIZE * math.cos(a), cy - r * SIZE * math.sin(a)))
    draw.polygon(gm_points, fill=(140, 140, 148, 255))

    # White matter (inner)
    wm_points = []
    for i in range(120):
        a = i / 120 * 2 * math.pi
        r = brain_shape(t, a) * 0.72 + 0.01 * math.sin(a * 7 + t * 4)
        wm_points.append((cx + r * SIZE * math.cos(a), cy - r * SIZE * math.sin(a)))
    draw.polygon(wm_points, fill=(185, 185, 190, 255))

    # Deep white matter (even lighter center)
    dwm_points = []
    for i in range(120):
        a = i / 120 * 2 * math.pi
        r = brain_shape(t, a) * 0.45 + 0.008 * math.sin(a * 9)
        dwm_points.append((cx + r * SIZE * math.cos(a), cy - r * SIZE * math.sin(a)))
    draw.polygon(dwm_points, fill=(170, 170, 178, 255))

    # Ventricles (dark, butterfly shape) — prominent mid-levels
    if 0.35 < t < 0.75:
        vent_size = (1 - abs(t - 0.55) * 4) * 0.08 * SIZE
        if vent_size > 5:
            # Left lateral ventricle
            lv_cx = cx - SIZE * 0.06
            lv_cy = cy - SIZE * 0.02
            draw.ellipse([lv_cx - vent_size * 0.9, lv_cy - vent_size * 1.3,
                          lv_cx + vent_size * 0.9, lv_cy + vent_size * 1.3],
                         fill=(25, 25, 30, 255))
            # Right lateral ventricle
            rv_cx = cx + SIZE * 0.06
            rv_cy = cy - SIZE * 0.02
            draw.ellipse([rv_cx - vent_size * 0.9, rv_cy - vent_size * 1.3,
                          rv_cx + vent_size * 0.9, rv_cy + vent_size * 1.3],
                         fill=(25, 25, 30, 255))

    # Longitudinal fissure (dark line, top center)
    if t > 0.2:
        fissure_len = brain_shape(t, math.pi / 2) * SIZE * (0.15 + t * 0.35)
        fissure_top = cy - brain_shape(t, math.pi / 2) * SIZE
        draw.line([(cx, fissure_top), (cx, fissure_top + fissure_len)],
                  fill=(25, 25, 30, 255), width=max(2, int(SIZE * 0.006)))

    # Sulci (darker lines in grey matter)
    for s in range(8):
        sa = (s / 8) * 2 * math.pi + t * 1.5
        points = []
        for d in range(15):
            dd = d / 15 * 0.35
            a = sa + dd
            r = brain_shape(t, a) * (0.95 - dd * 0.3)
            px = cx + r * SIZE * math.cos(a) + random.gauss(0, 1)
            py = cy - r * SIZE * math.sin(a) + random.gauss(0, 1)
            points.append((px, py))
        if len(points) >= 2:
            draw.line(points, fill=(110, 110, 118, 200), width=max(1, int(SIZE * 0.004)))

    # Positive finding (hemorrhage/tumor highlight)
    if positive:
        fx = cx + SIZE * 0.12
        fy = cy - SIZE * 0.08
        fr = SIZE * 0.07
        # Bright region
        for ring in range(int(fr), 0, -1):
            alpha = int(180 * (ring / fr) ** 0.5)
            r_color = min(255, 200 + int(55 * (1 - ring / fr)))
            draw.ellipse([fx - ring, fy - ring, fx + ring, fy + ring],
                         fill=(r_color, 80, 90, alpha))

    # Apply slight blur for MRI-like softness
    img = img.filter(ImageFilter.GaussianBlur(radius=1.5))

    return img


import os
os.makedirs(OUT_DIR, exist_ok=True)

NUM_SLICES = 14
POSITIVE_IDX = 10

for i in range(NUM_SLICES):
    t = (i + 0.5) / NUM_SLICES
    is_pos = (i == POSITIVE_IDX)
    img = draw_brain_slice(t, positive=is_pos)
    img.save(f'{OUT_DIR}/slice_{i:02d}.png')
    print(f'Generated slice {i} (t={t:.2f}, positive={is_pos})')

print(f'Done! {NUM_SLICES} slices saved to {OUT_DIR}/')
