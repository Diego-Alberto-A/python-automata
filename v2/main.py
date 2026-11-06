"""Autonomous collection claws on a 3D grid, with a free spectator camera."""
import argparse
from pathlib import Path
import time
from automata import ModeloRecoleccion
from engine_3d import init, cleanup, window_context
from free_camera import FreeCamera
from gltf_loader import load_gltf
from simulation_view import SimulationView


def run(args):
    scene = load_gltf(Path(__file__).parent / 'assets/characters/claw_lamp.glb')
    def restart():
        return SimulationView(ModeloRecoleccion(args.size, args.robots, args.cubes,
                              args.vision, args.seed, args.steps), scene)
    simulation = restart()
    camera = FreeCamera(args.size)
    if args.headless:
        from graphics_abstraction import SoftwareRenderer
        window = window_context(None, args.width, args.height)
        if args.renderer == 'native':
            from graphics_abstraction.native_renderer import NativeRenderer
            renderer = NativeRenderer(args.width, args.height)
        else:
            renderer = SoftwareRenderer(args.width, args.height)
    else:
        window = init(args.width, args.height, 'Automata v2 | Python Bresenham')
        if args.renderer == 'native':
            from graphics_abstraction.native_renderer import NativeRenderer
            try:
                window.display.renderer = NativeRenderer(args.width, args.height)
                window.display.pygame.display.set_caption('Automata v2 | C++ Bresenham')
            except RuntimeError as exc:
                print(f'{exc} Falling back to Python Bresenham.')
        renderer = window.display.renderer
    previous = set()
    paused = False
    multipliers = (.5, 1, 2, 4, 8)
    speed_index = 1
    last = time.perf_counter()
    frame = 0
    try:
        while not args.frames or frame < args.frames:
            start = time.perf_counter()
            dt = 1/60 if args.headless else min(.1, start - last)
            last = start
            keys = set()
            if not args.headless:
                quit_requested = False
                for kind, value in window.display.events():
                    if kind == 'quit':
                        quit_requested = True
                    elif kind == 'resize':
                        window.window_width, window.window_height = value
                    elif kind == 'wheel':
                        camera.position += camera.fwd * value * 3
                keys = window.display.keys()
                if quit_requested or 'escape' in keys:
                    break
            pressed = keys - previous
            previous = keys
            if 'space' in pressed:
                paused = not paused
            if 'r' in pressed:
                simulation = restart()
            if 'home' in pressed:
                camera.reset()
            if 'h' in pressed:
                simulation.show_hidden = not simulation.show_hidden
            if 'shift' in pressed:
                speed_index = (speed_index + 1) % len(multipliers)
            speed = args.speed * multipliers[speed_index]
            camera.update(keys, dt, window.window_width, window.window_height)
            if not paused:
                simulation.update(dt, speed)
            elif 'n' in pressed:
                simulation.update((1. - simulation.elapsed) / speed, speed)
            renderer.clear()
            simulation.draw(renderer, camera, args.mode)
            if not args.headless:
                model = simulation.model
                status = ('COMPLETE' if model.complete else 'STEP LIMIT' if model.finished
                          else 'PAUSED' if paused else 'RUNNING')
                pending = simulation.active is not None or any(c.drop_clock is not None for c in simulation.claws)
                if paused:
                    status = 'PAUSED'
                elif model.finished and pending:
                    status = 'FINISHING'
                window.display.present(
                    f'{status} | Round {model.t} | Delivered {model.entregados}/{args.cubes}'
                    f' | Blocked {sum(r.bloqueos for r in model.robots)} | {speed:g} turns/s\n'
                    'WASD fly | E/Q rise/fall | Arrows look | Wheel dolly | Home overview\n'
                    'Space pause | N next turn | Shift speed | H hidden cubes | R restart | Esc exit',
                    speed_index=speed_index)
                time.sleep(max(0., 1/60 - (time.perf_counter() - start)))
            frame += 1
        if args.output:
            renderer.save_ppm(args.output)
        print(f'Rendered {frame} frames; round {simulation.model.t}; '
              f'delivered {simulation.model.entregados}/{args.cubes}')
    finally:
        if not args.headless:
            cleanup(window)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--size', type=int, default=20)
    parser.add_argument('--robots', type=int, default=7)
    parser.add_argument('--cubes', type=int, default=20)
    parser.add_argument('--vision', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--steps', type=int, default=40000)
    parser.add_argument('--speed', type=float, default=7., help='Individual robot turns per second')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--renderer', choices=('native', 'software'), default='native',
                        help='C++ Bresenham or Python Bresenham')
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--width', type=int, default=960)
    parser.add_argument('--height', type=int, default=540)
    parser.add_argument('--mode', choices=('edges', 'points'), default='edges')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if min(args.width, args.height) < 1 or args.frames < 0 or not 0 < args.speed <= 200:
        parser.error('Use positive dimensions, nonnegative frames and speed in (0, 200]')
    if args.headless and not args.frames:
        args.frames = 120
    try:
        run(args)
    except ValueError as exc:
        parser.error(str(exc))
