"""Grab from a square, carry it, put it back in a square. No loose cube positions."""
import math
from pathlib import Path
import unittest
from character_animation import CharacterAnimation
from cube_logic import GridCube, grid_cell, CUBE_SIZE, player_matrix
from engine_3d import camera
from game_logic import player, polling_based_inputs, move_player
from gltf_loader import load_gltf
from graphics_abstraction.grid_floor import GridFloor
from math_functions import v3

ROOT = Path(__file__).resolve().parents[1]


class CubeTests(unittest.TestCase):
    def setUp(self):
        self.player = player()
        self.player.physical.position = v3(.2, 0, .5)
        self.player.intial_position = v3(0, 0, 0)
        self.player.ci.grounded = True
        self.cube = GridCube()
        self.scene = load_gltf(ROOT/'assets/characters/claw_lamp.glb')
        self.animation = CharacterAnimation(self.scene, self.cube)
        self.camera = camera()
        self.floor = GridFloor()

    def tick(self, keys=set(), frames=1):
        for _ in range(frames):
            polling_based_inputs(self.player, self.camera, 1/60, keys)
            self.animation.prepare(self.player, keys)
            move_player(self.player, self.floor, 1/60)
            self.animation.update(self.player, keys, 1/60)

    def test_cell_boundaries_and_invalid_pickup(self):
        self.assertEqual(grid_cell(v3(-.01, 0, -.01)), (-1,-1))
        self.assertEqual(grid_cell(v3(.999, 0, .999)), (0,0))
        self.assertEqual(grid_cell(v3(1, 0, 0)), (1,0))
        self.player.physical.position = v3(1,0,0)
        self.tick({'e'})
        self.assertNotEqual(self.animation.state, 'pickup')
        self.assertEqual(self.cube.cell, (0,0))

    def test_cardinal_snap_and_contact_matches_cube(self):
        for position in (v3(.1,0,.5),v3(.9,0,.5),v3(.5,0,.1),v3(.5,0,.9)):
            self.cube.reset()
            self.player.physical.position = position
            self.assertEqual(self.cube.request(self.player), 'pickup')
            self.assertAlmostEqual(self.player.yaw/(math.pi/2),round(self.player.yaw/(math.pi/2)))
            self.scene.animate(1.9,1,loop=False)
            ground = self.cube.matrix(self.player,self.scene)
            self.cube.advance('pickup',1.9)
            attached = self.cube.matrix(self.player,self.scene)
            for index in (12,13,14):
                self.assertAlmostEqual(ground[index],attached[index],places=5)

    def test_pickup_carry_drop_and_hold_e(self):
        self.tick({'e'},200)
        self.assertTrue(self.cube.held)
        self.assertIsNone(self.cube.cell)
        self.assertEqual(self.animation.state,'idle')
        self.tick({'e'},180)
        self.assertTrue(self.cube.held)

        self.player.physical.position = v3(-2.2,0,3.2)
        self.tick({'w'},20)
        expected_cell = grid_cell(self.player.physical.position)
        self.tick({'w','e'})
        self.assertEqual(self.animation.state,'drop')
        snapped_position = self.player.physical.position
        self.tick({'w','e'},110)
        self.assertEqual(self.player.physical.position,snapped_position)
        self.tick({'e'},40)
        self.assertFalse(self.cube.held)
        self.assertEqual(self.cube.cell,expected_cell)
        matrix = self.cube.matrix(self.player,self.scene)
        self.assertAlmostEqual(matrix[12],expected_cell[0]+.5)
        self.assertAlmostEqual(matrix[14],expected_cell[1]+.5)
        self.assertAlmostEqual(matrix[13],CUBE_SIZE/2)

    def test_drop_release_has_no_position_pop(self):
        self.tick({'e'},190)
        self.tick(set())
        self.tick({'e'})
        self.scene.animate(1.,2,loop=False)
        before = self.cube.matrix(self.player,self.scene)
        self.cube.advance('drop',1.)
        after = self.cube.matrix(self.player,self.scene)
        for index in (12,13,14):
            self.assertAlmostEqual(before[index],after[index],places=5)

    def test_held_cube_follows_wrist_and_reset(self):
        self.tick({'e'},190)
        before = self.cube.matrix(self.player,self.scene)
        self.player.physical.position += v3(5,2,-3)
        after = self.cube.matrix(self.player,self.scene)
        self.assertAlmostEqual(after[12]-before[12],5)
        self.assertAlmostEqual(after[13]-before[13],2)
        self.assertAlmostEqual(after[14]-before[14],-3)
        self.tick({'r'})
        self.assertFalse(self.cube.held)
        self.assertEqual(self.cube.cell,(0,0))

    def test_stop_starts_from_current_pose_then_freefalls(self):
        for phase in (.15,.55,.8,.95,1.2,1.6,2.):
            self.animation.state = 'move'
            self.animation.time = phase
            self.animation.apply(self.animation.sample(0,phase))
            before = dict(self.animation.pose)
            self.player.move = v3()
            self.animation.update(self.player,set(),1/60)
            self.assertEqual(self.animation.state,'slam')
            for key in before:
                for a,b in zip(before[key],self.animation.pose[key]):
                    self.assertAlmostEqual(a,b,places=6)
            previous_height = self.animation.pose[0,'translation'][1]
            for _ in range(90):
                self.animation.update(self.player,set(),1/60)
                height = self.animation.pose[0,'translation'][1]
                self.assertGreaterEqual(height,0)
                self.assertLessEqual(height,previous_height+1e-6)
                previous_height = height
            self.assertEqual(self.animation.state,'idle')

    def test_jump_does_not_slam_at_its_apex(self):
        self.tick({'space'})
        saw_apex = False
        for _ in range(100):
            self.tick(set())
            if not self.player.ci.grounded:
                self.assertEqual(self.animation.state,'air')
                if abs(self.player.vel_y) < .5:
                    saw_apex = True
            else:
                break
        self.assertTrue(saw_apex)
        self.assertEqual(self.animation.state,'slam')

    def test_walk_gap_is_short_and_identical_when_carrying(self):
        traces = []
        for held in (False, True):
            animation = CharacterAnimation(self.scene)
            animation.cube.held = held
            self.player.ci.grounded = True
            self.player.move = v3(0,0,1)
            trace = []
            for _ in range(240):
                animation.update(self.player,{'w'},1/60)
                trace.append(animation.pose[0,'translation'][1])
            traces.append(trace)
        self.assertEqual(traces[0],traces[1])
        longest = current = 0
        for height in traces[0]:
            current = current + 1 if height < 1e-5 else 0
            longest = max(longest,current)
        self.assertLessEqual(longest/60,.18)
        self.assertGreater(longest,0)

    def test_carried_jump_moves_arm_but_keeps_grip_closed(self):
        self.animation.cube.held = True
        poses = [self.animation.carry_motion(self.animation.sample(0,t))
                 for t in (0,.32,.55,.9,1.35,1.52,2.2)]
        for joint in (1,2,3):
            self.assertGreater(len({pose[joint,'rotation'] for pose in poses}),1)
        for pose in poses:
            for joint in (4,5,6,7):
                self.assertEqual(pose[joint,'rotation'],self.animation.carry_pose[joint,'rotation'])
        self.animation.state = 'move'
        self.animation.apply(poses[3])
        self.player.move = v3()
        self.player.ci.grounded = True
        self.animation.update(self.player,set(),1/60)
        for key in poses[3]:
            for before,after in zip(poses[3][key],self.animation.pose[key]):
                self.assertAlmostEqual(before,after,places=6)


if __name__ == '__main__':
    unittest.main()
