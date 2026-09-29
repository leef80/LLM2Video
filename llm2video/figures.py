"""Flat-illustration characters drawn from simple shapes.

Every figure is drawn in metres with the feet at (0, 0) and returned as an RGBA
sprite plus the pixel position of the feet inside the sprite.  Drawing happens at
2x and is downsampled for anti-aliasing.
"""
import math
from functools import lru_cache

from PIL import Image, ImageFilter

from .paint import Pen, catmull, hexc, shade

SS = 2  # supersampling factor

SKIN = hexc("#efc39b")
SKIN_SH = hexc("#d9a47a")
HAIR = hexc("#15110f")
INK = hexc("#241712")
WHITE = hexc("#f4efe3")
LIP = hexc("#8a2c24")
MOUTH = hexc("#3d0f0c")

MIN_ROBE = hexc("#a3211d")
EMP_ROBE = hexc("#e9b01c")
GOLD = hexc("#d8a431")
GOLD_D = hexc("#9c6a12")
JADE = hexc("#cfe3cf")


class Pose:
    """Animation parameters (all 0..1 unless noted)."""

    def __init__(self, mouth=0.0, blink=False, bow=0.0, kneel=0.0, prostrate=0.0,
                 gesture=0.0, look=(0.0, 0.0)):
        self.mouth = mouth
        self.blink = blink
        self.bow = bow
        self.kneel = kneel
        self.prostrate = prostrate
        self.gesture = gesture
        self.look = look

    def key(self):
        q = lambda v, n: int(round(max(0.0, min(1.0, v)) * n))
        return (q(self.mouth, 5), bool(self.blink), q(self.bow, 12), q(self.kneel, 16),
                q(self.prostrate, 16), q(self.gesture, 12),
                int(round(self.look[0] * 4)), int(round(self.look[1] * 4)))


def _rot(pts, pivot, deg):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    px, py = pivot
    return [(px + (x - px) * ca - (y - py) * sa, py + (x - px) * sa + (y - py) * ca) for x, y in pts]


def _mirror(pts):
    return [(-x, y) for x, y in pts]


def _outline(c):
    return shade(c, 0.55)


def _oval(cx, cy, rx, ry, deg, n=20):
    """Rotated ellipse as a polygon (used for the emperor's hat wings)."""
    a = math.radians(deg)
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)))
    return pts


# --------------------------------------------------------------------------- pieces

def _robe_body(p, robe, top=1.47, hem_w=0.34, waist_w=0.27, shoulder_w=0.25):
    ctrl = [(-0.12, top + 0.01), (-shoulder_w, top - 0.05), (-waist_w - 0.01, top - 0.3),
            (-waist_w, 0.95), (-waist_w - 0.03, 0.55), (-hem_w, 0.06), (-hem_w * 0.5, 0.03),
            (0, 0.025), (hem_w * 0.5, 0.03), (hem_w, 0.06), (waist_w + 0.03, 0.55),
            (waist_w, 0.95), (waist_w + 0.01, top - 0.3), (shoulder_w, top - 0.05), (0.12, top + 0.01)]
    body = p.layer()
    body.smooth(ctrl, robe, outline=_outline(robe), width=0.006)
    # shading on the side away from the light and soft folds
    sh = p.layer()
    sh.poly([(0.10, 2.0), (0.6, 2.0), (0.6, -0.1), (0.16, -0.1), (0.2, 0.6)], shade(robe, 0.8))
    sh.poly([(-0.6, 2.0), (-0.22, 2.0), (-0.24, 0.8), (-0.26, -0.1), (-0.6, -0.1)], shade(robe, 0.9))
    for x0, x1 in ((-0.12, -0.16), (0.02, 0.03), (0.13, 0.19)):
        sh.line(catmull([(x0, 0.9), (x0 + (x1 - x0) * 0.5, 0.5), (x1, 0.07)], closed=False),
                shade(robe, 0.78), 0.008)
    body.merge(sh, clip_to=body)
    p.merge(body)


def _feet(p, kneel=0.0):
    if kneel > 0.5:
        return
    for s in (-1, 1):
        p.smooth([(s * 0.03, 0.0), (s * 0.13, 0.0), (s * 0.15, 0.03), (s * 0.12, 0.055),
                  (s * 0.04, 0.05)], hexc("#1b1716"))


def _hem_waves(p, clip_layer, y0=0.03, y1=0.3):
    """Dragon-robe sea-wave border (江崖海水)."""
    lay = p.layer()
    cols = [hexc("#2c5f8a"), hexc("#f2ecd9"), hexc("#3f8a6d"), hexc("#f2ecd9"), hexc("#6b4c8a"),
            hexc("#f2ecd9")]
    band = (y1 - y0) * 0.62
    for i in range(34):
        x = -0.5 + i * 0.03
        lay.poly([(x, y0), (x + 0.018, y0), (x + 0.06, y0 + band), (x + 0.042, y0 + band)],
                 cols[i % len(cols)])
    # waves on top of the stripes
    top = y0 + band
    for i in range(12):
        cx = -0.4 + i * 0.075
        lay.ellipse(cx, top, 0.045, 0.03, hexc("#2c5f8a"))
        lay.ellipse(cx, top + 0.005, 0.034, 0.02, hexc("#f2ecd9"))
        lay.ellipse(cx + 0.006, top + 0.003, 0.02, 0.011, hexc("#2c5f8a"))
    # rocky peaks
    for cx, h in ((-0.18, 0.1), (0.0, 0.13), (0.18, 0.1)):
        lay.poly([(cx - 0.05, top), (cx - 0.012, top + h), (cx + 0.012, top + h * 0.85),
                  (cx + 0.05, top)], hexc("#3f8a6d"))
        lay.line([(cx - 0.02, top + 0.02), (cx - 0.005, top + h * 0.8)], hexc("#e8d9a6"), 0.005)
    p.merge(lay, clip_to=clip_layer)


def _dragon_roundel(p, cx, cy, r):
    p.ellipse(cx, cy, r, r, hexc("#f3cf5c"), outline=GOLD_D, width=r * 0.09)
    swirl = [(cx - r * 0.55, cy + r * 0.35), (cx - r * 0.1, cy + r * 0.62), (cx + r * 0.45, cy + r * 0.3),
             (cx + r * 0.2, cy - r * 0.1), (cx - r * 0.35, cy - r * 0.2), (cx - r * 0.1, cy - r * 0.6),
             (cx + r * 0.5, cy - r * 0.45)]
    p.line(catmull(swirl, closed=False), hexc("#b3410f"), r * 0.16)
    p.line(catmull(swirl, closed=False), hexc("#e3702a"), r * 0.06)
    # head, pearl and a few cloud puffs
    p.ellipse(cx - r * 0.55, cy + r * 0.35, r * 0.16, r * 0.13, hexc("#b3410f"))
    p.ellipse(cx - r * 0.6, cy + r * 0.38, r * 0.04, r * 0.04, hexc("#1b1716"))
    p.ellipse(cx + r * 0.05, cy + r * 0.05, r * 0.1, r * 0.1, hexc("#d8322a"))
    for dx, dy in ((0.55, 0.55), (-0.6, -0.5), (0.62, -0.05)):
        p.ellipse(cx + r * dx, cy + r * dy, r * 0.12, r * 0.08, hexc("#3c7fb0"))


def _crane_badge(p, cx, cy, w):
    h = w * 1.0
    p.rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, hexc("#c89b3c"))
    p.rect(cx - w / 2 + w * 0.06, cy - h / 2 + w * 0.06, cx + w / 2 - w * 0.06, cy + h / 2 - w * 0.06,
           hexc("#1f3354"))
    # crane: body, neck, head, wings
    p.smooth([(cx - w * 0.2, cy - w * 0.05), (cx, cy - w * 0.12), (cx + w * 0.18, cy - w * 0.02),
              (cx, cy + w * 0.05)], WHITE)
    p.line(catmull([(cx + w * 0.12, cy), (cx + w * 0.22, cy + w * 0.15), (cx + w * 0.15, cy + w * 0.3)],
                   closed=False), WHITE, w * 0.05)
    p.ellipse(cx + w * 0.15, cy + w * 0.31, w * 0.045, w * 0.035, WHITE)
    p.ellipse(cx + w * 0.15, cy + w * 0.35, w * 0.022, w * 0.018, hexc("#d8322a"))
    p.poly([(cx - w * 0.05, cy), (cx - w * 0.35, cy + w * 0.3), (cx - w * 0.1, cy + w * 0.12)], WHITE)
    p.line([(cx - w * 0.05, cy - w * 0.1), (cx - w * 0.1, cy - w * 0.33)], hexc("#e8e0cc"), w * 0.02)
    for dx, dy in ((-0.3, -0.3), (0.28, -0.28), (-0.28, 0.12)):
        p.ellipse(cx + w * dx, cy + w * dy, w * 0.08, w * 0.04, hexc("#c89b3c"))


def _belt(p, y, w, sag, strap, plaque):
    top = [(-w, y + 0.03), (-w * 0.5, y + 0.03 - sag * 0.7), (0, y + 0.03 - sag),
           (w * 0.5, y + 0.03 - sag * 0.7), (w, y + 0.03)]
    bot = [(x, yy - 0.05) for x, yy in top]
    p.poly(catmull(top, closed=False) + list(reversed(catmull(bot, closed=False))), strap,
           outline=_outline(strap), width=0.004)
    for i in range(-3, 4):
        x = i * w / 3.6
        yy = y + 0.005 - sag * (1 - (x / w) ** 2)
        p.rect(x - 0.022, yy - 0.018, x + 0.022, yy + 0.018, plaque)


def _collar(p, robe, y=1.47):
    p.ellipse(0, y - 0.005, 0.078, 0.032, WHITE)
    p.rect(-0.045, y - 0.01, 0.045, y + 0.09, SKIN_SH)
    p.ellipse(0, y - 0.01, 0.092, 0.04, None, outline=shade(robe, 0.8), width=0.024)


def _face(p, pose, beard, stern=False, head_tf=None):
    T = head_tf or (lambda pts: pts)

    def poly(pts, fill, **kw):
        p.poly(T(pts), fill, **kw)

    def line(pts, fill, w):
        p.line(T(pts), fill, w)

    # ears
    for s in (-1, 1):
        poly(catmull([(s * 0.078, 1.645), (s * 0.1, 1.64), (s * 0.103, 1.61), (s * 0.085, 1.585),
                      (s * 0.074, 1.6)]), SKIN_SH)
    face = [(0, 1.735), (0.07, 1.715), (0.087, 1.655), (0.082, 1.585), (0.055, 1.525), (0.02, 1.5),
            (0, 1.497), (-0.02, 1.5), (-0.055, 1.525), (-0.082, 1.585), (-0.087, 1.655), (-0.07, 1.715)]
    poly(catmull(face), SKIN, outline=shade(SKIN, 0.7), width=0.003)
    poly(catmull([(0.03, 1.73), (0.075, 1.705), (0.085, 1.62), (0.07, 1.55), (0.04, 1.51),
                  (0.06, 1.6)]), hexc("#e6b18a"))
    for s in (-1, 1):
        poly(catmull([(s * 0.045, 1.585), (s * 0.068, 1.59), (s * 0.07, 1.575), (s * 0.05, 1.57)]),
             hexc("#eeb296"))
    # brows
    slope = 0.014 if stern else 0.008
    for s in (-1, 1):
        line([(s * 0.016, 1.662 - (0.004 if stern else 0)), (s * 0.04, 1.668), (s * 0.066, 1.662 + slope)],
             INK, 0.009 if stern else 0.007)
    # eyes
    lx, ly = pose.look
    for s in (-1, 1):
        cx, cy = s * 0.038, 1.636
        if pose.blink:
            line([(cx - 0.017, cy - 0.001), (cx, cy - 0.004), (cx + 0.017, cy - 0.001)], INK, 0.004)
        else:
            poly([(cx - 0.019, cy), (cx - 0.006, cy + 0.008), (cx + 0.012, cy + 0.006), (cx + 0.019, cy - 0.001),
                  (cx + 0.004, cy - 0.006), (cx - 0.012, cy - 0.004)], WHITE)
            ex, ey = cx + lx * 0.006, cy + ly * 0.003
            poly(catmull([(ex - 0.008, ey), (ex, ey + 0.007), (ex + 0.008, ey), (ex, ey - 0.006)]), INK)
            poly(catmull([(ex + 0.002, ey + 0.004), (ex + 0.004, ey + 0.004), (ex + 0.003, ey + 0.002)]),
                 hexc("#ffffff"))
            line([(cx - 0.02, cy + 0.001), (cx - 0.006, cy + 0.009), (cx + 0.012, cy + 0.007),
                  (cx + 0.02, cy)], INK, 0.0035)
    # nose
    line([(0.004, 1.63), (0.009, 1.598), (0.002, 1.59)], shade(SKIN, 0.72), 0.004)
    line([(-0.012, 1.593), (-0.004, 1.588)], shade(SKIN, 0.72), 0.003)
    # mouth
    mo = pose.mouth
    my = 1.563
    if mo > 0.05:
        h = 0.004 + mo * 0.016
        poly(catmull([(-0.019, my), (0, my + 0.004), (0.019, my), (0, my - h)]), MOUTH)
        if mo > 0.4:
            poly(catmull([(-0.012, my + 0.001), (0, my + 0.003), (0.012, my + 0.001), (0, my - 0.003)]),
                 hexc("#e9e2d2"))
    else:
        line([(-0.018, my), (0, my - 0.002), (0.018, my)], LIP, 0.005)
    # facial hair
    hair = hexc("#1c1714")
    for s in (-1, 1):
        line([(s * 0.004, 1.583), (s * 0.022, 1.58), (s * 0.038, 1.571), (s * 0.046, 1.552)], hair, 0.007)
    if beard == "long":
        chin = 1.535 - mo * 0.012
        poly(catmull([(-0.028, chin + 0.012), (0.028, chin + 0.012), (0.024, chin - 0.07), (0.008, chin - 0.16),
                      (0, chin - 0.2), (-0.008, chin - 0.16), (-0.024, chin - 0.07)]), hair)
        for s in (-1, 1):
            poly(catmull([(s * 0.058, 1.55), (s * 0.07, 1.5), (s * 0.058, 1.42), (s * 0.05, 1.43),
                          (s * 0.058, 1.5), (s * 0.05, 1.545)]), hair)
        line([(0.006, chin), (0.004, chin - 0.12)], hexc("#4a403a"), 0.003)
    elif beard == "goatee":
        chin = 1.53 - mo * 0.012
        poly(catmull([(-0.018, chin + 0.012), (0.018, chin + 0.012), (0.012, chin - 0.04), (0, chin - 0.075),
                      (-0.012, chin - 0.04)]), hair)


def _minister_hat_front(p, T, back_first):
    black = hexc("#151414")
    if back_first:
        for s in (-1, 1):
            p.poly(T(catmull([(s * 0.07, 1.776), (s * 0.16, 1.79), (s * 0.26, 1.815), (s * 0.33, 1.812),
                              (s * 0.35, 1.78), (s * 0.325, 1.748), (s * 0.24, 1.752), (s * 0.15, 1.757)])),
                   black, outline=hexc("#4a4a4a"), width=0.004)
        return
    p.poly(T(catmull([(-0.074, 1.72), (-0.078, 1.83), (-0.05, 1.885), (0, 1.895), (0.05, 1.885),
                      (0.078, 1.83), (0.074, 1.72)])), black, outline=hexc("#3a3a3a"), width=0.004)
    p.poly(T(catmull([(-0.096, 1.675), (-0.1, 1.735), (-0.07, 1.772), (0, 1.782), (0.07, 1.772),
                      (0.1, 1.735), (0.096, 1.675), (0, 1.668)])), hexc("#1d1c1c"),
           outline=hexc("#3a3a3a"), width=0.004)
    p.line(T([(-0.05, 1.86), (-0.02, 1.878)]), hexc("#5a5a5a"), 0.006)
    p.line(T([(-0.08, 1.74), (-0.04, 1.765)]), hexc("#4a4a4a"), 0.005)


def _emperor_hat_front(p, T, back_first):
    if back_first:
        for s in (-1, 1):
            p.poly(T(_oval(s * 0.05, 1.855, 0.021, 0.048, -s * 14)), hexc("#b98518"), outline=GOLD_D, width=0.004)
            p.poly(T(_oval(s * 0.051, 1.86, 0.009, 0.03, -s * 14)), hexc("#e3b545"))
        return
    crown = catmull([(-0.086, 1.68), (-0.09, 1.79), (-0.06, 1.852), (0, 1.862), (0.06, 1.852),
                     (0.09, 1.79), (0.086, 1.68)])
    p.poly(T(crown), hexc("#d29f28"), outline=GOLD_D, width=0.004)
    for i in range(-4, 5):
        p.line(T([(i * 0.018, 1.7), (i * 0.02, 1.84 - abs(i) * 0.012)]), hexc("#a8771a"), 0.0025)
    for j in range(5):
        y = 1.71 + j * 0.03
        p.line(T([(-0.085 + j * 0.005, y), (0.085 - j * 0.005, y)]), hexc("#a8771a"), 0.0025)
    p.poly(T(catmull([(-0.1, 1.672), (-0.1, 1.712), (0, 1.722), (0.1, 1.712), (0.1, 1.672),
                      (0, 1.665)])), hexc("#8f5f10"), outline=GOLD_D, width=0.003)
    p.poly(T(catmull([(-0.02, 1.8), (0, 1.83), (0.02, 1.8), (0, 1.775)])), hexc("#d8322a"))
    p.ellipse(*T([(0, 1.694)])[0], 0.012, 0.012, hexc("#f4f0e0"))


# --------------------------------------------------------------------------- figures

HEAD = 1.13  # slightly enlarged heads read better at small sizes


def _head_tf(bow, drop=0.0):
    k = (1 - 0.22 * bow) * HEAD
    d = 0.055 * bow + drop

    def T(pts):
        return [(x * HEAD, 1.5 + (y - 1.5) * k - d) for x, y in pts]
    return T


def _minister_front(p, pose):
    robe = MIN_ROBE
    T = _head_tf(pose.bow)
    _minister_hat_front(p, T, back_first=True)
    _feet(p)
    _robe_body(p, robe)
    _crane_badge(p, 0, 1.2, 0.3)
    _belt(p, 0.97, 0.275, 0.07, hexc("#3a1512"), hexc("#d9c27a"))
    _collar(p, robe)
    _face(p, pose, beard="long", head_tf=T)
    _minister_hat_front(p, T, back_first=False)
    # sleeves and clasped hands holding the tablet
    lift = 0.05 * pose.bow
    for s in (-1, 1):
        sleeve = [(s * 0.2, 1.43), (s * 0.29, 1.34), (s * 0.325, 1.14 + lift), (s * 0.345, 0.86 + lift),
                  (s * 0.3, 0.74 + lift), (s * 0.17, 0.72 + lift), (s * 0.07, 0.8 + lift),
                  (s * 0.045, 1.1 + lift), (s * 0.12, 1.22 + lift), (s * 0.17, 1.33)]
        p.smooth(sleeve, shade(robe, 1.04), outline=_outline(robe), width=0.006)
        p.line(catmull([(s * 0.3, 1.2 + lift), (s * 0.28, 0.95 + lift), (s * 0.22, 0.8 + lift)], closed=False),
               shade(robe, 0.8), 0.008)
        p.ellipse(s * 0.052, 1.08 + lift, 0.035, 0.03, shade(robe, 0.6))
    hu_b, hu_t = 1.0 + lift * 1.6, 1.34 + lift * 1.6
    p.poly([(-0.036, hu_b), (0.036, hu_b), (0.03, hu_t), (0.0, hu_t + 0.012), (-0.03, hu_t)],
           hexc("#efe4c6"), outline=hexc("#a8997a"), width=0.004)
    for s in (-1, 1):
        p.ellipse(s * 0.03, 1.1 + lift, 0.034, 0.028, SKIN, outline=shade(SKIN, 0.7), width=0.003)


def _emperor_front(p, pose):
    robe = EMP_ROBE
    T = _head_tf(0.0)
    _emperor_hat_front(p, T, back_first=True)
    _feet(p)
    body = p.layer()
    body.smooth([(-0.12, 1.48), (-0.26, 1.42), (-0.28, 1.17), (-0.28, 0.95), (-0.31, 0.55), (-0.36, 0.06),
                 (0, 0.025), (0.36, 0.06), (0.31, 0.55), (0.28, 0.95), (0.28, 1.17), (0.26, 1.42),
                 (0.12, 1.48)], robe)
    _robe_body(p, robe, hem_w=0.36, waist_w=0.28, shoulder_w=0.26)
    _hem_waves(p, body)
    _dragon_roundel(p, 0, 1.2, 0.13)
    _belt(p, 0.95, 0.285, 0.06, hexc("#9e1f1a"), JADE)
    _collar(p, robe)
    _face(p, pose, beard="goatee", stern=True, head_tf=T)
    _emperor_hat_front(p, T, back_first=False)
    # arms: left one rests at the waist, right one gestures with the gesture parameter
    for s in (-1, 1):
        sleeve = [(s * 0.21, 1.44), (s * 0.3, 1.34), (s * 0.33, 1.1), (s * 0.35, 0.8), (s * 0.3, 0.64),
                  (s * 0.17, 0.62), (s * 0.08, 0.72), (s * 0.05, 0.95), (s * 0.12, 1.12), (s * 0.17, 1.3)]
        hand = (s * 0.055, 0.96)
        ang = 0.0
        if s == -1 and pose.gesture > 0:
            ang = -42 * pose.gesture
        sl = _rot(sleeve, (s * 0.22, 1.4), ang)
        lay = p.layer()
        lay.smooth(sl, shade(robe, 1.03), outline=_outline(robe), width=0.006)
        cuff = _rot([(s * 0.04, 0.7), (s * 0.3, 0.62), (s * 0.35, 0.69), (s * 0.07, 0.765)], (s * 0.22, 1.4), ang)
        lay2 = lay.layer()
        lay2.poly(cuff, hexc("#2c5f8a"))
        lay.merge(lay2, clip_to=lay)
        p.merge(lay)
        hx, hy = _rot([hand], (s * 0.22, 1.4), ang)[0]
        p.ellipse(hx, hy, 0.035, 0.03, SKIN, outline=shade(SKIN, 0.7), width=0.003)
        _dragon_roundel(p, *_rot([(s * 0.2, 1.33)], (s * 0.22, 1.4), ang)[0], 0.055)


def _back_body(p, robe, kneel, prost, badge, waves=False, hat="minister"):
    """Back view, optionally kneeling (kneel) and bowing to the ground (prost)."""
    sy = 1.45 - 0.5 * kneel - 0.42 * prost      # shoulder height
    hem = 0.34 + 0.08 * kneel + 0.04 * prost
    hump = 0.12 * prost
    head_y = sy + 0.2 - 0.42 * prost             # hat/head centre drops below the back when prostrate

    def head():
        yy = head_y - 1.65  # offset relative to the standing head
        tf = lambda pts: [(x * HEAD, 1.5 + (y - 1.5) * HEAD + yy) for x, y in pts]
        p.poly(tf([(-0.045, 1.46), (0.045, 1.46), (0.04, 1.57), (-0.04, 1.57)]), SKIN_SH)
        p.poly(tf(catmull([(-0.08, 1.56), (-0.085, 1.66), (0, 1.7), (0.085, 1.66), (0.08, 1.56),
                           (0, 1.54)])), HAIR)
        if hat == "minister":
            black = hexc("#151414")
            for s in (-1, 1):
                p.poly(tf(catmull([(s * 0.03, 1.75), (s * 0.16, 1.765), (s * 0.27, 1.792), (s * 0.35, 1.788),
                                   (s * 0.37, 1.755), (s * 0.345, 1.726), (s * 0.25, 1.73), (s * 0.14, 1.732)])),
                       black, outline=hexc("#4a4a4a"), width=0.004)
            p.poly(tf(catmull([(-0.074, 1.7), (-0.078, 1.83), (-0.05, 1.885), (0, 1.895), (0.05, 1.885),
                               (0.078, 1.83), (0.074, 1.7)])), black, outline=hexc("#3a3a3a"), width=0.004)
            p.poly(tf(catmull([(-0.098, 1.66), (-0.1, 1.74), (0, 1.76), (0.1, 1.74), (0.098, 1.66),
                               (0, 1.65)])), hexc("#1d1c1c"), outline=hexc("#3a3a3a"), width=0.004)
            p.ellipse(*tf([(0, 1.748)])[0], 0.022, 0.018, hexc("#2c2c2c"))
        else:
            crown = catmull([(-0.088, 1.66), (-0.092, 1.79), (-0.06, 1.85), (0, 1.86), (0.06, 1.85),
                             (0.092, 1.79), (0.088, 1.66)])
            p.poly(tf(crown), hexc("#c99322"), outline=GOLD_D, width=0.004)
            for i in range(-4, 5):
                p.line(tf([(i * 0.018, 1.68), (i * 0.02, 1.84 - abs(i) * 0.012)]), hexc("#a8771a"), 0.0025)

    if prost > 0.45:
        head()
    body = p.layer()
    ctrl = [(-0.12, sy + 0.02 + hump), (-0.25, sy - 0.05 + hump * 0.6), (-0.29, sy - 0.32),
            (-0.3, max(0.35, sy - 0.55)), (-hem, 0.06), (0, 0.035), (hem, 0.06),
            (0.3, max(0.35, sy - 0.55)), (0.29, sy - 0.32), (0.25, sy - 0.05 + hump * 0.6),
            (0.12, sy + 0.02 + hump)]
    body.smooth(ctrl, robe, outline=_outline(robe), width=0.006)
    if prost < 0.45:
        body.smooth([(-0.1, sy + 0.0), (-0.075, sy + 0.075), (0, sy + 0.09), (0.075, sy + 0.075), (0.1, sy + 0.0)],
                    shade(robe, 0.88), outline=_outline(robe), width=0.005)
    sh = body.layer()
    sh.poly([(0.08, 3), (0.8, 3), (0.8, -0.1), (0.14, -0.1)], shade(robe, 0.82))
    sh.line(catmull([(0.0, sy - 0.1), (0.01, sy * 0.5), (0.0, 0.05)], closed=False), shade(robe, 0.75), 0.008)
    body.merge(sh, clip_to=body)
    if waves:
        _hem_waves(body, body)
    if badge == "crane":
        _crane_badge(body, 0, sy - 0.27 + hump * 0.4, 0.3)
    elif badge == "dragon":
        _dragon_roundel(body, 0, sy - 0.25 + hump * 0.4, 0.13)
    p.merge(body)
    # hoop belt seen from behind
    by = max(0.3, sy - 0.5)
    _belt(p, by, 0.29 + 0.02 * kneel, -0.02, hexc("#3a1512") if badge == "crane" else hexc("#9e1f1a"),
          hexc("#d9c27a") if badge == "crane" else JADE)
    # sleeves hanging at the sides
    for s in (-1, 1):
        top = sy - 0.02 + hump * 0.5
        low = max(0.06, top - 0.62 + 0.15 * prost)
        sl = [(s * 0.2, top), (s * 0.3, top - 0.1), (s * 0.35, top - 0.35), (s * 0.37, low + 0.08),
              (s * 0.3, low), (s * 0.2, low + 0.02), (s * 0.24, top - 0.3)]
        p.smooth(sl, shade(robe, 0.97), outline=_outline(robe), width=0.006)
    if kneel > 0.5:
        for s in (-1, 1):
            p.smooth([(s * 0.06, 0.0), (s * 0.17, 0.0), (s * 0.17, 0.07), (s * 0.08, 0.08)], hexc("#1b1716"))
    elif not waves:
        _feet(p)
    if prost <= 0.45:
        head()


@lru_cache(maxsize=256)
def _render(who, view, key, scale):
    mouth, blink, bow, kneel, prost, gest, lx, ly = key
    pose = Pose(mouth / 5, blink, bow / 12, kneel / 16, prost / 16, gest / 12, (lx / 4, ly / 4))
    s = scale * SS
    if who == "guard":
        p = Pen(s, 1.1, 3.0, foot_m=0.05)
        _guard(p)
    else:
        p = Pen(s, 1.2, 2.15, foot_m=0.05)
        if who == "minister":
            if view == "front":
                _minister_front(p, pose)
            else:
                _back_body(p, MIN_ROBE, pose.kneel, pose.prostrate, "crane", hat="minister")
        else:
            if view == "front":
                _emperor_front(p, pose)
            else:
                _back_body(p, EMP_ROBE, 0, 0, "dragon", waves=True, hat="emperor")
    img = p.img.resize((max(1, p.w // SS), max(1, p.h // SS)), Image.LANCZOS)
    return img, (p.ox / SS, p.oy / SS)


def sprite(who, view, pose, scale, blur=0.0):
    """Return (RGBA image, (foot_x, foot_y)) for a character at `scale` px per metre."""
    img, anchor = _render(who, view, pose.key(), round(scale, 1))
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img, anchor


def _guard(p):
    armor = hexc("#7b2a1d")
    p.line([(0.22, 0.0), (0.22, 2.55)], hexc("#5a3a1a"), 0.03)
    p.poly([(0.205, 2.55), (0.235, 2.55), (0.22, 2.78)], hexc("#c9ccd0"))
    p.smooth([(0.2, 2.53), (0.26, 2.5), (0.25, 2.38), (0.22, 2.33), (0.19, 2.38), (0.18, 2.5)],
             hexc("#c7281e"))
    _feet(p)
    p.smooth([(-0.12, 1.47), (-0.24, 1.42), (-0.25, 1.0), (-0.27, 0.35), (-0.2, 0.3), (0, 0.33),
              (0.2, 0.3), (0.27, 0.35), (0.25, 1.0), (0.24, 1.42), (0.12, 1.47)], armor,
             outline=_outline(armor), width=0.008)
    p.rect(-0.14, 0.05, -0.04, 0.34, hexc("#2a2524"))
    p.rect(0.04, 0.05, 0.14, 0.34, hexc("#2a2524"))
    for j in range(8):
        y = 1.35 - j * 0.12
        p.line([(-0.22, y), (0.22, y)], hexc("#b58a3a"), 0.01)
    p.rect(-0.24, 0.9, 0.24, 0.97, hexc("#2a2524"))
    p.ellipse(0, 1.2, 0.09, 0.09, hexc("#c9ccd0"), outline=hexc("#6a6c70"), width=0.01)
    p.smooth([(0.2, 1.4), (0.3, 1.3), (0.28, 1.0), (0.22, 1.02), (0.2, 1.2)], shade(armor, 0.9))
    p.ellipse(0.22, 1.02, 0.04, 0.04, SKIN)
    p.smooth([(-0.2, 1.4), (-0.3, 1.3), (-0.28, 0.9), (-0.22, 0.92), (-0.2, 1.2)], shade(armor, 0.9))
    p.rect(-0.04, 1.44, 0.04, 1.54, SKIN_SH)
    p.smooth([(0, 1.72), (0.07, 1.7), (0.08, 1.6), (0.05, 1.52), (0, 1.5), (-0.05, 1.52), (-0.08, 1.6),
              (-0.07, 1.7)], SKIN)
    p.smooth([(-0.1, 1.64), (-0.09, 1.76), (0, 1.84), (0.09, 1.76), (0.1, 1.64), (0, 1.67)], hexc("#3b3f45"))
    p.line([(0, 1.84), (0, 1.95)], hexc("#3b3f45"), 0.02)
    p.smooth([(0, 1.95), (0.05, 1.92), (0.04, 1.84), (0, 1.86), (-0.04, 1.84), (-0.05, 1.92)], hexc("#c7281e"))
    p.line([(-0.03, 1.63), (-0.012, 1.63)], INK, 0.008)
    p.line([(0.012, 1.63), (0.03, 1.63)], INK, 0.008)
