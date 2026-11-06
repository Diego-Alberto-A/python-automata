"""Independent spectator camera, without a player or ground collision."""
import math
from engine_3d import camera
from math_functions import v3, look_at, perspective, normalizado_vector
from simulation_view import CELL_SIZE


class FreeCamera(camera):
    def __init__(self, size):
        super().__init__()
        self.size = size
        self.reset()

    def reset(self):
        span = self.size * CELL_SIZE
        self.position = v3(0, span * .8, -span * .8)
        self.yaw, self.pitch = 0., -math.pi / 4
        self.update_basis()

    def update(self, keys, dt, width, height):
        self.yaw += (('left' in keys) - ('right' in keys)) * dt * 1.4
        self.pitch = max(-1.5, min(1.5, self.pitch +
                         (('up' in keys) - ('down' in keys)) * dt * 1.4))
        self.update_basis()
        # look_at uses forward cross up as screen-right in this renderer.
        direction = self.fwd * (('w' in keys) - ('s' in keys))
        direction += self.rgt * (('a' in keys) - ('d' in keys))
        direction += v3(0, ('e' in keys) - ('q' in keys), 0)
        speed = max(8., self.size * .7)
        self.position += normalizado_vector(direction) * speed * dt
        self.view = look_at(self.position, self.position + self.fwd, v3(0, 1, 0))
        self.proj = perspective(math.radians(60), width / max(1, height), .1,
                                max(1000., self.size * CELL_SIZE * 10))
