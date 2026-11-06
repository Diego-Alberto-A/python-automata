"""Check the actual exported claw, not a pretend skeleton."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import math
from pathlib import Path
import unittest
from gltf_loader import Reader, load_gltf
from math_functions import identity_matrix, mult_ma
from cube_logic import FLOOR_WRIST

ASSET = Path(__file__).resolve().parents[1]/"assets"/"characters"/"claw_lamp"


class ClawAssetTests(unittest.TestCase):
    def test_rig_and_bind_matrices(self):
        reader = Reader(ASSET.with_suffix(".glb"))
        self.assertEqual([a["name"] for a in reader.doc["animations"]],["Jump","Pickup","Drop","Slam"])
        scene = load_gltf(ASSET.with_suffix(".glb"))
        joints,inverses = scene.skins[0]
        self.assertEqual(len(joints),8)
        for joint,inverse in zip(joints,inverses):
            matrix = mult_ma(scene.nodes[joint].machine.collapse(),inverse)
            for actual,expected in zip(matrix,identity_matrix()):
                self.assertAlmostEqual(actual,expected,places=5)
        for mesh in scene.meshes[0]:
            self.assertEqual(len(mesh.positions()),len(mesh.weights))
            for weights in mesh.weights: self.assertAlmostEqual(sum(weights),1)

    def test_animation_loops_and_floor_clearance(self):
        scene = load_gltf(ASSET.with_suffix(".glb"))
        for clip,duration in enumerate((2.2,3.0,2.3,.85)):
            scene.animate(0,clip,loop=False)
            first = [p for _,points in scene.drawables() for p in points]
            for frame in range(31):
                scene.animate(duration*frame/30,clip,loop=False)
                points = [p for _,points in scene.drawables() for p in points]
                self.assertGreaterEqual(min(p.y for p in points),-1e-5)
                self.assertTrue(all(math.isfinite(v) for p in points for v in (p.x,p.y,p.z)))
            if clip==0:
                for a,b in zip(first,points): self.assertLess((a-b).length(),1e-5)
        scene.animate(.95,0,loop=False)
        self.assertGreater(scene.nodes[0].machine.collapse()[13],1.24)
        scene.animate(1.9,1,loop=False)
        wrist = scene.nodes[3].machine.collapse()
        self.assertAlmostEqual(wrist[12],1.25,places=4)
        self.assertAlmostEqual(wrist[13],FLOOR_WRIST,places=4)
        scene.animate(3.2,1,loop=False)
        self.assertAlmostEqual(scene.nodes[3].machine.collapse()[13],1.8,places=4)

    def test_gltf_glb_equivalence(self):
        a,b = [load_gltf(ASSET.with_suffix(ext)) for ext in (".gltf",".glb")]
        for clip in (0,1,2,3):
            a.animate(1.,clip); b.animate(1.,clip)
            for (_,pa),(_,pb) in zip(a.drawables(),b.drawables()):
                self.assertEqual(pa,pb)


if __name__ == "__main__": unittest.main()
