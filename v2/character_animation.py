"""Walk, land, grab, drop. Keep the cube attached while the hands are busy."""
import math
from gltf_loader import interpolate
from math_functions import v3
from cube_logic import GridCube


class CharacterAnimation:
    def __init__(self, scene, cube=None):
        self.scene = scene
        self.cube = cube if cube is not None else GridCube()
        self.state = 'idle'
        self.time = 0.0
        self.previous_keys = set()
        self.pose = self.sample(0, 0)
        self.rest_pose = dict(self.pose)
        self.carry_pose = self.sample(1, 3.0)
        self.slam_start = None
        self.fall_duration = 0.0
        self._prepared = False
        self.apply(self.pose)

    def sample(self, clip, seconds):
        return {(node, path): interpolate(times, values, seconds, mode, path == 'rotation')
                for node, path, times, values, mode in self.scene.animations[clip]}

    def apply(self, pose):
        self.pose = pose
        for i, node in enumerate(self.scene.nodes):
            node.set_pose(pose.get((i, 'translation')), pose.get((i, 'rotation')),
                          pose.get((i, 'scale')))

    def advance_walk(self, seconds, dt):
        # keep the whole hop, just squeeze the grounded bits instead of gliding
        if seconds < 0.55:
            phase = seconds / 0.55 * 0.08
        elif seconds < 1.35:
            phase = 0.08 + seconds - 0.55
        else:
            phase = 0.88 + (seconds - 1.35) / 0.85 * 0.08

        phase = (phase + dt) % 0.96
        if phase < 0.08:
            return phase / 0.08 * 0.55
        if phase < 0.88:
            return 0.55 + phase - 0.08
        return 1.35 + (phase - 0.88) / 0.08 * 0.85

    def carry_motion(self, pose):
        if not self.cube.held:
            return pose

        def multiply(a, b):
            x, y, z, w = a
            X, Y, Z, W = b
            return (w*X + x*W + y*Z - z*Y,
                    w*Y - x*Z + y*W + z*X,
                    w*Z + x*Y - y*X + z*W,
                    w*W - x*X - y*Y - z*Z)

        result = dict(pose)
        # add the old arm motion onto the holding pose, only fingers stay locked
        for joint in range(1, 8):
            key = (joint, 'rotation')
            if joint >= 4:
                result[key] = self.carry_pose[key]
            else:
                x, y, z, w = self.rest_pose[key]
                delta = multiply((-x, -y, -z, w), pose[key])
                result[key] = multiply(self.carry_pose[key], delta)
        return result

    def prepare(self, player, keys):
        # called before moving, so snapping doesnt get undone by the same keypress
        pressed = keys - self.previous_keys
        self.previous_keys = set(keys)
        self._prepared = True

        if 'r' in keys:
            self.cube.reset()
            self.state, self.time = 'idle', 0.0
        elif 'e' in pressed and self.state not in ('pickup', 'drop'):
            action = self.cube.request(player)
            if action:
                self.state, self.time = action, 0.0

        if self.state in ('pickup', 'drop'):
            player.move = v3()
            player.vel_y = 0.0

    def start_slam(self):
        self.slam_start = dict(self.pose)
        height = self.slam_start.get((0, 'translation'), (0, 0, 0))[1]
        self.fall_duration = math.sqrt(max(0.0, 2 * height / 18))
        self.state, self.time = 'slam', 0.0

    def slam_pose(self):
        height = self.slam_start.get((0, 'translation'), (0, 0, 0))[1]
        impact_end = self.fall_duration + 0.12
        if self.time <= impact_end:
            target = self.carry_motion(self.sample(3, 0.44))
            blend = min(1.0, self.time / max(impact_end, 0.001))
            pose = dict(target)
            for key in target:
                if key[1] == 'rotation':
                    pose[key] = interpolate([0, 1], [self.slam_start[key], target[key]],
                                            blend, 'LINEAR', True)
            pose[0, 'translation'] = (0, max(0.0, height - 9 * self.time**2), 0)
            return pose
        return self.carry_motion(self.sample(3, min(0.85, 0.44 + self.time - impact_end)))

    def update(self, player, keys, dt):
        if not self._prepared:
            self.prepare(player, keys)
        self._prepared = False
        moving = player.move.x**2 + player.move.z**2 > 0.0001
        airborne = not player.ci.grounded and (abs(player.vel_y) > 0.5 or self.state == 'air')

        if self.state in ('pickup', 'drop'):
            self.time += dt
            self.cube.advance(self.state, self.time)
            duration = 3.0 if self.state == 'pickup' else 2.3
            pose = self.sample(1 if self.state == 'pickup' else 2, min(self.time, duration))
            self.apply(pose)
            if self.time >= duration:
                self.state, self.time = 'idle', 0.0
            return

        if airborne:
            if self.state != 'air':
                self.state, self.time = 'air', 0.55
            self.time = min(1.35, self.time + dt * 0.8)
        elif self.state == 'air' or (self.state == 'move' and not moving):
            self.start_slam()
        elif self.state == 'slam':
            self.time += dt
            if self.time >= self.fall_duration + 0.53:
                self.state, self.time = 'idle', 0.0
        elif moving:
            if self.state != 'move':
                self.state, self.time = 'move', 0.0
            self.time = self.advance_walk(self.time, dt * (1.5 if player.speed > 6 else 1))
        else:
            self.state, self.time = 'idle', 0.0

        if self.state == 'slam':
            pose = self.slam_pose()
        else:
            pose = self.carry_motion(self.sample(0, self.time))

        if self.state == 'air':
            # physics already lifts us, this fucking thing jumped twice with both lifts on
            pose[0, 'translation'] = (0, 0, 0)
        self.apply(pose)
