"""Small 2D drawing helpers on top of Pillow."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def catmull(pts, closed=True, n=8):
    """Catmull-Rom spline through control points -> dense polyline."""
    p = [np.asarray(q, dtype=float) for q in pts]
    m = len(p)
    out = []
    rng = range(m) if closed else range(m - 1)
    for i in rng:
        p0 = p[(i - 1) % m] if closed or i > 0 else p[0]
        p1 = p[i]
        p2 = p[(i + 1) % m]
        p3 = p[(i + 2) % m] if closed or i + 2 < m else p[-1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(tuple(q))
    if not closed:
        out.append(tuple(p[-1]))
    return out


def bez(p0, p1, p2, p3, n=16):
    out = []
    for k in range(n + 1):
        t = k / n
        a = (1 - t) ** 3
        b = 3 * (1 - t) ** 2 * t
        c = 3 * (1 - t) * t * t
        d = t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


class Pen:
    """Draw in metres on a sprite canvas.  Origin at the feet, y up."""

    def __init__(self, scale, width_m, height_m, foot_m=0.05, mirror=False):
        self.s = scale
        self.w = max(4, int(width_m * scale))
        self.h = max(4, int(height_m * scale))
        self.ox = self.w / 2
        self.oy = self.h - foot_m * scale
        self.mirror = mirror
        self.img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def P(self, x, y):
        if self.mirror:
            x = -x
        return (self.ox + x * self.s, self.oy - y * self.s)

    def pts(self, pts):
        return [self.P(x, y) for x, y in pts]

    def poly(self, pts, fill, outline=None, width=0.0):
        q = self.pts(pts)
        self.d.polygon(q, fill=fill)
        if outline is not None and width > 0:
            self.d.line(q + [q[0]], fill=outline, width=max(1, int(width * self.s)), joint="curve")

    def smooth(self, ctrl, fill, closed=True, n=8, outline=None, width=0.0):
        self.poly(catmull(ctrl, closed, n), fill, outline, width)

    def line(self, pts, fill, width):
        q = self.pts(pts)
        self.d.line(q, fill=fill, width=max(1, int(round(width * self.s))), joint="curve")

    def ellipse(self, cx, cy, rx, ry, fill, outline=None, width=0.0):
        x0, y0 = self.P(cx - rx, cy + ry)
        x1, y1 = self.P(cx + rx, cy - ry)
        if x0 > x1:
            x0, x1 = x1, x0
        self.d.ellipse([x0, y0, x1, y1], fill=fill, outline=outline,
                       width=max(1, int(width * self.s)) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill)

    def layer(self):
        """Fresh transparent layer of the same size, sharing the transform."""
        p = Pen.__new__(Pen)
        p.__dict__.update(self.__dict__)
        p.img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        p.d = ImageDraw.Draw(p.img)
        return p

    def merge(self, other, clip_to=None):
        """Composite another layer on top; optionally clip it to an alpha mask layer."""
        top = other.img
        if clip_to is not None:
            a = np.minimum(np.asarray(top)[..., 3], np.asarray(clip_to.img)[..., 3]).astype(np.uint8)
            top = top.copy()
            top.putalpha(Image.fromarray(a))
        self.img.alpha_composite(top)


def vgradient(size, stops):
    """Vertical gradient; stops = [(t, rgb), ...] with t in 0..1 from top."""
    w, h = size
    t = np.linspace(0, 1, h)
    ts = [s[0] for s in stops]
    ch = []
    for c in range(3):
        ch.append(np.interp(t, ts, [s[1][c] for s in stops]))
    col = np.stack(ch, axis=-1)
    arr = np.repeat(col[:, None, :], w, axis=1)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")


def noise_texture(size, scale=1.0, seed=0, amp=0.12):
    """Multiplicative value-noise (1 +- amp) as float array HxW."""
    rng = np.random.default_rng(seed)
    w, h = size
    acc = np.zeros((h, w))
    tot = 0
    for octave, weight in ((64, 0.5), (16, 0.3), (4, 0.2)):
        s = max(1, int(octave * scale))
        small = rng.random((h // s + 2, w // s + 2))
        img = Image.fromarray((small * 255).astype(np.uint8)).resize(
            ((w // s + 2) * s, (h // s + 2) * s), Image.BICUBIC)
        acc += np.asarray(img, dtype=float)[:h, :w] / 255 * weight
        tot += weight
    acc /= tot
    return 1 + (acc - 0.5) * 2 * amp


def soft_blob(rx, ry, color, blur):
    w, h = int(rx * 2 + blur * 4), int(ry * 2 + blur * 4)
    im = Image.new("RGBA", (w, h), color[:3] + (0,))
    d = ImageDraw.Draw(im)
    d.ellipse([w / 2 - rx, h / 2 - ry, w / 2 + rx, h / 2 + ry], fill=color)
    return im.filter(ImageFilter.GaussianBlur(blur))


