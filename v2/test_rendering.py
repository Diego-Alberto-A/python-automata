import unittest
from pathlib import Path
from graphics_abstraction.wire_geometry import compact_scene
from gltf_loader import load_gltf


class RenderingTests(unittest.TestCase):
    def test_welding_preserves_all_animated_edges(self):
        original = load_gltf(Path(__file__).parent / 'assets/characters/claw_lamp.glb')
        compact = compact_scene(original)
        def edges(scene):
            result = set()
            for mesh, positions in scene.drawables():
                points = [(round(p.x, 7), round(p.y, 7), round(p.z, 7)) for p in positions]
                for a, b in mesh.edges():
                    result.add((mesh.color, tuple(sorted((points[a], points[b])))))
            return result
        self.assertLess(sum(len(m.vertices) for meshes in compact.meshes for m in meshes),
                        sum(len(m.vertices) for meshes in original.meshes for m in meshes) / 2)
        for animation in range(4):
            for seconds in (0, .7, 2.3):
                original.animate(seconds, animation, loop=False)
                compact.animate(seconds, animation, loop=False)
                self.assertEqual(edges(original), edges(compact))


if __name__ == '__main__':
    unittest.main()
