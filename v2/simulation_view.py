"""Cell-aligned 3D playback; decisions always belong to automata.py."""
import copy
import math
from types import SimpleNamespace
from character_animation import CharacterAnimation
from cube_logic import GridCube, REACH, CUBE_SIZE, player_matrix
from math_functions import v3, translate, scale, mult_ma, transform4
from renderer_handler import Draw3D, DrawScene

CELL_SIZE = 3.0
COLORS = ((95, 220, 255), (255, 140, 100), (195, 145, 255),
          (255, 215, 90), (100, 240, 160), (255, 130, 205), (160, 190, 255))


def cell_center(cell, size):
    row, column = cell
    return v3((column + .5 - size / 2) * CELL_SIZE, 0,
              (row + .5 - size / 2) * CELL_SIZE)


def line(renderer, vp, a, b, color):
    renderer.line(transform4(vp, (*a, 1)), transform4(vp, (*b, 1)), color)


def square(renderer, vp, center, radius, color, height=.025):
    x, z = center.x, center.z
    points = [(x-radius, height, z-radius), (x+radius, height, z-radius),
              (x+radius, height, z+radius), (x-radius, height, z+radius)]
    for a, b in zip(points, points[1:] + points[:1]):
        line(renderer, vp, a, b, color)


class ClawView:
    def __init__(self, scene, robot, size):
        self.scene = copy.deepcopy(scene)
        self.cube = GridCube()
        self.animation = CharacterAnimation(self.scene, self.cube)
        self.player = SimpleNamespace(physical=SimpleNamespace(position=v3()), yaw=0.)
        self.center = cell_center(robot.posicion(), size)
        self.before = self.after = (robot.posicion(), robot.cargando)
        self.color = COLORS[robot.indice % len(COLORS)]
        self.size = size
        self.drop_clock = None
        self.drop_duration = 4.
        self.update(1.)

    def begin(self, before, after):
        self.before, self.after = before, after
        if before[1] and not after[1]:
            self.drop_clock = -.4 if before[0] != after[0] else 0.
        delta = cell_center(after[0], self.size) - cell_center(before[0], self.size)
        if delta.length() > 0:
            self.player.yaw = math.atan2(delta.x, delta.z)

    def update(self, progress):
        self._drawables = None
        before, after = self.before, self.after
        moving = before[0] != after[0]
        pickup = not before[1] and after[1]
        drop = before[1] and not after[1]
        movement_end = .4 if moving and (pickup or drop) else 1.
        travel = min(1., progress / movement_end) if moving else 1.
        start, end = cell_center(before[0], self.size), cell_center(after[0], self.size)
        self.center = start + (end - start) * travel
        forward = v3(math.sin(self.player.yaw), 0, math.cos(self.player.yaw))
        self.player.physical.position = self.center - forward * REACH
        action = max(0., (progress - (movement_end if moving else 0.)) /
                     (1. - movement_end if moving and (pickup or drop) else 1.))
        self.cube.held = before[1]
        if pickup and (not moving or progress >= movement_end):
            seconds = action * 3.
            self.cube.held = seconds >= 1.9
            pose = self.animation.sample(1, seconds)
        elif moving and progress < movement_end:
            pose = self.animation.carry_motion(self.animation.sample(0, travel * 2.2))
        else:
            self.cube.held = after[1]
            pose = self.animation.carry_motion(self.animation.sample(0, 0))
        self.animation.apply(pose)
        self.ground_cube = pickup and not self.cube.held

    def advance_drop(self, turns):
        if self.drop_clock is None:
            return
        self.drop_clock += turns
        if self.drop_clock < 0:
            return
        seconds = min(2.3, self.drop_clock / self.drop_duration * 2.3)
        self.cube.held = seconds < 1.
        self.animation.apply(self.animation.sample(2, seconds))
        self._drawables = None
        if seconds >= 2.3:
            self.drop_clock = None

    def draw(self, renderer, camera, mode):
        if self._drawables is None:
            self._drawables = list(self.scene.drawables())
        matrix = player_matrix(self.player)
        for mesh, positions in self._drawables:
            renderer.draw_mesh(mesh, matrix, camera.view, camera.proj, positions, mode=mode)
        if self.cube.held:
            Draw3D(renderer, self.cube.matrix(self.player, self.scene), camera.proj,
                   camera.view, self.cube.model.buffer, mode=mode)
        elif self.ground_cube:
            draw_cube(renderer, camera, self.cube, cell_center(self.after[0], self.size), mode)
        square(renderer, mult_ma(camera.proj, camera.view), self.center, 1.25, self.color)


def draw_cube(renderer, camera, cube, center, mode, hidden=False):
    matrix = mult_ma(translate(center + v3(0, CUBE_SIZE / 2, 0)), scale(CUBE_SIZE))
    color = (255, 65, 65) if hidden else None
    renderer.draw_mesh(cube.model.buffer.mesh, matrix, camera.view, camera.proj, color=color, mode=mode)
    square(renderer, mult_ma(camera.proj, camera.view), center, .28, color or (255, 205, 80))


class SimulationView:
    def __init__(self, model, scene, optimize=True):
        if optimize:
            from graphics_abstraction.wire_geometry import compact_scene
            scene = compact_scene(scene)
        self.model = model
        self.claws = [ClawView(scene, r, model.p.tamano) for r in model.robots]
        for claw in self.claws:
            claw.drop_duration = min(4., max(.6, len(self.claws) - 1.4))
        self.cube = GridCube()
        self.active = None
        self.elapsed = 0.
        self.show_hidden = True

    def update(self, dt, turns_per_second):
        remaining = dt * turns_per_second
        while remaining > 1e-9:
            if self.active is None:
                event = self.model.advance_agent()
                if event is None:
                    for claw in self.claws:
                        claw.advance_drop(remaining)
                    self.elapsed = 0.
                    return
                index, before, after = event
                self.active = self.claws[index]
                self.active.begin(before, after)
            chunk = min(remaining, 1. - self.elapsed)
            self.elapsed += chunk
            remaining -= chunk
            self.active.update(min(1., self.elapsed))
            for claw in self.claws:
                claw.advance_drop(chunk)
            if self.elapsed < 1.:
                return
            self.elapsed = 0.
            self.active = None

    def draw(self, renderer, camera, mode):
        n = self.model.p.tamano
        vp = mult_ma(camera.proj, camera.view)
        half = n * CELL_SIZE / 2
        for i in range(n + 1):
            offset = i * CELL_SIZE - half
            color = (100, 140, 165) if i in (0, n) else (40, 60, 75)
            line(renderer, vp, (offset, 0, -half), (offset, 0, half), color)
            line(renderer, vp, (-half, 0, offset), (half, 0, offset), color)
        visible = set().union(*(r.vistas for r in self.model.robots))
        for cell in visible:
            center = cell_center(cell, n)
            # Small discovery mark leaves the floor grid legible.
            line(renderer, vp, (center.x-.12, .01, center.z),
                 (center.x+.12, .01, center.z), (65, 100, 115))
        square(renderer, vp, cell_center(self.model.deposito, n), 1.45, (90, 255, 130))
        known = set().union(*(r.cubos_conocidos for r in self.model.robots))
        for cell in self.model.cubos if self.show_hidden else self.model.cubos & known:
            draw_cube(renderer, camera, self.cube, cell_center(cell, n), mode, hidden=cell not in known)
        for claw in self.claws:
            claw.draw(renderer, camera, mode)
