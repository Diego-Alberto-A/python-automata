"""Endless unit squares at Y=0, just calculated lines, no floor mesh."""
import math
from math_functions import v3, mult_ma, transform4


class GridFloor:
    floor_height = 0.0
    spawn = v3(0, 0, 0)

    @property
    def collision(self):
        return self

    def camera_position(self, target, desired):
        return desired

    def draw(self, renderer, view, projection, mode='edges'):
        x = -(view[0] * view[12] + view[1] * view[13] + view[2] * view[14])
        z = -(view[8] * view[12] + view[9] * view[13] + view[10] * view[14])
        cx, cz = math.floor(x), math.floor(z)
        vp = mult_ma(projection, view)
        radius = 35

        for i in range(-radius, radius + 1):
            fade = min(1.0, (radius - abs(i)) / 10)
            color = (int(22 + 30 * fade), int(26 + 42 * fade), int(31 + 50 * fade))
            segments = [((cx + i, 0, cz - radius, 1), (cx + i, 0, cz + radius, 1)),
                        ((cx - radius, 0, cz + i, 1), (cx + radius, 0, cz + i, 1))]
            for a, b in segments:
                renderer.line(transform4(vp, a), transform4(vp, b), color)
