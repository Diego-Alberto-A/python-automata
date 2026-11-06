"""Tiny generated glTFs for checks, no model downloads needed."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import base64
import json
from pathlib import Path
import struct
import tempfile
import unittest

from math_functions import *
from graphics_abstraction import SoftwareRenderer, bresenham, clip_line
from gltf_loader import load_gltf, GltfError, Reader, interpolate
from models import demo_models
from game_logic import (player, move_player, polling_based_inputs, event_based_inputs,
                        interaction_state, check_boundary)
from engine_3d import camera, window_context


def fixture():
    data = bytearray(); views = []; accessors = []
    def add(values,fmt,component,kind,count):
        while len(data)%4: data.append(0)
        raw = struct.pack("<"+fmt*len(values),*values)
        views.append({"buffer":0,"byteOffset":len(data),"byteLength":len(raw)})
        data.extend(raw)
        accessors.append({"bufferView":len(views)-1,"componentType":component,"count":count,"type":kind})
        return len(accessors)-1
    positions = add([0,0,0,1,0,0,0,1,0],"f",5126,"VEC3",3)
    joints = add([0,1,0,0]*3,"B",5121,"VEC4",3)
    weights = add([.5,.5,0,0]*3,"f",5126,"VEC4",3)
    times = add([0,1],"f",5126,"SCALAR",2)
    translations = add([0,0,0,2,0,0],"f",5126,"VEC3",2)
    inverse = add(list(identity_matrix())*2,"f",5126,"MAT4",2)
    doc = {"asset":{"version":"2.0"},"buffers":[{"byteLength":len(data)}],"bufferViews":views,"accessors":accessors,
           "meshes":[{"primitives":[{"attributes":{"POSITION":positions,"JOINTS_0":joints,"WEIGHTS_0":weights}}]}],
           "nodes":[{"children":[1,3],"translation":[3,0,0]},{"children":[2]},{},{"mesh":0,"skin":0,"translation":[99,0,0]}],
           "skins":[{"joints":[1,2],"inverseBindMatrices":inverse}],"scenes":[{"nodes":[0]}],"scene":0,
           "animations":[{"samplers":[{"input":times,"output":translations}],"channels":[{"sampler":0,"target":{"node":2,"path":"translation"}}]}]}
    return doc,bytes(data)


class EngineTests(unittest.TestCase):
    def test_bresenham_all_octants_and_degenerate(self):
        for x,y in [(7,2),(2,7),(-7,2),(-2,7),(7,-2),(2,-7),(-7,-2),(-2,-7),(0,0),(0,7),(7,0)]:
            points = list(bresenham(0,0,x,y))
            self.assertEqual(points[0],(0,0)); self.assertEqual(points[-1],(x,y))
            self.assertEqual(len(points),max(abs(x),abs(y))+1)
            for a,b in zip(points,points[1:]): self.assertEqual(max(abs(a[0]-b[0]),abs(a[1]-b[1])),1)

    def test_clipping_and_depth(self):
        self.assertIsNone(clip_line((0,0,0,-1),(1,0,0,-1)))
        a,b = clip_line((-2,0,0,1),(2,0,0,1))
        self.assertEqual(a,(-1,0,0,1)); self.assertEqual(b,(1,0,0,1))
        r = SoftwareRenderer(9,9); r.clear()
        r.line((-1,0,-.5,1),(1,0,-.5,1),(255,0,0))
        r.line((0,-1,.5,1),(0,1,.5,1),(0,0,255))
        self.assertEqual(r.pixels[(4*9+4)*3:(4*9+4)*3+3],bytes((255,0,0)))

    def test_matrix_machine_hierarchy_and_cache(self):
        root = ModelingMachine(); child = ModelingMachine(); leaf = ModelingMachine()
        child.parent = root; leaf.parent = child
        root.set_operations(translate(v3(1,0,0)))
        child.set_operations(translate(v3(0,2,0)))
        leaf.set_operations(translate(v3(0,0,3)))
        self.assertEqual(transform_point(leaf.collapse(),v3()),v3(1,2,3))
        revisions = [m.revision for m in (root,child,leaf)]
        leaf.collapse(); self.assertEqual([m.revision for m in (root,child,leaf)],revisions)
        root.set_operations(translate(v3(4,0,0)))
        self.assertEqual(transform_point(leaf.collapse(),v3()),v3(4,2,3))

    def test_player_lands_and_jumps(self):
        ground,_ = demo_models(); p = player()
        for _ in range(180): move_player(p,ground,1/60)
        self.assertLess(abs(p.physical.position.y),.01)
        p.vel_y = p.jump_force; move_player(p,ground,1/60)
        self.assertGreater(p.physical.position.y,.05)

    def test_controls_and_interaction(self):
        p = player()
        cam = camera()
        polling_based_inputs(p,cam,1/60,{"w","shift"})
        self.assertEqual(p.move,v3(0,0,1))
        self.assertEqual(p.speed,12)
        p.physical.position = v3(0,0,7)
        self.assertTrue(check_boundary(p,(-3,3),(5,9)))
        state = interaction_state(active=True)
        window = window_context(None,960,540)
        event_based_inputs([("click",(480,270)),("wheel",100)],state,window,cam)
        self.assertTrue(state.clicked_positively)
        self.assertEqual(cam.distance,2)

    def test_gltf_and_glb_skin_animation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            folder = Path(folder); doc,raw = fixture()
            for variant in ("embedded","external","glb"):
                if variant=="glb":
                    doc["buffers"][0].pop("uri",None)
                    js = json.dumps(doc).encode(); js += b" "*((-len(js))%4)
                    binary = raw+b"\0"*((-len(raw))%4)
                    contents = struct.pack("<4sII",b"glTF",2,28+len(js)+len(binary))+struct.pack("<II",len(js),0x4e4f534a)+js+struct.pack("<II",len(binary),0x004e4942)+binary
                    path = folder/"model.glb"; path.write_bytes(contents)
                else:
                    if variant=="embedded": uri = "data:application/octet-stream;base64,"+base64.b64encode(raw).decode()
                    else: uri = "buffer.bin"; (folder/uri).write_bytes(raw)
                    doc["buffers"][0]["uri"] = uri
                    path = folder/"model.gltf"; path.write_text(json.dumps(doc))
                scene = load_gltf(path); scene.animate(.5,loop=False)
                mesh,positions = next(scene.drawables())
                # root at 3, child moves to 1, half each gives 3.5
                # mesh translation is 99 on purpose, it mustnt get added to the skin
                self.assertEqual(positions[0],v3(3.5,0,0))
                self.assertEqual(len(mesh.vertices),24)
                scene.animate(1,loop=False)
                self.assertEqual(next(scene.drawables())[1][0],v3(4,0,0))
                renderer = SoftwareRenderer(64,64)
                renderer.draw_mesh(mesh,identity_matrix(),look_at(v3(4,2,6),v3(4,0,0),v3(0,1,0)),perspective(1,1,.1,100),positions)
                self.assertGreater(renderer.points_drawn,0)

    def test_sparse_normalized_accessor(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            data = bytes([1,255,128,0,255])
            doc = {"asset":{"version":"2.0"},"buffers":[{"byteLength":5,"uri":"data:application/octet-stream;base64,"+base64.b64encode(data).decode()}],
                   "bufferViews":[{"buffer":0,"byteLength":1},{"buffer":0,"byteOffset":1,"byteLength":4}],
                   "accessors":[{"componentType":5121,"normalized":True,"type":"VEC4","count":2,"sparse":{"count":1,"indices":{"bufferView":0,"componentType":5121},"values":{"bufferView":1}}}]}
            path = Path(folder)/"sparse.gltf"; path.write_text(json.dumps(doc))
            values = Reader(path).accessor(0)
            self.assertEqual(values[0],(0,0,0,0)); self.assertEqual(values[1],(1,128/255,0,1))

    def test_interpolation_and_rejection(self):
        self.assertEqual(interpolate([0,1],[(0,),(2,)],.5,"STEP"),(0,))
        self.assertEqual(interpolate([0,1],[(0,),(0,),(0,),(0,),(2,),(0,)],.5,"CUBICSPLINE"),(1,))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            doc,raw = fixture(); doc["nodes"][2]["children"] = [0]
            doc["buffers"][0]["uri"] = "data:application/octet-stream;base64,"+base64.b64encode(raw).decode()
            path = Path(folder)/"cycle.gltf"; path.write_text(json.dumps(doc))
            with self.assertRaises(GltfError): load_gltf(path)


if __name__=="__main__": unittest.main()
