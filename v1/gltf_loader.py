"""Reading glTF / GLB with stdlib, skeleton and weights included.

Triangle lists, strips, fans, packed or sparse accessors, node transforms and skins.
STEP / LINEAR / CUBICSPLINE for animation. Texture sampling isnt done here.
Required extensions we dont support, morphs and non-triangles get rejected.
"""
import base64
import bisect
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import struct
from urllib.parse import unquote

from math_functions import (ModelingMachine, identity_matrix, mult_ma,
                            transform_point, translate, quaternion_matrix, scale, v3)
from models import map_mesh

COMPONENTS = {5120:("b",1),5121:("B",1),5122:("h",2),5123:("H",2),5125:("I",4),5126:("f",4)}
COUNTS = {"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT2":4,"MAT3":9,"MAT4":16}


class GltfError(ValueError): pass


class Reader:
    def __init__(self,path):
        self.path = Path(path)
        raw = self.path.read_bytes(); binary = None
        if raw[:4] == b"glTF":
            if len(raw)<12: raise GltfError("Truncated GLB header")
            magic,version,length = struct.unpack_from("<4sII",raw)
            if version!=2 or length!=len(raw): raise GltfError("Invalid GLB version or length")
            offset = 12; chunks = []
            while offset<len(raw):
                if offset+8>len(raw): raise GltfError("Truncated GLB chunk")
                size,kind = struct.unpack_from("<II",raw,offset); offset += 8
                if size%4 or offset+size>len(raw): raise GltfError("Invalid GLB chunk size")
                chunks.append((kind,raw[offset:offset+size])); offset += size
            if not chunks or chunks[0][0]!=0x4e4f534a: raise GltfError("GLB must begin with JSON")
            self.doc = json.loads(chunks[0][1].decode("utf-8"))
            binary = next((data for kind,data in chunks[1:] if kind==0x004e4942),None)
        else: self.doc = json.loads(raw.decode("utf-8"))
        if self.doc.get("asset",{}).get("version")!="2.0": raise GltfError("Only glTF 2.0 is supported")
        if self.doc.get("extensionsRequired"):
            raise GltfError("Unsupported required extensions: "+", ".join(self.doc["extensionsRequired"]))
        self.buffers = []
        for i,buffer in enumerate(self.doc.get("buffers",[])):
            uri = buffer.get("uri")
            if uri is None:
                if i!=0 or binary is None: raise GltfError("Missing binary buffer")
                data = binary
            elif uri.startswith("data:"):
                header,payload = uri.split(",",1)
                if not header.endswith(";base64"): raise GltfError("Buffer data URI must use base64")
                data = base64.b64decode(payload,validate=True)
            else:
                if ":" in uri or uri.startswith(("/","\\")): raise GltfError("Only relative local buffer URIs are supported")
                data = (self.path.parent/unquote(uri)).read_bytes()
            if len(data)<buffer["byteLength"]: raise GltfError("Buffer is shorter than declared")
            self.buffers.append(data[:buffer["byteLength"]])

    def view(self,index):
        view = self.doc["bufferViews"][index]; data = self.buffers[view["buffer"]]
        offset = view.get("byteOffset",0); end = offset+view["byteLength"]
        if offset<0 or end>len(data): raise GltfError("Buffer view outside buffer")
        return memoryview(data)[offset:end],view

    def unpack(self,view_index,offset,count,component,type_name,strided=True):
        fmt,size = COMPONENTS[component]; count_components = COUNTS[type_name]
        # byte/short matrix columns need padding to 4 bytes, glTF wants it that way
        if type_name.startswith("MAT"):
            side = int(type_name[-1]); column_stride = ((side*size+3)//4)*4
            offsets = [c*column_stride+r*size for c in range(side) for r in range(side)]
            element_size = side*column_stride
        else:
            offsets = [i*size for i in range(count_components)]; element_size = count_components*size
        data,view = self.view(view_index)
        stride = view.get("byteStride",element_size) if strided else element_size
        if stride<element_size or offset<0 or count<0 or (count and offset+(count-1)*stride+element_size>len(data)):
            raise GltfError("Accessor outside buffer view or invalid stride")
        return [tuple(struct.unpack_from("<"+fmt,data,offset+i*stride+j)[0] for j in offsets) for i in range(count)]

    def accessor(self,index):
        a = self.doc["accessors"][index]; component = a["componentType"]; kind = a["type"]; count = a["count"]
        if component not in COMPONENTS or kind not in COUNTS: raise GltfError("Unsupported accessor format")
        if count<0: raise GltfError("Negative accessor count")
        if "bufferView" in a:
            result = self.unpack(a["bufferView"],a.get("byteOffset",0),count,component,kind)
        else: result = [(0,)*COUNTS[kind] for _ in range(count)]
        if "sparse" in a:
            sparse = a["sparse"]; indices = sparse["indices"]; values = sparse["values"]
            if indices["componentType"] not in (5121,5123,5125): raise GltfError("Invalid sparse index type")
            ix = self.unpack(indices["bufferView"],indices.get("byteOffset",0),sparse["count"],indices["componentType"],"SCALAR",False)
            vals = self.unpack(values["bufferView"],values.get("byteOffset",0),sparse["count"],component,kind,False)
            previous = -1
            for (i,),value in zip(ix,vals):
                if i<=previous or i>=count: raise GltfError("Invalid sparse indices")
                result[i] = value; previous = i
        if a.get("normalized") and component!=5126:
            maximum = {5120:127,5121:255,5122:32767,5123:65535,5125:4294967295}[component]
            result = [tuple(max(-1.,v/maximum) for v in row) for row in result]
        return result


@dataclass
class Node:
    name: str
    translation: tuple
    rotation: tuple
    scaling: tuple
    matrix: object
    mesh: object
    skin: object
    parent: object = None
    machine: ModelingMachine = field(default_factory=ModelingMachine)

    def set_pose(self,t=None,r=None,s=None):
        if self.matrix is not None:
            if any(value is not None for value in (t,r,s)): raise GltfError("Animation targets a matrix node")
            self.machine.set_operations(self.matrix)
        else:
            # leave T/R/S apart for now, the state machine does the mult when needed
            self.machine.set_operations(
                translate(v3(*(t if t is not None else self.translation))),
                quaternion_matrix(r if r is not None else self.rotation),
                scale(v3(*(s if s is not None else self.scaling))),
            )


def interpolate(times,values,time,mode,rotation=False):
    if not times: raise GltfError("Animation has no keys")
    index = max(0,min(len(times)-1,bisect.bisect_right(times,time)-1))
    if time<=times[0]: index = 0
    if mode=="CUBICSPLINE": a = values[index*3+1]
    else: a = values[index]
    if index==len(times)-1 or time<=times[0] or mode=="STEP": return a
    dt = times[index+1]-times[index]; t = (time-times[index])/dt
    if mode=="CUBICSPLINE":
        b = values[(index+1)*3+1]; out = values[index*3+2]; incoming = values[(index+1)*3]
        result = tuple((2*t**3-3*t*t+1)*x+(t**3-2*t*t+t)*dt*o+(-2*t**3+3*t*t)*y+(t**3-t*t)*dt*n for x,y,o,n in zip(a,b,out,incoming))
    else:
        b = values[index+1]
        if rotation:
            dot = sum(x*y for x,y in zip(a,b))
            if dot<0: b = tuple(-v for v in b); dot = -dot
            if dot<.9995:
                theta = math.acos(max(-1.,min(1.,dot))); sin = math.sin(theta)
                return tuple((math.sin((1-t)*theta)*x+math.sin(t*theta)*y)/sin for x,y in zip(a,b))
        result = tuple(x+(y-x)*t for x,y in zip(a,b))
    if rotation:
        length = math.sqrt(sum(v*v for v in result))
        return tuple(v/max(length,1e-12) for v in result)
    return result


class Scene:
    def __init__(self,nodes,meshes,skins,animations,active):
        self.nodes,self.meshes,self.skins,self.animations,self.active = nodes,meshes,skins,animations,active
        for node in nodes:
            node.machine.parent = nodes[node.parent].machine if node.parent is not None else None
            node.set_pose()

    def animate(self,seconds,animation=0,loop=True):
        if not self.animations: return
        if not 0 <= animation < len(self.animations):
            raise GltfError(f"Animation {animation} does not exist; scene has {len(self.animations)} animations")
        channels = self.animations[animation]
        duration = max((channel[2][-1] for channel in channels),default=0.)
        time = seconds%duration if loop and duration>0 else max(0.,min(duration,seconds))
        poses = {}
        for node,path,times,values,mode in channels:
            poses.setdefault(node,{})[path] = interpolate(times,values,time,mode,path=="rotation")
        for i,node in enumerate(self.nodes):
            pose = poses.get(i,{})
            node.set_pose(pose.get("translation"),pose.get("rotation"),pose.get("scale"))

    def drawables(self):
        worlds = [node.machine.collapse() for node in self.nodes]
        palettes = {}
        for i in self.active:
            node = self.nodes[i]
            if node.mesh is None: continue
            for mesh in self.meshes[node.mesh]:
                positions = mesh.positions()
                if node.skin is not None:
                    if not mesh.joints: raise GltfError("Skinned primitive is missing joints and weights")
                    if node.skin not in palettes:
                        joints,inverse = self.skins[node.skin]
                        palettes[node.skin] = [mult_ma(worlds[j],bind) for j,bind in zip(joints,inverse)]
                    palette = palettes[node.skin]; skinned = []
                    # jointWorld * inverseBind puts these straight into world space
                    # dont multiply the mesh world matrix again, we're already there
                    for p,joints,weights in zip(positions,mesh.joints,mesh.weights):
                        total = sum(weights)
                        if total<=1e-12: skinned.append(transform_point(worlds[i],p)); continue
                        out = v3()
                        for joint,weight in zip(joints,weights):
                            if joint<0 or joint>=len(palette): raise GltfError("Joint index outside skin")
                            if weight: out = out+transform_point(palette[joint],p)*(weight/total)
                        skinned.append(out)
                    positions = skinned
                else: positions = [transform_point(worlds[i],p) for p in positions]
                yield mesh,positions


def load_gltf(path):
    reader = Reader(path); doc = reader.doc; meshes = []
    for source in doc.get("meshes",[]):
        primitives = []
        for primitive in source["primitives"]:
            if primitive.get("targets"): raise GltfError("Morph targets are not supported")
            attrs = primitive["attributes"]
            if "POSITION" not in attrs: raise GltfError("Primitive is missing POSITION")
            positions = reader.accessor(attrs["POSITION"]); count = len(positions)
            normals = reader.accessor(attrs["NORMAL"]) if "NORMAL" in attrs else [(0,1,0)]*count
            uvs = reader.accessor(attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else [(0,0)]*count
            if len(normals)!=count or len(uvs)!=count: raise GltfError("Attribute counts differ")
            if any(len(p)!=3 for p in positions+normals) or any(len(uv)!=2 for uv in uvs): raise GltfError("Invalid vertex attribute shape")
            indices = [row[0] for row in reader.accessor(primitive["indices"])] if "indices" in primitive else list(range(count))
            if any(not isinstance(i,int) or i<0 or i>=count for i in indices): raise GltfError("Invalid triangle index")
            mode = primitive.get("mode",4)
            if mode==5:
                indices = [j for i in range(2,len(indices)) for j in ((indices[i-2],indices[i-1],indices[i]) if i%2==0 else (indices[i-1],indices[i-2],indices[i]))]
            elif mode==6: indices = [j for i in range(2,len(indices)) for j in (indices[0],indices[i-1],indices[i])]
            elif mode!=4: raise GltfError("Only triangle primitives are supported")
            if len(indices)%3: raise GltfError("Triangle indices must be divisible by three")
            color = (160,210,235)
            if "material" in primitive:
                material = doc["materials"][primitive["material"]]
                factor = material.get("pbrMetallicRoughness",{}).get("baseColorFactor",[1,1,1,1])
                color = tuple(round(max(0,min(1,v))*255) for v in factor[:3])
            mesh = map_mesh([v for p,n,uv in zip(positions,normals,uvs) for v in (*p,*n,*uv)],indices=indices,color=color)
            joint_sets = sorted(int(key.split("_")[1]) for key in attrs if key.startswith("JOINTS_"))
            weight_sets = sorted(int(key.split("_")[1]) for key in attrs if key.startswith("WEIGHTS_"))
            if joint_sets!=weight_sets: raise GltfError("Joint and weight attributes must be paired")
            if joint_sets:
                mesh.joints = [() for _ in range(count)]; mesh.weights = [() for _ in range(count)]
                for number in joint_sets:
                    joints = reader.accessor(attrs[f"JOINTS_{number}"]); weights = reader.accessor(attrs[f"WEIGHTS_{number}"])
                    if len(joints)!=count or len(weights)!=count: raise GltfError("Skin attribute counts differ")
                    for i,(j,w) in enumerate(zip(joints,weights)):
                        if len(j)!=4 or len(w)!=4 or any(not isinstance(v,int) or v<0 for v in j) or any(v<0 for v in w): raise GltfError("Invalid skin attributes")
                        mesh.joints[i] += j; mesh.weights[i] += w
            mesh.rebuild(); primitives.append(mesh)
        meshes.append(primitives)
    nodes = [Node(n.get("name",str(i)),tuple(n.get("translation",[0,0,0])),tuple(n.get("rotation",[0,0,0,1])),tuple(n.get("scale",[1,1,1])),tuple(n["matrix"]) if "matrix" in n else None,n.get("mesh"),n.get("skin")) for i,n in enumerate(doc.get("nodes",[]))]
    for i,n in enumerate(doc.get("nodes",[])):
        for child in n.get("children",[]):
            if child<0 or child>=len(nodes) or nodes[child].parent is not None: raise GltfError("Invalid node hierarchy")
            nodes[child].parent = i
    for i in range(len(nodes)):
        seen = set(); cursor = i
        while cursor is not None:
            if cursor in seen: raise GltfError("Cycle in node hierarchy")
            seen.add(cursor); cursor = nodes[cursor].parent
    skins = []
    for skin in doc.get("skins",[]):
        joints = skin["joints"]
        if any(j<0 or j>=len(nodes) for j in joints): raise GltfError("Invalid skin joint node")
        inverse = reader.accessor(skin["inverseBindMatrices"]) if "inverseBindMatrices" in skin else [identity_matrix() for _ in joints]
        if len(inverse)!=len(joints) or any(len(m)!=16 for m in inverse): raise GltfError("Invalid inverse bind matrices")
        skins.append((joints,inverse))
    for node in nodes:
        if node.mesh is not None and not 0<=node.mesh<len(meshes): raise GltfError("Invalid mesh reference")
        if node.skin is not None and not 0<=node.skin<len(skins): raise GltfError("Invalid skin reference")
        if len(node.translation)!=3 or len(node.rotation)!=4 or len(node.scaling)!=3 or (node.matrix is not None and len(node.matrix)!=16): raise GltfError("Invalid node transform")
    animations = []
    for animation in doc.get("animations",[]):
        channels = []; targets = set()
        for channel in animation["channels"]:
            target = channel["target"]
            if "node" not in target: continue
            node,path = target["node"],target["path"]
            if path not in ("translation","rotation","scale"): raise GltfError("Unsupported animation target: "+path)
            if not 0<=node<len(nodes) or nodes[node].matrix is not None: raise GltfError("Invalid animation target node")
            if (node,path) in targets: raise GltfError("Duplicate animation target")
            targets.add((node,path)); sampler = animation["samplers"][channel["sampler"]]
            times = [row[0] for row in reader.accessor(sampler["input"])]; values = reader.accessor(sampler["output"])
            mode = sampler.get("interpolation","LINEAR")
            if mode not in ("STEP","LINEAR","CUBICSPLINE"): raise GltfError("Unsupported interpolation")
            if not times or any(b<=a for a,b in zip(times,times[1:])): raise GltfError("Animation times must increase")
            if len(values)!=len(times)*(3 if mode=="CUBICSPLINE" else 1) or any(len(v)!=(4 if path=="rotation" else 3) for v in values): raise GltfError("Invalid animation output")
            channels.append((node,path,times,values,mode))
        animations.append(channels)
    if doc.get("scenes"):
        roots = doc["scenes"][doc.get("scene",0)].get("nodes",[])
    else: roots = [i for i,n in enumerate(nodes) if n.parent is None]
    active = set()
    def visit(i):
        if not 0<=i<len(nodes): raise GltfError("Invalid scene node")
        if i in active: return
        active.add(i)
        for child in doc["nodes"][i].get("children",[]): visit(child)
    for root in roots: visit(root)
    return Scene(nodes,meshes,skins,animations,sorted(active))
