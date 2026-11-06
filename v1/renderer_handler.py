"""Same drawing entry points, actual pixel work is in graphics_abstraction."""
from math_functions import identity_matrix


def createRenderer(context):
    return context.display.renderer


def Draw3D(renderer, model, proj, view, mesh_buffer, mode='edges'):
    renderer.draw_mesh(mesh_buffer.mesh, model, view, proj, mode=mode)


def DrawScene(renderer, scene, proj, view, model=None, mode='edges'):
    model = identity_matrix() if model is None else model
    for mesh, positions in scene.drawables():
        renderer.draw_mesh(mesh, model, view, proj, positions, mode=mode)
