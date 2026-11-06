"""Small math helpers, no extra libraries.
Matrices kept column-major like before, still all CPU work though.
"""
from dataclasses import dataclass
from enum import Enum, auto
import math


@dataclass(frozen=True)
class vec3f:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, b):
        return vec3f(self.x + b.x, self.y + b.y, self.z + b.z)

    def __sub__(self, b):
        return vec3f(self.x - b.x, self.y - b.y, self.z - b.z)

    def __mul__(self, s):
        return vec3f(self.x * s, self.y * s, self.z * s)

    def sqr_length(self):
        return dot_product(self, self)

    def length(self):
        return math.sqrt(self.sqr_length())
v3 = vec3f
mat4 = tuple


def basic_add(a, b):
    return a + b


def basic_sub(a, b):
    return a - b


def basic_mult(a, s):
    return a * s


def dot_product(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def cross_product(a, b):
    return v3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def normalizado_vector(v):
    return v * (1 / math.sqrt(max(1e-12, v.sqr_length())))


def clampf(x, a, b):
    return max(a, min(b, x))


def normalize_angle(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def identity_matrix():
    return (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def mult_ma(a, b):
    return tuple((sum((a[k * 4 + r] * b[c * 4 + k] for k in range(4))) for c in range(4) for r in range(4)))


def transform4(m, p):
    x, y, z, w = p
    return (m[0] * x + m[4] * y + m[8] * z + m[12] * w, m[1] * x + m[5] * y + m[9] * z + m[13] * w, m[2] * x + m[6] * y + m[10] * z + m[14] * w, m[3] * x + m[7] * y + m[11] * z + m[15] * w)


def transform_point(m, p):
    q = transform4(m, (p.x, p.y, p.z, 1.0))
    return v3(*q[:3])


def translate(t):
    m = list(identity_matrix())
    m[12:15] = (t.x, t.y, t.z)
    return tuple(m)


def scale(s):
    if isinstance(s, (int, float)):
        s = v3(s, s, s)
    return (s.x, 0.0, 0.0, 0.0, 0.0, s.y, 0.0, 0.0, 0.0, 0.0, s.z, 0.0, 0.0, 0.0, 0.0, 1.0)


def quaternion_matrix(q):
    length = math.sqrt(sum((x * x for x in q)))
    if length < 1e-12:
        return identity_matrix()
    x, y, z, w = (v / length for v in q)
    return (1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w), 0.0, 2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w), 0.0, 2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y), 0.0, 0.0, 0.0, 0.0, 1.0)


def rotate_y(a):
    return quaternion_matrix((0.0, math.sin(a / 2), 0.0, math.cos(a / 2)))


def compose(t, r, s):
    return mult_ma(translate(t), mult_ma(quaternion_matrix(r), scale(s)))


def perspective(fovy, aspect, zn, zf):
    f = 1 / math.tan(fovy / 2)
    return (f / aspect, 0.0, 0.0, 0.0, 0.0, f, 0.0, 0.0, 0.0, 0.0, (zf + zn) / (zn - zf), -1.0, 0.0, 0.0, 2 * zf * zn / (zn - zf), 0.0)


def look_at(eye, at, up):
    f = normalizado_vector(at - eye)
    s = normalizado_vector(cross_product(f, up))
    u = cross_product(s, f)
    return (s.x, u.x, -f.x, 0.0, s.y, u.y, -f.y, 0.0, s.z, u.z, -f.z, 0.0, -dot_product(s, eye), -dot_product(u, eye), dot_product(f, eye), 1.0)


class MatrixState(Enum):
    DIRTY = auto()
    COLLAPSED = auto()


class ModelingMachine:
    """Declaration of modeling operations through a cached matrix, no mult on reuse.

    (operations on tuples, set_operations as mutation path, parent revision lets
    the hierarchy invalidate descendants lazily-ish, kinda)
    """

    def __init__(self):
        self.operations = ()
        self.state = MatrixState.DIRTY
        self.matrix = identity_matrix()
        self.revision = 0
        self._parent_key = None
        self.parent = None

    def set_operations(self, *operations):
        operations = tuple((tuple(m) for m in operations))
        if operations != self.operations:
            self.operations = operations
            self.state = MatrixState.DIRTY

    def collapse(self, parent=None):
        if parent is not None:
            self.parent = parent
        parent = self.parent
        parent_matrix = parent.collapse() if parent else identity_matrix()
        key = (id(parent), parent.revision) if parent else None
        if self.state is MatrixState.DIRTY or key != self._parent_key:
            result = parent_matrix
            for operation in self.operations:
                result = mult_ma(result, operation)
            self.matrix = result
            self._parent_key = key
            self.revision += 1
            self.state = MatrixState.COLLAPSED
        return self.matrix


def closest_point_on_triangle(p, a, b, c):
    ab, ac, ap = (b - a, c - a, p - a)
    d1, d2 = (dot_product(ab, ap), dot_product(ac, ap))
    if d1 <= 0 and d2 <= 0:
        return a
    bp = p - b
    d3, d4 = (dot_product(ab, bp), dot_product(ac, bp))
    if d3 >= 0 and d4 <= d3:
        return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and (d3 <= 0):
        return a + ab * (d1 / (d1 - d3))
    cp = p - c
    d5, d6 = (dot_product(ab, cp), dot_product(ac, cp))
    if d6 >= 0 and d5 <= d6:
        return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and (d6 <= 0):
        return a + ac * (d2 / (d2 - d6))
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and (d5 - d6 >= 0):
        return b + (c - b) * ((d4 - d3) / (d4 - d3 + (d5 - d6)))
    denom = va + vb + vc
    if abs(denom) < 1e-12:
        return a
    return a + ab * (vb / denom) + ac * (vc / denom)
