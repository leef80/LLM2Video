"""Minimal pinhole camera + painter's-algorithm helpers.

World axes: x to the right, y up, z pointing from the courtyard toward the hall.
Units are metres.
"""
import math

import numpy as np

NEAR = 0.15


def _norm(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


class Camera:
    def __init__(self, pos, target, fov_deg, size, roll_deg=0.0):
        self.pos = np.asarray(pos, dtype=float)
        self.size = size
        w, h = size
        f = _norm(np.asarray(target, dtype=float) - self.pos)
        up = np.array([0.0, 1.0, 0.0])
        r = _norm(np.cross(up, f))
        u = np.cross(f, r)
        if roll_deg:
            a = math.radians(roll_deg)
            r, u = r * math.cos(a) + u * math.sin(a), -r * math.sin(a) + u * math.cos(a)
        self.f, self.r, self.u = f, r, u
        self.focal = (h / 2) / math.tan(math.radians(fov_deg) / 2)
        self.cx, self.cy = w / 2, h / 2

    def to_cam(self, pts):
        d = np.asarray(pts, dtype=float) - self.pos
        return np.stack([d @ self.r, d @ self.u, d @ self.f], axis=-1)

    def cam_to_screen(self, c):
        c = np.asarray(c, dtype=float)
        z = c[..., 2]
        x = self.cx + self.focal * c[..., 0] / z
        y = self.cy - self.focal * c[..., 1] / z
        return np.stack([x, y], axis=-1)

    def project(self, pts):
        return self.cam_to_screen(self.to_cam(pts))

    def depth(self, p):
        return float((np.asarray(p, dtype=float) - self.pos) @ self.f)

    def scale_at(self, p):
        """Pixels per metre for an object at world point p."""
        return self.focal / max(self.depth(p), NEAR)

    def facing(self, point, normal):
        return float(np.dot(self.pos - np.asarray(point, dtype=float), normal)) > 0

    def project_poly(self, pts):
        """Project a planar polygon, clipping it against the near plane.

        Returns a list of (x, y) tuples or None when fully behind the camera.
        """
        c = self.to_cam(pts)
        out = []
        n = len(c)
        for i in range(n):
            a, b = c[i], c[(i + 1) % n]
            ina, inb = a[2] >= NEAR, b[2] >= NEAR
            if ina:
                out.append(a)
            if ina != inb:
                t = (NEAR - a[2]) / (b[2] - a[2])
                out.append(a + t * (b - a))
        if len(out) < 3:
            return None
        s = self.cam_to_screen(np.array(out))
        return [tuple(p) for p in s]


def homography(src, dst):
    """3x3 matrix H with dst ~ H @ src for four point pairs."""
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(a, dtype=float))
    hm = vt[-1].reshape(3, 3)
    return hm / hm[2, 2]
