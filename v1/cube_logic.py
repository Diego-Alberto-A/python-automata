"""One cube, either sat in a square or attached to the claw. Thats the whole deal."""
import math
from math_functions import v3, translate, rotate_y, scale, mult_ma
from models import map_mesh, model


CLAW_SCALE = 0.8
REACH = 1.25 * CLAW_SCALE
GRIP_Y = -(0.16 + 0.32 * math.cos(math.radians(15)) + 0.235)
CUBE_LOCAL_SIZE = 2 * (0.22 - 0.32 * math.sin(math.radians(15)) - 0.055)
CUBE_SIZE = CUBE_LOCAL_SIZE * CLAW_SCALE
FLOOR_WRIST = -GRIP_Y + CUBE_LOCAL_SIZE / 2


def grid_cell(position):
    # floor, not int: -0.2 belongs to square -1, not square 0
    return math.floor(position.x), math.floor(position.z)


def cell_center(cell, height=0.0):
    return v3(cell[0] + 0.5, height, cell[1] + 0.5)


def player_matrix(player):
    return mult_ma(translate(player.physical.position),
                   mult_ma(rotate_y(player.yaw - math.pi / 2), scale(CLAW_SCALE)))


class GridCube:
    def __init__(self):
        self.cell = (0, 0)
        self.held = False
        self.drop_cell = None
        points = [(x, y, z) for x in (-0.5, 0.5)
                  for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
        indices = [0,1,3,0,3,2, 4,6,7,4,7,5, 0,4,5,0,5,1,
                   2,3,7,2,7,6, 0,2,6,0,6,4, 1,5,7,1,7,3]
        vertices = [value for p in points for value in (*p, 0, 1, 0, 0, 0)]
        mesh = map_mesh(vertices, indices=indices, color=(70, 230, 195))
        mesh.rebuild()
        self.model = model('grid_cube', mesh)

    def reset(self):
        self.cell = (0, 0)
        self.held = False
        self.drop_cell = None

    def can_grab(self, player):
        return not self.held and grid_cell(player.physical.position) == self.cell

    def snap(self, player, cell):
        center = cell_center(cell, player.physical.position.y)
        delta = center - player.physical.position
        if abs(delta.x) + abs(delta.z) < 1e-8:
            delta = v3(math.sin(player.yaw), 0, math.cos(player.yaw))

        if abs(delta.x) > abs(delta.z):
            forward = v3(1 if delta.x > 0 else -1, 0, 0)
        else:
            forward = v3(0, 0, 1 if delta.z >= 0 else -1)

        # base sits one reach away, so the jaws meet the square's exact middle
        player.physical.position = center - forward * REACH
        player.yaw = math.atan2(forward.x, forward.z)
        player.move = v3()
        player.vel_y = 0.0

    def request(self, player):
        if not player.ci.grounded:
            return None
        if self.held:
            self.drop_cell = grid_cell(player.physical.position)
            self.snap(player, self.drop_cell)
            return 'drop'
        if self.can_grab(player):
            self.snap(player, self.cell)
            return 'pickup'
        return None

    def advance(self, state, seconds):
        if state == 'pickup' and seconds >= 1.9 and not self.held:
            self.held = True
            self.cell = None
        elif state == 'drop' and seconds >= 1.0 and self.held:
            self.cell = self.drop_cell
            self.drop_cell = None
            self.held = False

    def matrix(self, player, scene):
        if self.held:
            wrist = scene.nodes[3].machine.collapse()
            grip = mult_ma(wrist, translate(v3(0, GRIP_Y, 0)))
            return mult_ma(player_matrix(player), mult_ma(grip, scale(CUBE_LOCAL_SIZE)))
        return mult_ma(translate(cell_center(self.cell, CUBE_SIZE / 2)), scale(CUBE_SIZE))
