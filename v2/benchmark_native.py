"""Compare Python and C++ Bresenham with the same hidden-window presentation."""
import argparse
import json
import statistics
import time
from pathlib import Path
from graphics_abstraction import Display
from graphics_abstraction.native_renderer import NativeRenderer
from automata import ModeloRecoleccion
from free_camera import FreeCamera
from gltf_loader import load_gltf
from simulation_view import SimulationView


def run(frames):
    scene = load_gltf(Path(__file__).parent / 'assets/characters/claw_lamp.glb')
    results = []
    for moving in (False, True):
        for backend in ('original', 'software_cached', 'native'):
            display = Display(960,540,hidden=True)
            if backend == 'native':
                display.renderer = NativeRenderer(960,540)
            view = SimulationView(ModeloRecoleccion(),scene,optimize=backend!='original')
            camera = FreeCamera(20)
            samples = []
            try:
                for i in range(frames+3):
                    display.events()
                    start = time.perf_counter()
                    camera.update({'left'} if moving else set(),1/60,960,540)
                    view.update(1/60,7)
                    if backend == 'original':
                        for claw in view.claws:
                            claw._drawables = None
                    display.renderer.clear()
                    view.draw(display.renderer,camera,'edges')
                    display.present('Bresenham benchmark | 7 claws | 960x540')
                    if i>=3:
                        samples.append((time.perf_counter()-start)*1000)
                results.append(dict(backend=backend,moving_camera=moving,frames=frames,
                    mean_ms=statistics.mean(samples), median_ms=statistics.median(samples),
                    fps=1000/statistics.mean(samples)))
            finally:
                display.close()
    Path(__file__).with_name('performance_native.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=int,default=30)
    args=parser.parse_args()
    if args.frames<1:
        parser.error('frames must be positive')
    run(args.frames)
