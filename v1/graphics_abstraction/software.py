"""Dibujado por puntos, Bresenham handles the triangle edges.
Clip before dividing by w, depth buffer sorts overlapping pixels.
Still wireframe, so faces dont hide the lines behind them.
"""
import math
from math_functions import transform4, mult_ma


def bresenham(x0, y0, x1, y1):
    dx, dy = (abs(x1 - x0), -abs(y1 - y0))
    sx, sy = (1 if x0 < x1 else -1, 1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        yield (x0, y0)
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def clip_line(a, b):
    """Keep x/y/z inside -w..w, and w positive, before the divide."""
    if not all((math.isfinite(v) for v in (*a, *b))):
        return None
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    da = (aw + ax, aw - ax, aw + ay, aw - ay, aw + az, aw - az, aw - 1e-08)
    db = (bw + bx, bw - bx, bw + by, bw - by, bw + bz, bw - bz, bw - 1e-08)
    if min(da) >= 0 and min(db) >= 0:
        return (a, b)
    lo, hi = (0.0, 1.0)
    for fa, fb in zip(da, db):
        if fa < 0 and fb < 0:
            return None
        if fa < 0:
            lo = max(lo, fa / (fa - fb))
        elif fb < 0:
            hi = min(hi, fa / (fa - fb))
        if lo > hi:
            return None
    return (tuple((a[i] + (b[i] - a[i]) * lo for i in range(4))), tuple((a[i] + (b[i] - a[i]) * hi for i in range(4))))


class SoftwareRenderer:

    def __init__(self, width, height):
        self.resize(width, height)

    def resize(self, width, height):
        if width < 1 or height < 1:
            raise ValueError('Framebuffer dimensions must be positive')
        self.width, self.height = (width, height)
        self.pixels = bytearray(width * height * 3)
        self.depth = [math.inf] * (width * height)
        self.points_drawn = 0

    def clear(self, color=(15, 18, 23)):
        self.pixels[:] = bytes(color) * (self.width * self.height)
        self.depth[:] = [math.inf] * (self.width * self.height)
        self.points_drawn = 0

    def point(self, x, y, z, color):
        if 0 <= x < self.width and 0 <= y < self.height and (-1.000001 <= z <= 1.000001):
            index = y * self.width + x
            if z <= self.depth[index]:
                self.depth[index] = z
                self.pixels[index * 3:index * 3 + 3] = bytes(color)
                self.points_drawn += 1

    def line(self, a, b, color):
        clipped = clip_line(a, b)
        if clipped is None:
            return
        a, b = clipped

        def project(p):
            return (round((p[0] / p[3] * 0.5 + 0.5) * (self.width - 1)), round((0.5 - p[1] / p[3] * 0.5) * (self.height - 1)), p[2] / p[3])
        x0, y0, z0 = project(a)
        x1, y1, z1 = project(b)
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i, (x, y) in enumerate(bresenham(x0, y0, x1, y1)):
            self.point(x, y, z0 + (z1 - z0) * (i / steps if steps else 0), color)

    def draw_mesh(self, mesh, model, view, projection, positions=None, color=None, mode='edges'):
        if mode not in ('edges', 'points'):
            raise ValueError('Drawing mode must be edges or points')
        mvp = mult_ma(projection, mult_ma(view, model))
        positions = mesh.positions() if positions is None else positions
        projected = [transform4(mvp, (p.x, p.y, p.z, 1.0)) for p in positions]
        color = mesh.color if color is None else color
        if mode == 'points':
            for p in projected:
                if clip_line(p, p):
                    self.line(p, p, color)
            return
        for a, b in mesh.edges():
            self.line(projected[a], projected[b], color)

    def save_ppm(self, path):
        with open(path, 'wb') as file:
            file.write(f'P6\n{self.width} {self.height}\n255\n'.encode())
            file.write(self.pixels)
