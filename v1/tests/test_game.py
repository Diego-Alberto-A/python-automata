"""Room checks: walking, collisions and switching the claw animations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


from pathlib import Path
import unittest
from character_animation import CharacterAnimation
from engine_3d import camera
from game_logic import player, move_player, polling_based_inputs
from gltf_loader import load_gltf
from level import StaticLevel
from math_functions import v3

ROOT = Path(__file__).resolve().parents[1]


class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = StaticLevel(ROOT/"assets"/"maps"/"andy.gltf")

    def make_player(self):
        p = player()
        p.height = 2.
        p.intial_position = self.level.spawn
        p.physical.position = self.level.spawn
        return p

    def test_floor_jump_movement_and_reset(self):
        p = self.make_player()
        cam = camera()
        for _ in range(120): move_player(p,self.level.collision,1/60)
        self.assertLess(abs(p.physical.position.y-self.level.floor),.02)
        # wait til we actually touch ground before asking for a jump
        for _ in range(5):
            if p.ci.grounded: break
            move_player(p,self.level.collision,1/60)
        polling_based_inputs(p,cam,1/60,{"space"})
        self.assertEqual(p.vel_y,p.jump_force)
        for _ in range(20): move_player(p,self.level.collision,1/60)
        self.assertGreater(p.physical.position.y,self.level.floor+.5)
        start = p.physical.position
        for _ in range(15):
            polling_based_inputs(p,cam,1/60,{"w"})
            move_player(p,self.level.collision,1/60)
        self.assertGreater((p.physical.position-start).length(),.1)
        polling_based_inputs(p,cam,1/60,{"r"})
        self.assertEqual(p.physical.position,self.level.spawn)
        self.assertEqual(p.vel_y,0)

    def test_animation_input_transitions(self):
        p = self.make_player()
        p.ci.grounded = True
        scene = load_gltf(ROOT/"assets"/"characters"/"claw_lamp.glb")
        animation = CharacterAnimation(scene)
        animation.update(p,set(),1/60)
        self.assertEqual(animation.state,"idle")
        p.move = v3(0,0,1)
        animation.update(p,{"w"},1/60)
        self.assertEqual(animation.state,"move")
        p.move = v3()
        p.physical.position = v3(.2,0,.5)
        animation.update(p,{"e"},1/60)
        self.assertEqual(animation.state,"pickup")
        for _ in range(340): animation.update(p,{"e"},1/60)
        self.assertEqual(animation.state,"idle")
        animation.update(p,set(),1/60)
        animation.update(p,{"e"},1/60)
        self.assertEqual(animation.state,"drop")
        for _ in range(150): animation.update(p,set(),1/60)
        p.ci.grounded = False
        p.vel_y = 5.
        animation.update(p,{"space"},1/60)
        self.assertEqual(animation.state,"air")
        self.assertAlmostEqual(scene.nodes[0].machine.collapse()[13],0)

    def test_spatial_index_matches_full_collision(self):
        from game_logic import collide_and_slide_capsuleish
        p = self.make_player()
        displacement = v3(.03,-.05,0)
        indexed = collide_and_slide_capsuleish(p.physical.position,displacement,.8,2.,self.level.grid)
        full = collide_and_slide_capsuleish(p.physical.position,displacement,.8,2.,self.level.collision.mesh.tris)
        self.assertLess((indexed[0]-full[0]).length(),1e-6)
        self.assertEqual(indexed[2].grounded,full[2].grounded)


if __name__=="__main__": unittest.main()
