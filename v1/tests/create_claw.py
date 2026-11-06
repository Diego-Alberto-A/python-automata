"""Make the claw glTF/GLB with stdlib.
Rigid weights here cause these are metal bits, joints turn but rails dont bend.
Run again to rebuild assets/characters/claw_lamp.gltf and claw_lamp.glb.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import base64
import json
import math
from pathlib import Path
import struct
from math_functions import (v3, compose, mult_ma, transform_point, transform4,
                            identity_matrix, cross_product, normalizado_vector)
from cube_logic import FLOOR_WRIST

ROOT = Path(__file__).resolve().parents[1]
L1, L2 = 1.45, 1.25


def qz(angle):
    return (0., 0., math.sin(angle/2), math.cos(angle/2))


def arm_angles(x, y):
    y -= .28
    cosine = max(-1., min(1., (x*x+y*y-L1*L1-L2*L2)/(2*L1*L2)))
    elbow = -math.acos(cosine)
    shoulder = math.atan2(y,x)-math.atan2(L2*math.sin(elbow), L1+L2*math.cos(elbow))-math.pi/2
    return shoulder, elbow, -shoulder-elbow


def smooth_keys(time, keys):
    for (a,va),(b,vb) in zip(keys,keys[1:]):
        if time <= b:
            u = max(0., (time-a)/(b-a))
            u = u*u*(3-2*u)
            return tuple(x+(y-x)*u for x,y in zip(va,vb))
    return keys[-1][1]


def pose(time, clip):
    if clip == 0:
        x,y,grip = smooth_keys(time,[(0,(.45,2.15,0)),(.32,(.65,1.45,.25)),
            (.55,(.2,2.55,.45)),(.9,(.45,1.9,.2)),(1.35,(.4,2.3,0)),
            (1.52,(.65,1.5,.25)),(1.8,(.4,2.2,0)),(2.2,(.45,2.15,0))])
        u = (time-.55)/.8
        jump = 1.25*4*u*(1-u) if 0<u<1 else 0.
    elif clip == 1:
        x,y,grip = smooth_keys(time,[(0,(.45,2.15,0)),(.45,(.8,1.8,0)),
            (1.5,(1.25,FLOOR_WRIST,0)),(1.9,(1.25,FLOOR_WRIST,1)),
            (3.,(.8,1.8,1))])
        jump = 0.
    elif clip == 2:
        x,y,grip = smooth_keys(time,[(0,(.8,1.8,1)),
            (1.0,(1.25,FLOOR_WRIST,1)),(1.4,(1.25,FLOOR_WRIST,0)),
            (2.3,(.45,2.15,0))])
        jump = 0.
    else:
        x,y,grip = smooth_keys(time,[(0,(.45,2.15,0)),(.32,(.45,2.15,0)),
            (.44,(.65,1.45,0)),(.62,(.4,2.2,0)),(.85,(.45,2.15,0))])
        jump = max(0.,.9 - .5 * 18 * time * time)
    shoulder,elbow,wrist = arm_angles(x,y)
    spread = math.radians(45-60*grip)
    curl = math.radians(-65+80*grip)
    return jump, [0.,shoulder,elbow,wrist,-spread,-curl,spread,curl]


def build():
    names = ["root_base","shoulder","elbow","wrist","left_finger","left_tip","right_finger","right_tip"]
    parents = [None,0,1,2,3,4,3,6]
    translations = [(0,0,0),(0,.28,0),(0,L1,0),(0,L2,0),(-.22,-.16,0),(0,-.32,0),(.22,-.16,0),(0,-.32,0)]
    _,angles = pose(0,0)
    nodes = []
    worlds = []
    for i,name in enumerate(names):
        node = {"name":name,"translation":translations[i],"rotation":qz(angles[i])}
        children = [j for j,p in enumerate(parents) if p==i]
        if children: node["children"] = children
        nodes.append(node)
        local = compose(v3(*translations[i]),qz(angles[i]),v3(1,1,1))
        worlds.append(mult_ma(worlds[parents[i]],local) if parents[i] is not None else local)

    materials = [
        {"name":"Ivory enamel","pbrMetallicRoughness":{"baseColorFactor":[.88,.9,.83,1],"metallicFactor":.45,"roughnessFactor":.3}},
        {"name":"Graphite joints","pbrMetallicRoughness":{"baseColorFactor":[.28,.39,.48,1],"metallicFactor":.8,"roughnessFactor":.28}},
        {"name":"Brass claw","pbrMetallicRoughness":{"baseColorFactor":[1,.63,.16,1],"metallicFactor":.75,"roughnessFactor":.3}},
        {"name":"Rubber pads","pbrMetallicRoughness":{"baseColorFactor":[.24,.65,.59,1],"metallicFactor":0,"roughnessFactor":.9}},
    ]
    buckets = [dict(positions=[],normals=[],joints=[],weights=[]) for _ in materials]

    def triangle(a,b,c,bone,material):
        normal = normalizado_vector(cross_product(v3(*b)-v3(*a),v3(*c)-v3(*a)))
        normal = transform4(worlds[bone],(normal.x,normal.y,normal.z,0))[:3]
        bucket = buckets[material]
        for p in (a,b,c):
            point = transform_point(worlds[bone],v3(*p))
            bucket["positions"].append((point.x,point.y,point.z))
            bucket["normals"].append(normal)
            bucket["joints"].append((bone,0,0,0))
            bucket["weights"].append((1.,0.,0.,0.))

    def box(center,size,bone,material):
        x,y,z = center; a,b,c = [s/2 for s in size]
        p = [(x-a,y-b,z-c),(x+a,y-b,z-c),(x+a,y+b,z-c),(x-a,y+b,z-c),
             (x-a,y-b,z+c),(x+a,y-b,z+c),(x+a,y+b,z+c),(x-a,y+b,z+c)]
        for a,b,c,d in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(1,2,6,5),(0,4,7,3)]:
            triangle(p[a],p[b],p[c],bone,material)
            triangle(p[a],p[c],p[d],bone,material)

    def cylinder(center,radius,length,bone,material,axis="z",segments=12):
        def p(angle,h):
            a,b = radius*math.cos(angle),radius*math.sin(angle)
            local = (a,h,b) if axis=="y" else (a,b,h)
            return tuple(c+v for c,v in zip(center,local))
        for i in range(segments):
            a,b = 2*math.pi*i/segments,2*math.pi*(i+1)/segments
            pa,pb,pc,pd = p(a,-length/2),p(b,-length/2),p(b,length/2),p(a,length/2)
            # mapping onto Y flips the handedness, so flip these triangles too
            faces = [(pa,pb,pc),(pa,pc,pd)]
            low = tuple(c+(-length/2 if j==(1 if axis=="y" else 2) else 0) for j,c in enumerate(center))
            high = tuple(c+(length/2 if j==(1 if axis=="y" else 2) else 0) for j,c in enumerate(center))
            faces += [(low,pb,pa),(high,pd,pc)]
            for aa,bb,cc in faces:
                triangle(aa,cc,bb,bone,material) if axis=="y" else triangle(aa,bb,cc,bone,material)

    # round base, rubber edge and the swivel bit on top
    cylinder((0,.075,0),.62,.15,0,0,"y",20)
    cylinder((0,.018,0),.58,.036,0,3,"y",20)
    cylinder((0,.2,0),.18,.1,0,1,"y")
    # two rails and crossbars, that desk lamp kinda shape
    for bone,length in ((1,L1),(2,L2)):
        for z in (-.12,.12):
            box((0,length/2,z),(.10,length,.075),bone,0)
        box((0,length*.2,0),(.11,.075,.31),bone,1)
        box((0,length*.8,0),(.11,.075,.31),bone,1)
        cylinder((0,0,0),.15,.42,bone,1)
        cylinder((0,0,.225),.065,.035,bone,2)
        # thin tension rod along the frame
        box((.11,length*.5,0),(.035,length*.66,.035),bone,2)
    cylinder((0,0,0),.14,.32,3,1)
    box((0,-.10,0),(.52,.16,.28),3,2)
    for bone,tip in ((4,5),(6,7)):
        cylinder((0,0,0),.075,.25,bone,1,segments=8)
        box((0,-.16,0),(.10,.32,.16),bone,2)
        cylinder((0,0,0),.065,.20,tip,1,segments=8)
        box((0,-.13,0),(.085,.26,.14),tip,2)
        box((0,-.235,0),(.11,.07,.18),tip,3)

    binary = bytearray(); views = []; accessors = []
    def accessor(rows,kind,component=5126,bounds=False):
        while len(binary)%4: binary.append(0)
        fmt = "f" if component==5126 else "H"
        flat = [v for row in rows for v in row]
        raw = struct.pack("<"+fmt*len(flat),*flat)
        views.append({"buffer":0,"byteOffset":len(binary),"byteLength":len(raw)})
        binary.extend(raw)
        acc = {"bufferView":len(views)-1,"componentType":component,"count":len(rows),"type":kind}
        if bounds:
            acc["min"] = [min(row[i] for row in rows) for i in range(len(rows[0]))]
            acc["max"] = [max(row[i] for row in rows) for i in range(len(rows[0]))]
        accessors.append(acc)
        return len(accessors)-1

    primitives = []
    for i,bucket in enumerate(buckets):
        primitives.append({"attributes":{
            "POSITION":accessor(bucket["positions"],"VEC3",bounds=True),
            "NORMAL":accessor(bucket["normals"],"VEC3"),
            "JOINTS_0":accessor(bucket["joints"],"VEC4",5123),
            "WEIGHTS_0":accessor(bucket["weights"],"VEC4")},"material":i,"mode":4})
    inverse = []
    for m in worlds:
        # undo the bind transform: transpose R, then translation is -R transpose * T
        inv = list(identity_matrix())
        for col in range(3):
            for row in range(3): inv[col*4+row] = m[row*4+col]
        for row in range(3): inv[12+row] = -sum(inv[col*4+row]*m[12+col] for col in range(3))
        inverse.append(inv)
    bind_accessor = accessor(inverse,"MAT4")
    animations = []
    for clip,(name,duration) in enumerate((("Jump",2.2),("Pickup",3.0),("Drop",2.3),("Slam",.85))):
        count = round(duration*30)
        times = [duration*i/count for i in range(count+1)]
        samples = [pose(t,clip) for t in times]
        time_accessor = accessor([(t,) for t in times],"SCALAR",bounds=True)
        samplers,channels = [],[]
        def channel(node,path,rows,kind):
            samplers.append({"input":time_accessor,"output":accessor(rows,kind),"interpolation":"LINEAR"})
            channels.append({"sampler":len(samplers)-1,"target":{"node":node,"path":path}})
        channel(0,"translation",[(0,s[0],0) for s in samples],"VEC3")
        for bone in range(1,8):
            channel(bone,"rotation",[qz(s[1][bone]) for s in samples],"VEC4")
        animations.append({"name":name,"samplers":samplers,"channels":channels})
    nodes.append({"name":"Claw_Lamp_Mesh","mesh":0,"skin":0})
    doc = {"asset":{"version":"2.0","generator":"Automata procedural claw builder (stdlib only)"},
        "scene":0,"scenes":[{"name":"Claw Lamp","nodes":[0,8]}],"nodes":nodes,
        "meshes":[{"name":"Claw Lamp mechanical body","primitives":primitives}],
        "skins":[{"name":"Eight-joint mechanical skeleton","skeleton":0,"joints":list(range(8)),"inverseBindMatrices":bind_accessor}],
        "materials":materials,"animations":animations,"accessors":accessors,"bufferViews":views,
        "buffers":[{"byteLength":len(binary)}],
        "extras":{"units":"meters","up":"Y","animation_0":"Anticipation, takeoff, airborne recoil, landing, settle; in-place loop",
                  "animation_1":"Reach floor, close fingers, lift; ends holding",
                  "animation_2":"Lower, release at the floor, retract",
                  "animation_3":"Freefall, compress on impact, recover",
                  "grip_target":[1.25,FLOOR_WRIST,0],"rig":"Rigid mechanical weights; eight actual skin joints"}}
    folder = ROOT/"assets"/"characters"
    folder.mkdir(parents=True,exist_ok=True)
    js = json.dumps(doc,separators=(",",":")).encode()
    js += b" "*((-len(js))%4)
    blob = bytes(binary)+b"\0"*((-len(binary))%4)
    glb = struct.pack("<4sII",b"glTF",2,28+len(js)+len(blob))
    glb += struct.pack("<II",len(js),0x4e4f534a)+js
    glb += struct.pack("<II",len(blob),0x004e4942)+blob
    (folder/"claw_lamp.glb").write_bytes(glb)
    doc["buffers"][0]["uri"] = "data:application/octet-stream;base64,"+base64.b64encode(binary).decode()
    (folder/"claw_lamp.gltf").write_text(json.dumps(doc,indent=2),encoding="utf-8")
    print(f"Created claw_lamp.gltf and .glb: {sum(len(b['positions'])//3 for b in buckets)} triangles, 8 joints, 4 animations")


if __name__ == "__main__":
    build()
