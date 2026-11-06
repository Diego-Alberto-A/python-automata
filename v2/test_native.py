import math
import random
import unittest
from pathlib import Path
from graphics_abstraction.native_renderer import NativeRenderer
from graphics_abstraction.software import SoftwareRenderer
from gltf_loader import load_gltf
from simulation_view import SimulationView
from automata import ModeloRecoleccion
from free_camera import FreeCamera


class NativeTests(unittest.TestCase):
    def pair(self, width=101, height=79):
        a, b = SoftwareRenderer(width, height), NativeRenderer(width, height)
        a.clear(); b.clear()
        return a, b

    def assert_same(self, a, b):
        self.assertEqual(a.pixels, b.pixels)
        self.assertEqual(a.points_drawn, b.points_drawn)
        for x, y in zip(a.depth, b.depth):
            if math.isinf(x):
                self.assertEqual(x, y)
            else:
                self.assertAlmostEqual(x, y, places=13)

    def test_lines_all_octants_clipping_depth_and_invalid(self):
        a, b = self.pair()
        rng = random.Random(42)
        cases = [((0,0,0,1),(x,y,.5,1)) for x in (-1,0,1) for y in (-1,0,1)]
        cases += [(tuple(rng.uniform(-2,2) for _ in range(4)),
                   tuple(rng.uniform(-2,2) for _ in range(4))) for _ in range(1000)]
        cases += [((float('nan'),0,0,1),(0,0,0,1)), ((0,0,0,0),(0,0,0,0)),
                  ((-1,0,-.5,1),(1,0,.5,1)), ((0,-1,0,1),(0,1,0,1))]
        for start, end in cases:
            color = tuple(rng.randrange(256) for _ in range(3))
            a.line(start,end,color); b.line(start,end,color)
        self.assert_same(a,b)

    def test_scene_matches_during_animation_and_camera_motion(self):
        scene = load_gltf(Path(__file__).parent / 'assets/characters/claw_lamp.glb')
        view = SimulationView(ModeloRecoleccion(), scene)
        camera = FreeCamera(20)
        a,b = self.pair(320,180)
        for mode in ('edges','points'):
            for frame in range(5):
                camera.update({'left','w'}, .1, 320,180)
                view.update(.1, 20)
                a.clear(); b.clear()
                view.draw(a,camera,mode); view.draw(b,camera,mode)
                self.assert_same(a,b)

    def test_resize_clear_and_export(self):
        a,b = self.pair()
        a.resize(13,17); b.resize(13,17)
        a.clear((1,2,3)); b.clear((1,2,3))
        self.assert_same(a,b)
        a.line((-1,-1,0,1),(1,1,0,1),(255,255,255))
        b.line((-1,-1,0,1),(1,1,0,1),(255,255,255))
        self.assert_same(a,b)


if __name__ == '__main__':
    unittest.main()
