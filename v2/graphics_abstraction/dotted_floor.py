"""Floor at Y=0, dots stuck to world positions.
No mesh or floor boundary, just calculate the nearby dots each frame.
"""
import math
from math_functions import v3, mult_ma, transform4


class DottedFloor:
    floor_height = 0.0
    spawn = v3(0, 0, 0)

    @property
    def collision(self):
        return self

    def camera_position(self, target, desired):
        return desired

    def draw(self, renderer, view, projection, mode='edges'):
        # get camera X/Z back from the view matrix, then dot the nearby ground
        x = -(view[0] * view[12] + view[1] * view[13] + view[2] * view[14])
        z = -(view[8] * view[12] + view[9] * view[13] + view[10] * view[14])
        center_x, center_z = (math.floor(x), math.floor(z))
        vp = mult_ma(projection, view)
        radius = 45
        for gx in range(center_x - radius, center_x + radius + 1):
            for gz in range(center_z - radius, center_z + radius + 1):
                distance = math.hypot(gx - x, gz - z)
                if distance >= radius:
                    continue
                px, py, pz, w = transform4(vp, (gx, self.floor_height, gz, 1))
                if w <= 0 or abs(px) > w or abs(py) > w or (abs(pz) > w):
                    continue
                sx = round((px / w * 0.5 + 0.5) * (renderer.width - 1))
                sy = round((0.5 - py / w * 0.5) * (renderer.height - 1))
                fade = min(1.0, (radius - distance) / 15)
                color = (int(15 + 90 * fade), int(18 + 115 * fade), int(23 + 130 * fade))
                renderer.point(sx, sy, pz / w, color)
