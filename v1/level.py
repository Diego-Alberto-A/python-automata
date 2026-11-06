"""Room meshes grouped up, plus nearby-triangle lookup for collisions."""
from collections import defaultdict, Counter
import math
from gltf_loader import load_gltf
from math_functions import v3, cross_product, dot_product, normalizado_vector, closest_point_on_triangle, identity_matrix, mult_ma, transform4
from models import map_mesh, model, tri


class TriangleGrid:
    def __init__(self, triangles, size=3.):
        self.size = size
        self.cells = defaultdict(list)
        self.triangles = triangles
        for triangle in triangles:
            for x in range(math.floor(triangle.min_x/size),math.floor(triangle.max_x/size)+1):
                for z in range(math.floor(triangle.min_z/size),math.floor(triangle.max_z/size)+1):
                    self.cells[x,z].append(triangle)

    def query(self, box):
        seen = set()
        for x in range(math.floor(box[0]/self.size),math.floor(box[1]/self.size)+1):
            for z in range(math.floor(box[2]/self.size),math.floor(box[3]/self.size)+1):
                for triangle in self.cells.get((x,z),()):
                    key = id(triangle)
                    if key not in seen:
                        seen.add(key)
                        yield triangle


class StaticLevel:
    def __init__(self,path):
        scene = load_gltf(path)
        groups = defaultdict(list)
        triangles = []
        floors = Counter()
        for mesh,points in scene.drawables():
            indices = mesh.indices or list(range(len(points)))
            for i in range(0,len(indices),3):
                a,b,c = (points[j] for j in indices[i:i+3])
                normal = cross_product(b-a,c-a)
                length = normal.length()
                if length<1e-9:
                    continue
                triangle = tri(a,b,c)
                triangles.append(triangle)
                if abs(normal.y)/length > .999:
                    floors[round((a.y+b.y+c.y)/3,2)] += length/2
                center = (a+b+c)*(1/3)
                groups[(math.floor(center.x/4),math.floor(center.z/4),mesh.color)].append((a,b,c))
        if not triangles:
            raise ValueError("Map contains no collision triangles")
        self.floor = floors.most_common(1)[0][0] if floors else min(t.min_y for t in triangles)
        self.collision = model("room",map_mesh(tris=triangles))
        self.grid = TriangleGrid(triangles)
        self.collision.mesh.spatial_index = self.grid
        self.batches = []
        for (_,_,color),faces in groups.items():
            vertices,indices,lookup = [],[],{}
            edges = defaultdict(list)
            points = []
            for face in faces:
                ids = []
                for p in face:
                    key = (round(p.x,5),round(p.y,5),round(p.z,5))
                    if key not in lookup:
                        lookup[key] = len(points)
                        points.append(p)
                        vertices.extend((p.x,p.y,p.z,0,1,0,0,0))
                    ids.append(lookup[key])
                indices.extend(ids)
                normal = normalizado_vector(cross_product(face[1]-face[0],face[2]-face[0]))
                for a,b in ((ids[0],ids[1]),(ids[1],ids[2]),(ids[2],ids[0])):
                    edges[min(a,b),max(a,b)].append(normal)
            mesh = map_mesh(vertices,indices=indices,color=tuple(max(28,int(c*.45)) for c in color))
            # same flat face on both sides of this edge? no shape there to draw
            mesh._edges = tuple(edge for edge,normals in edges.items()
                if len(normals)!=2 or abs(normals[0].x*normals[1].x+normals[0].y*normals[1].y+normals[0].z*normals[1].z)<.9999)
            lo = v3(min(p.x for p in points),min(p.y for p in points),min(p.z for p in points))
            hi = v3(max(p.x for p in points),max(p.y for p in points),max(p.z for p in points))
            corners = [(x,y,z,1) for x in (lo.x,hi.x) for y in (lo.y,hi.y) for z in (lo.z,hi.z)]
            self.batches.append((mesh,points,corners))
        self.spawn = self.find_spawn()
        self._frame_key = None

    def camera_position(self,target,desired):
        """Keep the camera out of furniture, orbit controls still do their thing."""
        direction = desired-target
        distance = direction.length()
        box = (min(target.x,desired.x),max(target.x,desired.x),
               min(target.z,desired.z),max(target.z,desired.z),
               min(target.y,desired.y),max(target.y,desired.y))
        nearest = 1.
        for triangle in self.grid.query(box):
            e1,e2 = triangle.b-triangle.a,triangle.c-triangle.a
            h = cross_product(direction,e2)
            det = dot_product(e1,h)
            if abs(det)<1e-9: continue
            s = target-triangle.a
            u = dot_product(s,h)/det
            if not 0<=u<=1: continue
            q = cross_product(s,e1)
            v = dot_product(direction,q)/det
            if v<0 or u+v>1: continue
            t = dot_product(e2,q)/det
            if .02<t<nearest: nearest = t
        return target+direction*max(.05,nearest-.15/max(distance,.001)) if nearest<1 else desired

    def find_spawn(self):
        triangles = self.grid.triangles
        min_x,max_x = min(t.min_x for t in triangles),max(t.max_x for t in triangles)
        min_z,max_z = min(t.min_z for t in triangles),max(t.max_z for t in triangles)
        center_x,center_z = (min_x+max_x)/2,(min_z+max_z)/2
        candidates = [(x,z) for x in range(math.ceil(min_x+1),math.floor(max_x))
                      for z in range(math.ceil(min_z+1),math.floor(max_z))]
        candidates.sort(key=lambda p:(p[0]-center_x)**2+(p[1]-center_z)**2)
        for x,z in candidates:
            feet = v3(x,self.floor+.03,z)
            nearby = list(self.grid.query((x-.8,x+.8,z-.8,z+.8,self.floor,self.floor+2)))
            support = any(abs(closest_point_on_triangle(v3(x,self.floor,z),t.a,t.b,t.c).y-self.floor)<.02
                          and (closest_point_on_triangle(v3(x,self.floor,z),t.a,t.b,t.c)-v3(x,self.floor,z)).length()<.02 for t in nearby)
            blocked = any((v3(x,feet.y+y,z)-closest_point_on_triangle(v3(x,feet.y+y,z),t.a,t.b,t.c)).length()<.79
                          for y in (.8,1.,1.2) for t in nearby)
            if support and not blocked:
                target = feet+v3(0,1,0)
                desired = feet+v3(-4.5,5,-6.6)
                if (self.camera_position(target,desired)-target).length()>5:
                    return feet
        raise ValueError("No clear floor spawn found; this map needs an explicit spawn")

    def draw(self,renderer,view,projection,mode="edges"):
        key = (view,projection,mode,renderer.width,renderer.height)
        if key == self._frame_key:
            renderer.pixels[:] = self._pixels
            renderer.depth[:] = self._depth
            return
        vp = mult_ma(projection,view)
        for mesh,points,corners in self.batches:
            clip = [transform4(vp,p) for p in corners]
            if any(all(p[3]+sign*p[axis]<0 for p in clip) for axis in range(3) for sign in (-1,1)):
                continue
            renderer.draw_mesh(mesh,identity_matrix(),view,projection,points,mode=mode)
        self._frame_key = key
        self._pixels = bytes(renderer.pixels)
        self._depth = renderer.depth.copy()
