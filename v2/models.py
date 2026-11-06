"""Same mesh layout: position.xyz | normal.xyz | uv.xy.
Indices, joints and weights added for glTF, no GPU buffers here.
"""
from dataclasses import dataclass, field
from pathlib import Path
from math_functions import v3, identity_matrix, transform_point


@dataclass
class tri:
    a: object
    b: object
    c: object

    def __post_init__(self):
        for axis in ('x', 'y', 'z'):
            values = [getattr(p, axis) for p in (self.a, self.b, self.c)]
            setattr(self, 'min_' + axis, min(values))
            setattr(self, 'max_' + axis, max(values))


@dataclass
class map_mesh:
    vertices: list = field(default_factory=list)
    tris: list = field(default_factory=list)
    indices: list = field(default_factory=list)
    joints: list = field(default_factory=list)
    weights: list = field(default_factory=list)
    color: tuple = (160, 210, 235)
    _edges: object = field(default=None, init=False, repr=False)

    def positions(self):
        return [v3(*self.vertices[i:i + 3]) for i in range(0, len(self.vertices), 8)]

    def edges(self):
        if self._edges is None:
            edges = set()
            indices = self.indices or list(range(len(self.vertices) // 8))
            for i in range(0, len(indices), 3):
                a, b, c = indices[i:i + 3]
                edges.update(((min(u, v), max(u, v)) for u, v in ((a, b), (b, c), (c, a))))
            self._edges = tuple(sorted(edges))
        return self._edges

    def rebuild(self):
        self._edges = None
        p = self.positions()
        indices = self.indices or list(range(len(p)))
        self.tris = [tri(*(p[j] for j in indices[i:i + 3])) for i in range(0, len(indices), 3)]


@dataclass
class mesh_buffers:
    """Old buffer handle idea, but it holds CPU geometry now, no VAO/VBO ids."""
    mesh: map_mesh

    @property
    def vert_count(self):
        return len(self.mesh.vertices) // 8


@dataclass
class model:
    model_id: str
    mesh: map_mesh

    @property
    def buffer(self):
        return mesh_buffers(self.mesh)


@dataclass
class models_assets:
    characters: dict = field(default_factory=dict)
    maps: dict = field(default_factory=dict)


def createMesh(vertices, usage=None):
    mesh = map_mesh(list(vertices))
    mesh.rebuild()
    return mesh_buffers(mesh)


def updateMesh(buffer, vertices, usage=None):
    buffer.mesh.vertices = list(vertices)
    buffer.mesh.rebuild()


def load_assets(root='assets'):
    from gltf_loader import load_gltf
    result = models_assets()
    for kind in ('characters', 'maps'):
        folder = Path(root) / kind
        if folder.exists():
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in ('.gltf', '.glb'):
                    getattr(result, kind)[path.stem] = load_gltf(path)
    return result


def collision_model(scene):
    """Turn the current pose into collision triangles, just a snapshot."""
    vertices = []
    for mesh, positions in scene.drawables():
        indices = mesh.indices or list(range(len(positions)))
        for index in indices:
            p = positions[index]
            vertices.extend((p.x, p.y, p.z, 0, 1, 0, 0, 0))
    mesh = map_mesh(vertices)
    mesh.rebuild()
    return model('scene_collision', mesh)


def demo_models():

    def make(name, points, indices, color):
        mesh = map_mesh([value for p in points for value in (*p, 0, 1, 0, 0, 0)], indices=indices, color=color)
        mesh.rebuild()
        return model(name, mesh)
    ground = make('ground', [(-15, 0, -15), (15, 0, -15), (15, 0, 15), (-15, 0, 15)], [0, 2, 1, 0, 3, 2], (90, 160, 120))
    cube = make('player', [(-0.6, 0, -0.6), (0.6, 0, -0.6), (0.6, 1.6, -0.6), (-0.6, 1.6, -0.6), (-0.6, 0, 0.6), (0.6, 0, 0.6), (0.6, 1.6, 0.6), (-0.6, 1.6, 0.6)], [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1, 3, 2, 6, 3, 6, 7, 1, 5, 6, 1, 6, 2, 0, 3, 7, 0, 7, 4], (240, 190, 95))
    return (ground, cube)
