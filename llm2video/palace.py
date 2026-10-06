"""The palace set: textures, 3D layout and the static (non-animated) render of a shot."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import assets
from .cam3d import NEAR, Camera, homography
from .figures import Pose, sprite
from .paint import catmull, noise_texture, soft_blob
from .palette import mix, pal, rgb, shade, sky_stops

# ----------------------------------------------------------------------------- layout
N_STEPS = 22
RISE = 0.25
TREAD = 0.46
H = N_STEPS * RISE              # platform height
L = N_STEPS * TREAD             # horizontal run of the stairs
STAIR_X = 6.5                   # stairs span -STAIR_X..STAIR_X
RAMP_X = 1.7                    # carved imperial ramp in the middle
COURT_X = 34.0
COURT_Z0 = -64.0
TERRACE_D = 16.0
HALL_Z = L + 10.0
HALL_W, HALL_H = 50.0, 21.0
GATE_W, GATE_H = 64.0, 24.0

MINISTER_POS = (0.0, 0.0, -3.0)
EMPEROR_POS = (0.0, H, L + 0.6)

SUN = np.array([-0.45, 0.75, -0.5])
SUN = SUN / np.linalg.norm(SUN)
HAZE = rgb("haze")

STONE = pal("steps")        # bluestone steps
MARBLE = pal("marble")       # white marble balustrades
PAVE = pal("pave")
PAVE_PATH = pal("pave.path")


def light(normal):
    d = max(0.0, float(np.dot(normal, SUN)))
    return (0.55 + 0.6 * d) / (0.55 + 0.6 * 0.497)


def lit(color, normal, depth=0.0, extra=1.0):
    c = shade(color, light(np.asarray(normal, dtype=float)) * extra)
    h = 1 - math.exp(-max(depth, 0) / 230.0)
    return mix(c[:3], HAZE, h * 0.85) + (255,)


# ----------------------------------------------------------------------------- textures

class _TexPen:
    """Metre coordinates on a texture: x to the right, y up from the bottom edge."""

    def __init__(self, img, ppm, ox=0.0, oy=0.0):
        self.img, self.ppm, self.ox, self.oy = img, ppm, ox, oy
        self.d = ImageDraw.Draw(img)
        self.hpx = img.height

    def P(self, x, y):
        return ((x + self.ox) * self.ppm, self.hpx - (y + self.oy) * self.ppm)

    def poly(self, pts, fill):
        self.d.polygon([self.P(*p) for p in pts], fill=fill)

    def rect(self, x0, y0, x1, y1, fill):
        a, b = self.P(x0, y1), self.P(x1, y0)
        self.d.rectangle([a[0], a[1], b[0], b[1]], fill=fill)

    def line(self, pts, fill, w):
        self.d.line([self.P(*p) for p in pts], fill=fill, width=max(1, int(w * self.ppm)))

    def ellipse(self, cx, cy, rx, ry, fill, outline=None, w=0.0):
        a, b = self.P(cx - rx, cy + ry), self.P(cx + rx, cy - ry)
        self.d.ellipse([a[0], a[1], b[0], b[1]], fill=fill, outline=outline,
                       width=max(1, int(w * self.ppm)) if outline else 0)


def _roof(tp, x0, x1, y0, top_x0, top_x1, y1, lift, tile_c, dark_c):
    """Hip roof face with upturned corners, glazed tile rows and eave tile ends."""
    bottom = catmull([(x0 - 0.4, y0 + lift), (x0 + 2.2, y0 + 0.08), ((x0 + x1) / 2, y0),
                      (x1 - 2.2, y0 + 0.08), (x1 + 0.4, y0 + lift)], closed=False, n=12)
    outline = [(top_x0, y1)] + bottom + [(top_x1, y1)]
    mask = Image.new("L", tp.img.size, 0)
    ImageDraw.Draw(mask).polygon([tp.P(*p) for p in outline], fill=255)
    lay = Image.new("RGBA", tp.img.size, (0, 0, 0, 0))
    lp = _TexPen(lay, tp.ppm, tp.ox, tp.oy)
    # vertical gradient: brighter near the eave, darker near the ridge
    steps = 24
    for i in range(steps):
        ya = y0 - 1 + (y1 - y0 + 1.2) * i / steps
        yb = y0 - 1 + (y1 - y0 + 1.2) * (i + 1) / steps
        lp.rect(x0 - 1, ya, x1 + 1, yb, mix(tile_c[:3], dark_c[:3], i / steps * 0.45) + (255,))
    x = x0 - 1
    k = 0
    while x < x1 + 1:
        lp.line([(x, y0 - 1), (x, y1 + 0.2)], shade(tile_c, 0.72), 0.07)
        if k % 2 == 0:
            lp.line([(x + 0.12, y0 - 1), (x + 0.12, y1 + 0.2)], shade(tile_c, 1.18), 0.05)
        x += 0.34
        k += 1
    tp.img.paste(lay, (0, 0), Image.fromarray(np.minimum(np.asarray(mask), np.asarray(lay)[..., 3])))
    # eave edge: dark underside + tile ends
    under = [(p[0], p[1] - 0.28) for p in bottom]
    tp.poly(bottom + list(reversed(under)), pal("ornament.dark"))
    for p in bottom[::2]:
        tp.ellipse(p[0], p[1] - 0.05, 0.13, 0.13, shade(tile_c, 0.85), outline=shade(tile_c, 0.6), w=0.03)
    return bottom


def _brackets(tp, x0, x1, y0, h, unit=0.7):
    tp.rect(x0, y0, x1, y0 + h, pal("bracket.gap"))
    blue, green, gold = pal("lintel.blue"), pal("lintel.green"), pal("paint.gold")
    x = x0 + unit / 2
    while x < x1 - unit / 3:
        rows = [(0.18, green), (0.36, blue), (0.26, green), (0.46, blue), (0.3, green)]
        yy = y0
        rh = h / len(rows)
        for w, c in rows:
            ww = w * unit
            tp.rect(x - ww / 2, yy + rh * 0.08, x + ww / 2, yy + rh * 0.92, c)
            tp.line([(x - ww / 2, yy + rh * 0.92), (x + ww / 2, yy + rh * 0.92)], gold, 0.02)
            yy += rh
        x += unit


def _hall(tp, cx, base_y, width, bays, name=None, font_path=None, levels=2, scale=1.0):
    """Draw a double-eave hall centred at cx with its base at base_y (metres)."""
    s = scale
    half = width / 2
    red, red_d = pal("hall.red"), pal("hall.red.dark")
    gold = pal("paint.gold")
    tile, tile_d = pal("roof.tile"), pal("roof.tile.dark")
    # base
    tp.rect(cx - half + 1 * s, base_y, cx + half - 1 * s, base_y + 1.2 * s, pal("hall.base"))
    tp.rect(cx - half + 1 * s, base_y + 1.05 * s, cx + half - 1 * s, base_y + 1.2 * s, pal("hall.base.light"))
    tp.rect(cx - half + 1 * s, base_y, cx + half - 1 * s, base_y + 0.12 * s, pal("hall.base.dark"))
    y_col0, y_col1 = base_y + 1.2 * s, base_y + 7.6 * s
    span = width - 7.1 * s
    bay = span / bays
    xs = [cx - span / 2 + i * bay for i in range(bays + 1)]
    # doors and windows
    tp.rect(xs[0], y_col0, xs[-1], y_col1, pal("hall.void"))
    for i in range(bays):
        a, b = xs[i], xs[i + 1]
        leaves = 4
        lw = (b - a) / leaves
        for k in range(leaves):
            la, lb = a + k * lw + 0.06 * s, a + (k + 1) * lw - 0.06 * s
            end_bay = i in (0, bays - 1)
            top_lattice = y_col0 + (3.2 if end_bay else 2.4) * s
            tp.rect(la, y_col0, lb, y_col1 - 0.5 * s, pal("hall.door"))
            tp.rect(la + 0.08 * s, top_lattice, lb - 0.08 * s, y_col1 - 0.75 * s, pal("hall.lattice.ground"))
            # lattice
            yy = top_lattice
            step = 0.28 * s
            while yy < y_col1 - 0.75 * s:
                tp.line([(la + 0.08 * s, yy), (lb - 0.08 * s, yy)], pal("hall.lattice"), 0.03 * s)
                yy += step
            xx = la + 0.08 * s
            while xx < lb - 0.08 * s:
                tp.line([(xx, top_lattice), (xx, y_col1 - 0.75 * s)], pal("hall.lattice"), 0.03 * s)
                xx += step
            if end_bay:
                tp.rect(la, y_col0, lb, top_lattice - 0.3 * s, red)
            else:
                tp.rect(la + 0.12 * s, y_col0 + 0.3 * s, lb - 0.12 * s, top_lattice - 0.5 * s, pal("hall.door.panel"))
                tp.line([(la + 0.12 * s, top_lattice - 0.5 * s), (lb - 0.12 * s, top_lattice - 0.5 * s)], gold,
                        0.05 * s)
            tp.line([(la, top_lattice - 0.15 * s), (lb, top_lattice - 0.15 * s)], gold, 0.06 * s)
    # under-eave shadow (drawn on its own layer so alpha blends instead of punching holes)
    sh = Image.new("RGBA", tp.img.size, (0, 0, 0, 0))
    sp = _TexPen(sh, tp.ppm, tp.ox, tp.oy)
    for k in range(10):
        ya = y_col1 - (k + 1) * 0.35 * s
        sp.poly([(xs[0], ya), (xs[-1], ya), (xs[-1], ya + 0.35 * s), (xs[0], ya + 0.35 * s)],
                pal("shadow", int(120 * (1 - k / 10))))
    tp.img.alpha_composite(sh)
    # columns
    for x in xs:
        tp.rect(x - 0.38 * s, y_col0, x + 0.38 * s, y_col1, red)
        tp.rect(x - 0.3 * s, y_col0, x - 0.18 * s, y_col1, pal("hall.red.light"))
        tp.rect(x + 0.16 * s, y_col0, x + 0.38 * s, y_col1, red_d)
        tp.rect(x - 0.48 * s, y_col0, x + 0.48 * s, y_col0 + 0.25 * s, pal("gate.coping"))
    # lintel
    y_l0, y_l1 = y_col1, y_col1 + 0.95 * s
    tp.rect(xs[0] - 0.6 * s, y_l0, xs[-1] + 0.6 * s, y_l1, pal("lintel.blue"))
    for i in range(bays):
        a, b = xs[i], xs[i + 1]
        m = (a + b) / 2
        w = (b - a) * 0.28
        tp.poly([(m - w, (y_l0 + y_l1) / 2), (m - w * 0.7, y_l1 - 0.1 * s), (m + w * 0.7, y_l1 - 0.1 * s),
                 (m + w, (y_l0 + y_l1) / 2), (m + w * 0.7, y_l0 + 0.1 * s), (m - w * 0.7, y_l0 + 0.1 * s)],
                pal("lintel.green"))
        tp.line([(m - w, (y_l0 + y_l1) / 2), (m - w * 0.7, y_l1 - 0.1 * s), (m + w * 0.7, y_l1 - 0.1 * s),
                 (m + w, (y_l0 + y_l1) / 2), (m + w * 0.7, y_l0 + 0.1 * s), (m - w * 0.7, y_l0 + 0.1 * s),
                 (m - w, (y_l0 + y_l1) / 2)], gold, 0.06 * s)
        for e in (a + 0.5 * s, b - 0.5 * s):
            d = 1 if e < m else -1
            tp.line([(e, y_l0 + 0.1 * s), (e + d * 0.35 * s, (y_l0 + y_l1) / 2), (e, y_l1 - 0.1 * s)], gold,
                    0.06 * s)
    _brackets(tp, xs[0] - 1.2 * s, xs[-1] + 1.2 * s, y_l1, 1.15 * s, unit=0.72 * s)
    y_b = y_l1 + 1.15 * s
    # rafter ends
    tp.rect(xs[0] - 2 * s, y_b, xs[-1] + 2 * s, y_b + 0.35 * s, pal("eave.under"))
    x = xs[0] - 1.9 * s
    k = 0
    while x < xs[-1] + 1.9 * s:
        tp.rect(x, y_b + 0.08 * s, x + 0.16 * s, y_b + 0.26 * s, pal("lintel.blue") if k % 2 else pal("lintel.green"))
        x += 0.3 * s
        k += 1
    y_r0 = y_b + 0.35 * s
    if levels == 2:
        top1 = y_r0 + 2.6 * s
        _roof(tp, cx - half + 0.5 * s, cx + half - 0.5 * s, y_r0, cx - half + 5 * s, cx + half - 5 * s, top1,
              0.75 * s, tile, tile_d)
        # upper storey
        w2 = half - 5.8 * s
        tp.rect(cx - w2, top1 - 0.05, cx + w2, top1 + 0.7 * s, pal("hall.red.dark"))
        _brackets(tp, cx - w2, cx + w2, top1 + 0.7 * s, 0.8 * s, unit=0.6 * s)
        y_u0 = top1 + 1.5 * s
        tp.rect(cx - w2 - 0.8 * s, y_u0 - 0.05, cx + w2 + 0.8 * s, y_u0 + 0.25 * s, pal("eave.under"))
        y_u0 += 0.25 * s
    else:
        y_u0 = y_r0
    # upper roof
    ridge_y = y_u0 + 5.4 * s
    rx0, rx1 = cx - half * 0.48, cx + half * 0.48
    ux0, ux1 = (cx - half + 3.8 * s, cx + half - 3.8 * s) if levels == 2 else (cx - half, cx + half)
    _roof(tp, ux0, ux1, y_u0, rx0, rx1, ridge_y, 0.8 * s, shade(tile, 0.96), tile_d)
    # hip ridges with little guardian figures
    for sgn, rx in ((-1, rx0), (1, rx1)):
        cx_end = ux0 - 0.3 * s if sgn < 0 else ux1 + 0.3 * s
        pts = catmull([(rx, ridge_y + 0.2 * s), ((rx + cx_end) / 2 + sgn * 0.3 * s, (ridge_y + y_u0) / 2 + 0.6 * s),
                       (cx_end, y_u0 + 0.9 * s)], closed=False, n=10)
        tp.line(pts, shade(tile_d, 0.9), 0.4 * s)
        tp.line(pts, shade(tile, 1.08), 0.12 * s)
        for j in range(5):
            px, py = pts[-2 - j * 2]
            tp.ellipse(px, py + 0.28 * s, 0.14 * s, 0.2 * s, pal("ornament.dark"))
    # main ridge and chiwen ornaments
    tp.rect(rx0 - 0.2 * s, ridge_y, rx1 + 0.2 * s, ridge_y + 0.75 * s, shade(tile_d, 1.05))
    tp.rect(rx0 - 0.2 * s, ridge_y + 0.5 * s, rx1 + 0.2 * s, ridge_y + 0.62 * s, shade(tile, 1.1))
    for sgn, rx in ((-1, rx0), (1, rx1)):
        body = [(rx - sgn * 0.1 * s, ridge_y), (rx + sgn * 0.9 * s, ridge_y), (rx + sgn * 1.0 * s, ridge_y + 1.4 * s),
                (rx + sgn * 0.6 * s, ridge_y + 2.4 * s), (rx - sgn * 0.3 * s, ridge_y + 2.6 * s),
                (rx - sgn * 0.6 * s, ridge_y + 2.1 * s), (rx - sgn * 0.25 * s, ridge_y + 1.9 * s),
                (rx - sgn * 0.1 * s, ridge_y + 1.3 * s), (rx - sgn * 0.5 * s, ridge_y + 0.8 * s)]
        tp.poly(catmull(body, n=6), shade(tile_d, 1.05))
        tp.line(catmull([(rx + sgn * 0.3 * s, ridge_y + 0.4 * s), (rx + sgn * 0.5 * s, ridge_y + 1.4 * s),
                         (rx, ridge_y + 2.1 * s)], closed=False), shade(tile, 1.1), 0.1 * s)
        tp.ellipse(rx - sgn * 0.05 * s, ridge_y + 1.2 * s, 0.12 * s, 0.12 * s, pal("ornament.dark"))
    # plaque
    if name:
        pw, ph = 2.5 * s, 4.1 * s
        py0 = y_r0 + 1.3 * s
        tp.rect(cx - pw / 2, py0, cx + pw / 2, py0 + ph, pal("plaque.frame"))
        tp.rect(cx - pw / 2 + 0.28 * s, py0 + 0.28 * s, cx + pw / 2 - 0.28 * s, py0 + ph - 0.28 * s, pal("plaque.ground"))
        for j in range(12):
            tp.ellipse(cx - pw / 2 + 0.14 * s, py0 + 0.3 * s + j * (ph - 0.6 * s) / 11, 0.07 * s, 0.07 * s,
                       pal("plaque.stud"))
            tp.ellipse(cx + pw / 2 - 0.14 * s, py0 + 0.3 * s + j * (ph - 0.6 * s) / 11, 0.07 * s, 0.07 * s,
                       pal("plaque.stud"))
        if font_path:
            fs = int(0.95 * s * tp.ppm)
            font = ImageFont.truetype(font_path, fs)
            for j, ch in enumerate(name):
                cy = py0 + ph - 0.55 * s - (j + 0.5) * (ph - 1.1 * s) / len(name)
                x, y = tp.P(cx, cy)
                tp.d.text((x, y), ch, font=font, fill=pal("plaque.text"), anchor="mm")


@lru_cache(maxsize=4)
def hall_texture(ppm=110):
    img = Image.new("RGBA", (int(HALL_W * ppm), int(HALL_H * ppm)), (0, 0, 0, 0))
    tp = _TexPen(img, ppm)
    _hall(tp, HALL_W / 2, 0.0, HALL_W - 1.0, 11, name="承天殿", font_path=assets.font("plaque"))
    return img


@lru_cache(maxsize=4)
def gate_texture(ppm=40):
    img = Image.new("RGBA", (int(GATE_W * ppm), int(GATE_H * ppm)), (0, 0, 0, 0))
    tp = _TexPen(img, ppm)
    wall_h = 10.0
    tp.rect(0, 0, GATE_W, wall_h, pal("gate.wall"))
    tp.rect(0, 0, GATE_W, 0.8, pal("gate.base"))
    tp.rect(0, wall_h - 0.5, GATE_W, wall_h, pal("gate.coping"))
    for cx, w in ((GATE_W / 2, 5.0), (GATE_W / 2 - 12, 3.8), (GATE_W / 2 + 12, 3.8)):
        tp.rect(cx - w / 2, 0.8, cx + w / 2, 5.2, pal("gate.void"))
        tp.ellipse(cx, 5.2, w / 2, w / 2, pal("gate.void"))
    _hall(tp, GATE_W / 2, wall_h, 40.0, 9, levels=2, scale=0.85)
    return img


@lru_cache(maxsize=4)
def corridor_texture(length=100.0, ppm=30):
    h = 9.0
    img = Image.new("RGBA", (int(length * ppm), int(h * ppm)), (0, 0, 0, 0))
    tp = _TexPen(img, ppm)
    tp.rect(0, 0, length, 0.7, pal("corridor.base"))
    tp.rect(0, 0.7, length, 6.0, pal("gate.wall"))
    x = 2.0
    while x < length:
        tp.rect(x - 0.25, 0.7, x + 0.25, 6.0, pal("corridor.col"))
        tp.rect(x + 1.0, 2.6, x + 3.0, 4.8, pal("corridor.window"))
        for k in range(6):
            tp.line([(x + 1.0 + k * 0.4, 2.6), (x + 1.0 + k * 0.4, 4.8)], pal("corridor.lattice"), 0.05)
        x += 4.0
    tp.rect(0, 6.0, length, 6.6, pal("lintel.blue"))
    tp.rect(0, 6.6, length, 6.9, pal("eave.under"))
    tp.rect(0, 6.9, length, 8.6, pal("corridor.roof"))
    x = 0.0
    while x < length:
        tp.line([(x, 6.9), (x, 8.6)], pal("corridor.roof.line"), 0.06)
        x += 0.35
    tp.rect(0, 8.5, length, 9.0, pal("corridor.roof.edge"))
    return img


@lru_cache(maxsize=4)
def terrace_texture(width=COURT_X - STAIR_X, ppm=60):
    img = Image.new("RGBA", (int(width * ppm), int(H * ppm)), (0, 0, 0, 0))
    tp = _TexPen(img, ppm)
    tp.rect(0, 0, width, H, pal("terrace"))
    bands = [(0.0, 0.35, "terrace.dark"), (0.35, 0.8, "terrace.band"), (1.5, 1.9, "terrace.band"),
             (1.9, 3.6, "terrace.panel"), (3.6, 4.0, "terrace.band"), (4.7, 5.1, "terrace.band"),
             (5.1, H, "hall.base.light")]
    for y0, y1, c in bands:
        tp.rect(0, y0, width, y1, pal(c))
    for y0 in (0.8, 4.0):  # lotus petal rows
        x = 0.1
        while x < width:
            tp.ellipse(x + 0.2, y0 + 0.35, 0.2, 0.35, pal("marble.1"), outline=pal("marble.3"), w=0.03)
            x += 0.42
    x = 0.8
    while x < width:  # carved panels on the recessed waist
        tp.rect(x, 2.1, x + 2.2, 3.4, pal("marble.2"))
        tp.rect(x + 0.1, 2.2, x + 2.1, 3.3, pal("marble.1.5"))
        x += 3.0
    x = 1.3
    while x < width:  # drain spouts
        tp.rect(x - 0.18, 4.9, x + 0.18, 5.25, pal("spout"))
        tp.ellipse(x, 4.95, 0.2, 0.17, pal("spout"))
        tp.ellipse(x, 4.92, 0.06, 0.05, pal("spout.hole"))
        x += 2.6
    arr = np.asarray(img).astype(float)
    arr[..., :3] *= noise_texture(img.size, scale=0.5, seed=3, amp=0.06)[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


@lru_cache(maxsize=4)
def ramp_texture(ppm=160):
    w_m = RAMP_X * 2
    l_m = math.hypot(L, H)
    img = Image.new("RGBA", (int(w_m * ppm), int(l_m * ppm)), pal("terrace.panel"))
    tp = _TexPen(img, ppm)
    rng = np.random.default_rng(7)
    hi, lo = pal("marble.0"), pal("marble.4.5")

    def relief(pts, w):
        tp.line([(x - 0.03, y + 0.03) for x, y in pts], hi, w)
        tp.line([(x + 0.03, y - 0.03) for x, y in pts], lo, w)
        tp.line(pts, pal("marble.1.5"), w * 0.75)

    tp.rect(0, 0, w_m, l_m, pal("marble.2.5"))
    tp.rect(0.12, 0.12, w_m - 0.12, l_m - 0.12, pal("marble.2"))
    # sea waves at the bottom, mountains, then clouds with dragons
    for k in range(8):
        y = 0.3 + k * 0.1
        relief([(0.2 + i * 0.1, y + 0.05 * math.sin(i * 1.3 + k)) for i in range(int((w_m - 0.4) / 0.1) + 1)], 0.04)
    for cx in (0.9, 1.7, 2.5):
        relief([(cx - 0.4, 1.1), (cx, 1.8), (cx + 0.4, 1.1)], 0.06)
    for dragon_y in (4.0, 8.5):
        body = [(0.5, dragon_y - 1.2), (2.8, dragon_y - 0.6), (0.7, dragon_y + 0.2), (2.6, dragon_y + 1.0),
                (1.5, dragon_y + 1.8)]
        dense = catmull(body, closed=False, n=14)
        relief(dense, 0.2)
        for i in range(0, len(dense) - 1, 2):
            x, y = dense[i]
            tp.ellipse(x, y, 0.05, 0.05, lo)
        hx, hy = body[-1]
        tp.ellipse(hx, hy, 0.3, 0.24, pal("marble.1.5"), outline=lo, w=0.04)
        relief([(hx - 0.25, hy + 0.15), (hx - 0.5, hy + 0.5)], 0.05)
        relief([(hx + 0.25, hy + 0.15), (hx + 0.5, hy + 0.5)], 0.05)
        tp.ellipse(1.7, dragon_y + 2.3, 0.18, 0.18, pal("terrace.band"), outline=lo, w=0.04)
    for _ in range(26):
        cx, cy = rng.uniform(0.4, w_m - 0.4), rng.uniform(2.2, l_m - 0.8)
        r = rng.uniform(0.12, 0.25)
        pts = [(cx + r * (1 - t / 14) * math.cos(t * 0.8), cy + r * (1 - t / 14) * math.sin(t * 0.8))
               for t in range(14)]
        relief(pts, 0.04)
    arr = np.asarray(img).astype(float)
    arr[..., :3] *= noise_texture(img.size, scale=0.4, seed=11, amp=0.05)[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")


@lru_cache(maxsize=8)
def burner_sprite(scale):
    from .paint import Pen
    p = Pen(scale * 2, 1.8, 2.4, foot_m=0.05)
    bronze, dark = pal("bronze"), pal("bronze.dark")
    for x in (-0.45, 0.0, 0.45):
        p.poly([(x - 0.07, 0.0), (x + 0.07, 0.0), (x + 0.09, 0.6), (x - 0.09, 0.6)], dark)
    p.smooth([(-0.62, 1.25), (-0.66, 0.9), (-0.45, 0.55), (0, 0.48), (0.45, 0.55), (0.66, 0.9), (0.62, 1.25)],
             bronze, outline=dark, width=0.02)
    p.rect(-0.66, 1.18, 0.66, 1.3, shade(bronze, 1.2))
    for s in (-1, 1):
        p.poly([(s * 0.35, 1.3), (s * 0.45, 1.3), (s * 0.47, 1.62), (s * 0.3, 1.62), (s * 0.3, 1.52),
                (s * 0.38, 1.52)], dark)
    p.smooth([(-0.4, 1.3), (-0.35, 1.5), (0, 1.6), (0.35, 1.5), (0.4, 1.3)], shade(bronze, 0.9))
    p.ellipse(0, 1.68, 0.08, 0.08, bronze)
    p.line([(-0.4, 0.95), (0.4, 0.95)], pal("bronze.light"), 0.03)
    for k in range(-3, 4):
        p.ellipse(k * 0.15, 0.8, 0.04, 0.04, pal("bronze.light"))
    img = p.img.resize((p.w // 2, p.h // 2), Image.LANCZOS)
    return img, (p.ox / 2, p.oy / 2)


# ----------------------------------------------------------------------------- scene render

def _warp(canvas, tex, quad, cam, bright=1.0, haze_depth=0.0):
    pts = cam.to_cam(np.array(quad))
    if (pts[:, 2] < NEAR).any():
        return
    dst = cam.cam_to_screen(pts)
    x0, y0 = np.floor(dst.min(axis=0)).astype(int)
    x1, y1 = np.ceil(dst.max(axis=0)).astype(int)
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x1, canvas.width), min(y1, canvas.height)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    # pre-scale the texture to roughly the on-screen size to avoid aliasing
    span = max(np.linalg.norm(dst[1] - dst[0]), np.linalg.norm(dst[2] - dst[3]))
    k = min(1.0, span * 1.3 / tex.width)
    t = tex if k > 0.95 else tex.resize((max(2, int(tex.width * k)), max(2, int(tex.height * k))), Image.LANCZOS)
    tw, th = t.size
    src = [(0, 0), (tw, 0), (tw, th), (0, th)]
    hm = homography([(x - cx0, y - cy0) for x, y in dst], src)
    out = t.transform((cx1 - cx0, cy1 - cy0), Image.PERSPECTIVE, tuple(hm.flatten()[:8]), Image.BICUBIC)
    if bright != 1.0 or haze_depth > 0:
        a = np.asarray(out).astype(float)
        a[..., :3] *= bright
        h = (1 - math.exp(-haze_depth / 230.0)) * 0.85
        a[..., :3] = a[..., :3] * (1 - h) + np.array(HAZE) * h
        out = Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")
    canvas.alpha_composite(out, (int(cx0), int(cy0)))


class Scene:
    """Collects depth-sorted draw calls for one camera."""

    def __init__(self, cam):
        self.cam = cam
        self.items = []

    def add(self, depth, fn):
        self.items.append((depth, len(self.items), fn))

    def quad(self, pts, color, normal, outline=None, extra=1.0):
        cam = self.cam
        c = np.mean(pts, axis=0)
        if normal is not None and not cam.facing(c, normal):
            return
        d = cam.depth(c)
        if d < NEAR and all(cam.depth(p) < NEAR for p in pts):
            return
        col = lit(color, normal if normal is not None else (0, 0, -1), np.linalg.norm(c - cam.pos), extra)

        def fn(draw, img, pts=pts, col=col):
            q = cam.project_poly(pts)
            if q:
                draw.polygon(q, fill=col)
                if outline:
                    draw.line(q + [q[0]], fill=outline, width=1)
        self.add(d, fn)

    def render(self, draw, img):
        for _, _, fn in sorted(self.items, key=lambda t: (-t[0], t[1])):
            fn(draw, img)


def _box(sc, x0, x1, y0, y1, z0, z1, color, extra=1.0):
    faces = [
        ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
        ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        ([(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)], (-1, 0, 0)),
        ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (1, 0, 0)),
        ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
    ]
    for pts, n in faces:
        sc.quad(np.array(pts, dtype=float), color, np.array(n, dtype=float), extra=extra)


def _balustrade(sc, p0, p1, n_posts, height=1.1):
    """Marble balustrade from p0 to p1 (both on the walking surface)."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    posts = [p0 + (p1 - p0) * i / (n_posts - 1) for i in range(n_posts)]
    along = p1 - p0
    horiz = np.array([along[0], 0, along[2]])
    horiz /= np.linalg.norm(horiz)
    side = np.cross(horiz, [0, 1, 0])
    for a, b in zip(posts[:-1], posts[1:]):
        # panel between posts (thin slab)
        bot_a, bot_b = a + [0, 0.12, 0], b + [0, 0.12, 0]
        top_a, top_b = a + [0, height * 0.72, 0], b + [0, height * 0.72, 0]
        for sgn in (-1, 1):
            off = side * 0.07 * sgn
            n = side * sgn
            sc.quad(np.array([bot_a + off, bot_b + off, top_b + off, top_a + off]), MARBLE, n)
            ia = a + (b - a) * 0.12
            ib = a + (b - a) * 0.88
            sc.quad(np.array([ia + [0, 0.25, 0] + off * 1.05, ib + [0, 0.25, 0] + off * 1.05,
                              ib + [0, height * 0.6, 0] + off * 1.05, ia + [0, height * 0.6, 0] + off * 1.05]),
                    shade(MARBLE, 0.86), n)
        sc.quad(np.array([top_a - side * 0.09, top_b - side * 0.09, top_b + side * 0.09, top_a + side * 0.09]),
                shade(MARBLE, 1.02), np.array([0, 1.0, 0]))
    for q in posts:
        x, y, z = q
        _box(sc, x - 0.13, x + 0.13, y, y + height, z - 0.13, z + 0.13, MARBLE)
        _box(sc, x - 0.1, x + 0.1, y + height, y + height + 0.22, z - 0.1, z + 0.1, shade(MARBLE, 1.03))


def build_scene(cam, detail=True):
    sc = Scene(cam)
    rng = np.random.default_rng(1)
    # ---- stairs (two flights either side of the carved ramp)
    for i in range(N_STEPS):
        y0, y1 = i * RISE, (i + 1) * RISE
        z0, z1 = i * TREAD, (i + 1) * TREAD
        for xa, xb in ((-STAIR_X, -RAMP_X), (RAMP_X, STAIR_X)):
            v = 1 + rng.uniform(-0.06, 0.06)
            sc.quad(np.array([(xa, y0, z0), (xb, y0, z0), (xb, y1, z0), (xa, y1, z0)]), shade(STONE, 0.93 * v),
                    np.array([0, 0, -1.0]))
            sc.quad(np.array([(xa, y1, z0), (xb, y1, z0), (xb, y1, z1), (xa, y1, z1)]), shade(STONE, v),
                    np.array([0, 1.0, 0]))
            # nosing highlight with the shadow line underneath, and the shadow at the back of each tread
            sc.quad(np.array([(xa, y1 - 0.075, z0 - 0.005), (xb, y1 - 0.075, z0 - 0.005), (xb, y1 - 0.035, z0 - 0.005),
                              (xa, y1 - 0.035, z0 - 0.005)]), shade(STONE, 0.66), np.array([0, 0, -1.0]))
            sc.quad(np.array([(xa, y1 - 0.035, z0 - 0.006), (xb, y1 - 0.035, z0 - 0.006), (xb, y1, z0 - 0.006),
                              (xa, y1, z0 - 0.006)]), shade(STONE, 1.16), np.array([0, 0, -1.0]))
            sc.quad(np.array([(xa, y1 + 0.003, z1 - 0.06), (xb, y1 + 0.003, z1 - 0.06), (xb, y1 + 0.003, z1),
                              (xa, y1 + 0.003, z1)]), shade(STONE, 0.72), np.array([0, 1.0, 0]))
            if detail:  # joints between stone blocks
                jx = xa + rng.uniform(0.3, 1.4)
                while jx < xb - 0.3:
                    sc.quad(np.array([(jx, y0 + 0.01, z0 - 0.007), (jx + 0.025, y0 + 0.01, z0 - 0.007),
                                      (jx + 0.025, y1 - 0.075, z0 - 0.007), (jx, y1 - 0.075, z0 - 0.007)]),
                            shade(STONE, 0.7), np.array([0, 0, -1.0]))
                    sc.quad(np.array([(jx, y1 + 0.004, z0), (jx + 0.025, y1 + 0.004, z0),
                                      (jx + 0.025, y1 + 0.004, z1), (jx, y1 + 0.004, z1)]),
                            shade(STONE, 0.78), np.array([0, 1.0, 0]))
                    jx += rng.uniform(1.1, 1.9)
            if detail:
                for _ in range(2):  # stains / worn patches
                    sx = rng.uniform(xa + 0.2, xb - 0.8)
                    w = rng.uniform(0.2, 0.7)
                    sc.quad(np.array([(sx, y1 + 0.002, z0 + 0.08), (sx + w, y1 + 0.002, z0 + 0.08),
                                      (sx + w, y1 + 0.002, z0 + 0.3), (sx, y1 + 0.002, z0 + 0.3)]),
                            shade(STONE, rng.uniform(0.86, 0.94)), np.array([0, 1.0, 0]))
        # stair side walls
        for x, n in ((-STAIR_X, -1.0), (STAIR_X, 1.0)):
            sc.quad(np.array([(x, 0, z0), (x, y1, z0), (x, y1, z1), (x, 0, z1)]), MARBLE, np.array([n, 0, 0]))
    # ---- carved ramp
    ramp = [(-RAMP_X, H + 0.06, L), (RAMP_X, H + 0.06, L), (RAMP_X, 0.06, 0.0), (-RAMP_X, 0.06, 0.0)]
    rn = np.cross(np.subtract(ramp[1], ramp[0]), np.subtract(ramp[3], ramp[0]))
    rn = rn / np.linalg.norm(rn)
    if rn[1] < 0:
        rn = -rn
    rc = np.mean(ramp, axis=0)
    if cam.facing(rc, rn):
        sc.add(cam.depth(rc) + 2.0,
               lambda draw, img: _warp(img, ramp_texture(), ramp, cam, light(rn),
                                       float(np.linalg.norm(rc - cam.pos))))
    for x in (-RAMP_X - 0.12, RAMP_X):  # raised borders of the ramp
        for i in range(N_STEPS):
            y0, z0 = i * RISE, i * TREAD
            sc.quad(np.array([(x, y0 + 0.28, z0), (x + 0.12, y0 + 0.28, z0), (x + 0.12, y0 + 0.28 + RISE, z0 + TREAD),
                              (x, y0 + 0.28 + RISE, z0 + TREAD)]), MARBLE, np.array([0, 1.0, -0.5]))
            sc.quad(np.array([(x, y0, z0), (x + 0.12, y0, z0), (x + 0.12, y0 + 0.28, z0), (x, y0 + 0.28, z0)]),
                    MARBLE, np.array([0, 0, -1.0]))
    # ---- balustrades
    for x in (-STAIR_X + 0.15, STAIR_X - 0.15):
        _balustrade(sc, (x, 0.0, 0.0), (x, H, L), 9)
        _box(sc, x - 0.16, x + 0.16, 0, 0.8, -0.9, 0.0, MARBLE)  # drum stones at the foot
    for sgn in (-1, 1):
        _balustrade(sc, (sgn * STAIR_X, H, L + 0.15), (sgn * COURT_X, H, L + 0.15), 19)
    # ---- terrace front walls
    for sgn in (-1, 1):
        xa, xb = sgn * STAIR_X, sgn * COURT_X
        quad = [(min(xa, xb), H, L), (max(xa, xb), H, L), (max(xa, xb), 0, L), (min(xa, xb), 0, L)]
        c = np.mean(quad, axis=0)
        if cam.facing(c, (0, 0, -1)):
            sc.add(cam.depth(c), lambda draw, img, q=quad, c=c: _warp(
                img, terrace_texture(), q, cam, light(np.array([0, 0, -1.0])), float(np.linalg.norm(c - cam.pos))))
    # ---- hall, gate and side corridors
    hq = [(-HALL_W / 2, H + HALL_H, HALL_Z), (HALL_W / 2, H + HALL_H, HALL_Z), (HALL_W / 2, H, HALL_Z),
          (-HALL_W / 2, H, HALL_Z)]
    hc = np.mean(hq, axis=0)
    if cam.facing(hc, (0, 0, -1)):
        sc.add(cam.depth(hc) + 5, lambda draw, img: _warp(img, hall_texture(), hq, cam, 1.0,
                                                         float(np.linalg.norm(hc - cam.pos))))
    gq = [(GATE_W / 2, GATE_H, COURT_Z0), (-GATE_W / 2, GATE_H, COURT_Z0), (-GATE_W / 2, 0, COURT_Z0),
          (GATE_W / 2, 0, COURT_Z0)]
    gc = np.mean(gq, axis=0)
    if cam.facing(gc, (0, 0, 1)):
        sc.add(cam.depth(gc) + 5, lambda draw, img: _warp(img, gate_texture(), gq, cam, 0.9,
                                                         float(np.linalg.norm(gc - cam.pos))))
    seg = 10.0
    z = COURT_Z0
    tex = corridor_texture()
    while z < L + TERRACE_D - 0.1:
        z1 = min(z + seg, L + TERRACE_D)
        u0, u1 = (z - COURT_Z0) / 100.0, (z1 - COURT_Z0) / 100.0
        sub = tex.crop((int(u0 * tex.width), 0, int(u1 * tex.width), tex.height))
        for sgn in (-1, 1):
            x = sgn * COURT_X
            n = np.array([-sgn, 0, 0], dtype=float)
            if sgn < 0:
                quad = [(x, 9.0, z1), (x, 9.0, z), (x, 0, z), (x, 0, z1)]
                t = sub.transpose(Image.FLIP_LEFT_RIGHT)
            else:
                quad = [(x, 9.0, z), (x, 9.0, z1), (x, 0, z1), (x, 0, z)]
                t = sub
            c = np.mean(quad, axis=0)
            if cam.facing(c, n):
                sc.add(cam.depth(c), lambda draw, img, q=quad, t=t, c=c, n=n: _warp(
                    img, t, q, cam, light(n), float(np.linalg.norm(c - cam.pos))))
        z = z1
    # ---- guards and bronze tripods (static billboards)
    for pos in ((-8.2, H, L + 0.9), (8.2, H, L + 0.9), (-9.0, 0, -1.2), (9.0, 0, -1.2)):
        _billboard(sc, lambda s: sprite("guard", "front", Pose(), s), pos)
    for x in (-5.5, 5.5):
        _billboard(sc, lambda s: burner_sprite(round(s, 1)), (x, H, L + 5.5))
    return sc


def _billboard(sc, make, pos):
    cam = sc.cam
    d = cam.depth(pos)
    if d < 1.0:
        return
    scale = cam.scale_at(pos)
    fx, fy = cam.project([pos])[0]

    def fn(draw, img):
        spr, (ax, ay) = make(scale)
        paste_rgba(img, spr, fx - ax, fy - ay)
    sc.add(d, fn)


def paste_rgba(dst, src, x, y):
    """alpha_composite that tolerates sprites hanging off any edge."""
    x, y = int(round(x)), int(round(y))
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    dst.alpha_composite(src.crop((cx0, cy0, cx1, cy1)), (x + cx0, y + cy0))


def draw_ground(cam, img, draw):
    """Courtyard and terrace paving (always behind everything else)."""
    rng = np.random.default_rng(5)
    far = []
    # grout base
    for pts, col, n in (
        ([(-COURT_X, 0, COURT_Z0), (COURT_X, 0, COURT_Z0), (COURT_X, 0, 0), (-COURT_X, 0, 0)], pal("pave.grout"),
         (0, 1, 0)),
        ([(-COURT_X, H, L), (COURT_X, H, L), (COURT_X, H, L + TERRACE_D), (-COURT_X, H, L + TERRACE_D)],
         pal("pave.grout"), (0, 1, 0)),
    ):
        if cam.facing(np.mean(pts, axis=0), n):
            q = cam.project_poly(np.array(pts, float))
            if q:
                draw.polygon(q, fill=lit(col, n, 40))

    def slabs(x0, x1, z0, z1, y, sw, sd, base, stagger=True):
        if not cam.facing((0, y, (z0 + z1) / 2), (0, 1, 0)):
            return
        z = z0
        row = 0
        while z < z1 - 1e-6:
            off = (sw / 2 if (stagger and row % 2) else 0)
            x = x0 - off
            while x < x1 - 1e-6:
                xa, xb = max(x, x0), min(x + sw, x1)
                g = 0.03
                pts = np.array([(xa + g, y, z + g), (xb - g, y, z + g), (xb - g, y, min(z + sd, z1) - g),
                                (xa + g, y, min(z + sd, z1) - g)])
                c = pts.mean(axis=0)
                d = float(np.linalg.norm(c - cam.pos))
                if d < 140:
                    q = cam.project_poly(pts)
                    if q:
                        col = lit(shade(base, 1 + rng.uniform(-0.07, 0.07)), (0, 1, 0), d)
                        far.append((d, q, col))
                x += sw
            z += sd
            row += 1

    slabs(-COURT_X, -2.4, COURT_Z0, 0, 0.0, 1.6, 0.8, PAVE)
    slabs(2.4, COURT_X, COURT_Z0, 0, 0.0, 1.6, 0.8, PAVE)
    slabs(-2.4, 2.4, COURT_Z0, 0, 0.0, 2.4, 1.2, PAVE_PATH, stagger=False)
    slabs(-COURT_X, COURT_X, L + 0.2, L + TERRACE_D, H, 1.2, 1.2, pal("pave.terrace"))
    for d, q, col in sorted(far, key=lambda t: -t[0]):
        draw.polygon(q, fill=col)


SKY_STOPS = sky_stops()


def sky_image(cam, size):
    """Late-afternoon sky coloured by the elevation angle of each pixel row, plus a sun glow."""
    w, h = size
    yy = np.arange(h, dtype=float)
    dirs = cam.f[None, :] + cam.u[None, :] * ((cam.cy - yy) / cam.focal)[:, None]
    elev = np.degrees(np.arcsin(dirs[:, 1] / np.linalg.norm(dirs, axis=1)))
    col = np.stack([np.interp(elev, [e for e, _ in SKY_STOPS], [c[k] for _, c in SKY_STOPS]) for k in range(3)],
                   axis=-1)
    arr = np.repeat(col[:, None, :], w, axis=1)
    hy = float(cam.cy + cam.focal * np.tan(np.arcsin(cam.f[1])))  # horizon row (no roll)
    gy, gx = np.mgrid[0:h, 0:w]
    sx, sy = -0.1 * w, hy - 0.35 * h
    r = np.sqrt((gx - sx) ** 2 + (gy - sy) ** 2) / (0.9 * w)
    glow = np.exp(-r * r * 2.2)[..., None]
    arr = arr * (1 - 0.4 * glow) + np.array(rgb("glow")) * 0.4 * glow
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB"), hy


def render_static(cam_params, size, ss=2):
    """Render sky and world layers for a camera; returns (sky RGB, world RGBA, cam)."""
    w, h = size
    cam_hi = Camera(cam_params["pos"], cam_params["target"], cam_params["fov"], (w * ss, h * ss),
                    cam_params.get("roll", 0.0))
    cam = Camera(cam_params["pos"], cam_params["target"], cam_params["fov"], (w, h), cam_params.get("roll", 0.0))
    world = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(world)
    draw_ground(cam_hi, world, draw)
    sc = build_scene(cam_hi)
    sc.render(draw, world)
    world = world.resize((w, h), Image.LANCZOS)
    sky, horizon = sky_image(cam, (w, h))
    return sky, world, cam, horizon


def soft_shadow(rx, ry):
    return soft_blob(rx, ry, pal("shadow", 110), max(2, rx * 0.25))
