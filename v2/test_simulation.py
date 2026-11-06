import unittest
from pathlib import Path
from automata import ModeloRecoleccion
from simulation_view import CELL_SIZE, cell_center, SimulationView
from gltf_loader import load_gltf
from free_camera import FreeCamera


class AutomataTests(unittest.TestCase):
    def test_collection_and_invariants(self):
        for size, robots, cubes, vision in ((3, 1, 3, 2), (10, 7, 20, 2),
                                          (20, 7, 20, 2), (100, 7, 20, 2)):
            with self.subTest(size=size, vision=vision):
                model = ModeloRecoleccion(size, robots, cubes, vision)
                while not model.finished:
                    event = model.advance_agent()
                    _, before, after = event
                    self.assertLessEqual(abs(before[0][0]-after[0][0]) +
                                         abs(before[0][1]-after[0][1]), 1)
                    positions = [r.posicion() for r in model.robots]
                    self.assertEqual(len(set(positions)), robots)
                    self.assertEqual(set(model.ocupadas), set(positions))
                    self.assertTrue(all(0 <= f < size and 0 <= c < size for f, c in positions))
                    self.assertEqual(len(model.cubos) + model.entregados +
                                     sum(r.cargando for r in model.robots), cubes)
                self.assertTrue(model.complete)
                self.assertEqual(model.entregados, cubes)

    def test_perception_and_seed(self):
        a, b = ModeloRecoleccion(), ModeloRecoleccion()
        self.assertEqual(a.cubos, b.cubos)
        for robot in a.robots:
            self.assertTrue(all(robot.distancia(robot.posicion(), p) <= 2
                                for p in robot.celdas_visibles()))
            self.assertEqual(robot.cubos_conocidos, a.cubos & set(robot.celdas_visibles()))
        for _ in range(80):
            self.assertEqual(a.advance_agent(), b.advance_agent())

    def test_empty_limit_and_validation(self):
        self.assertTrue(ModeloRecoleccion(cubos=0).complete)
        model = ModeloRecoleccion(steps=1)
        model.step()
        self.assertTrue(model.finished)
        self.assertFalse(model.complete)
        for kwargs in ({'tamano': 2}, {'robots': 21}, {'cubos': -1},
                       {'cubos': 500}, {'radio_vision': -1}, {'steps': 0}):
            with self.assertRaises(ValueError):
                ModeloRecoleccion(**kwargs)

    def test_grid_mapping(self):
        a, b, c = cell_center((0, 0), 20), cell_center((0, 1), 20), cell_center((1, 0), 20)
        self.assertEqual(b.x-a.x, CELL_SIZE)
        self.assertEqual(c.z-a.z, CELL_SIZE)
        self.assertEqual(a.y, 0)


class PlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = load_gltf(Path(__file__).parent / 'assets/characters/claw_lamp.glb')

    def test_pickup_drop_and_independent_instances(self):
        view = SimulationView(ModeloRecoleccion(), self.scene)
        first, second = view.claws[:2]
        other_pose = second.scene.nodes[3].machine.collapse()
        first.begin(((2, 0), False), ((2, 1), True))
        first.update(.5)
        self.assertFalse(first.cube.held)
        self.assertTrue(first.ground_cube)
        first.update(1.)
        self.assertTrue(first.cube.held)
        self.assertEqual(second.scene.nodes[3].machine.collapse(), other_pose)
        first.begin(((0, 1), True), ((0, 0), False))
        first.update(.45)
        first.advance_drop(.45)
        self.assertTrue(first.cube.held)
        first.update(1.)
        first.advance_drop(.55)
        self.assertTrue(first.cube.held)
        first.advance_drop(4.)
        self.assertFalse(first.cube.held)

    def test_pause_speed_and_drop_do_not_change_turn_order(self):
        model = ModeloRecoleccion()
        reference = ModeloRecoleccion()
        view = SimulationView(model, self.scene)
        for _ in range(200):
            view.update(1/7, 7)
            reference.advance_agent()
        self.assertEqual(model.t, reference.t)
        self.assertEqual([r.posicion() for r in model.robots], [r.posicion() for r in reference.robots])
        before = [(c.drop_clock, c.center, c.animation.pose) for c in view.claws]
        view.update(0, 56)
        self.assertEqual(before, [(c.drop_clock, c.center, c.animation.pose) for c in view.claws])
        camera, shifted = FreeCamera(20), FreeCamera(20)
        camera.update({'w'}, .1, 640,360)
        shifted.update({'w','shift'}, .1, 640,360)
        self.assertEqual(camera.position, shifted.position)

    def test_playback_finishes_and_camera_is_independent(self):
        model = ModeloRecoleccion(3, 1, 1)
        view = SimulationView(model, self.scene)
        camera = FreeCamera(3)
        positions = [r.posicion() for r in model.robots]
        camera.update({'w', 'e'}, 1., 640, 360)
        self.assertEqual(positions, [r.posicion() for r in model.robots])
        for _ in range(1000):
            view.update(.25, 20)
            if model.complete and view.active is None:
                break
        self.assertTrue(model.complete)
        self.assertIsNone(view.active)
        self.assertFalse(any(c.cube.held for c in view.claws))

    def test_single_turn_does_not_start_next_decision(self):
        model = ModeloRecoleccion()
        view = SimulationView(model, self.scene)
        view.update(1 / 7, 7)
        self.assertEqual(model.turn, 1)
        self.assertIsNone(view.active)


if __name__ == '__main__':
    unittest.main()
