"""C++ Bresenham rasterizer; Python keeps ModelingMachine and simulation logic."""
import ctypes as ct
import os
from pathlib import Path
from .software import SoftwareRenderer
from math_functions import mult_ma


class NativeRenderer(SoftwareRenderer):
    def __init__(self, width, height):
        path = Path(__file__).parent / 'native' / ('bresenham.dll' if os.name == 'nt' else 'libbresenham.so')
        try:
            self.lib = ct.CDLL(str(path))
        except OSError as exc:
            raise RuntimeError('C++ renderer unavailable. Run python build_native.py or use --renderer software.') from exc
        byte_ptr, double_ptr = ct.POINTER(ct.c_uint8), ct.POINTER(ct.c_double)
        common = [byte_ptr, double_ptr, ct.c_int, ct.c_int]
        self.lib.clear_frame.argtypes = common + [byte_ptr]
        self.lib.clear_frame.restype = None
        self.lib.draw_line.argtypes = common + [double_ptr, byte_ptr]
        self.lib.draw_line.restype = ct.c_uint64
        self.lib.draw_mesh.argtypes = common + [double_ptr, ct.c_uint32,
            ct.POINTER(ct.c_uint32), ct.c_uint32, double_ptr, byte_ptr, ct.c_int]
        self.lib.draw_mesh.restype = ct.c_uint64
        self.resize(width, height)

    def resize(self, width, height):
        if width < 1 or height < 1:
            raise ValueError('Framebuffer dimensions must be positive')
        self.width, self.height = width, height
        self.pixels = bytearray(width * height * 3)
        self._pixels = (ct.c_uint8 * len(self.pixels)).from_buffer(self.pixels)
        self.depth = (ct.c_double * (width * height))()
        self._cache = {}
        self.clear()

    def clear(self, color=(15, 18, 23)):
        self.lib.clear_frame(self._pixels, self.depth, self.width, self.height,
                             (ct.c_uint8 * 3)(*color))
        self.points_drawn = 0

    def line(self, a, b, color):
        self.points_drawn += self.lib.draw_line(self._pixels, self.depth, self.width,
            self.height, (ct.c_double * 8)(*a, *b), (ct.c_uint8 * 3)(*color))

    def draw_mesh(self, mesh, model, view, projection, positions=None, color=None, mode='edges'):
        if mode not in ('edges', 'points'):
            raise ValueError('Drawing mode must be edges or points')
        cached = self._cache.get(id(mesh))
        if cached is None or cached[0] is not mesh or cached[1] is not positions:
            source = mesh.positions() if positions is None else positions
            xyz = (ct.c_double * (len(source)*3))(*(v for p in source for v in (p.x,p.y,p.z)))
            edge_list = mesh.edges()
            edges = (ct.c_uint32 * (len(edge_list)*2))(*(v for e in edge_list for v in e))
            cached = (mesh, positions, xyz, edges)
            if len(self._cache) > 256:
                self._cache.clear()
            self._cache[id(mesh)] = cached
        _, _, xyz, edges = cached
        mvp = mult_ma(projection, mult_ma(view, model))
        count = self.lib.draw_mesh(self._pixels, self.depth, self.width, self.height,
            xyz, len(xyz)//3, edges, len(edges)//2, (ct.c_double * 16)(*mvp),
            (ct.c_uint8 * 3)(*(mesh.color if color is None else color)), mode == 'points')
        if count == 2**64-1:
            raise MemoryError('Native mesh rasterization failed')
        self.points_drawn += count
