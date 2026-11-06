"""Claw, grid, one cube. E grabs or drops in the middle of a square."""
import argparse
from pathlib import Path
import time
import math
from gltf_loader import load_gltf
from level import StaticLevel
from graphics_abstraction.grid_floor import GridFloor
from character_animation import CharacterAnimation
from cube_logic import GridCube, CLAW_SCALE
from engine_3d import init, cleanup, camera as camera_type, window_context, timing_setup, update_frame, sync_frame
from game_logic import player as player_type, interaction_state, polling_based_inputs, event_based_inputs, move_player, move_camera, check_boundary
from math_functions import ModelingMachine, identity_matrix, translate, rotate_y, scale
from models import demo_models
from renderer_handler import Draw3D, DrawScene


def run(args):
    root = Path(__file__).resolve().parent
    character = load_gltf(root / 'assets' / 'characters' / 'claw_lamp.glb')
    level = None
    if args.scene and (not args.procedural):
        level = StaticLevel(args.scene)
        map = level.collision
        print(f'Room loaded: {len(map.mesh.tris)} triangles; spawn {level.spawn}')
    else:
        level = GridFloor()
        map = level.collision
    if args.headless:
        from graphics_abstraction import SoftwareRenderer
        window = window_context(None, args.width, args.height)
        r_r = SoftwareRenderer(args.width, args.height)
    else:
        window = init(args.width, args.height)
        r_r = window.display.renderer
    player = player_type()
    camera = camera_type()
    camera.yaw = 0.6
    camera.update_basis()
    player.physical.skin = character
    player.height = 2.0
    if level:
        player.intial_position = level.spawn
        player.physical.position = level.spawn
    cube = GridCube()
    animation = CharacterAnimation(character, cube)
    state = interaction_state()
    timing = timing_setup(window, 60)
    modeling = ModelingMachine()
    frame = 0
    try:
        while state.running and (not args.frames or frame < args.frames):
            timing.starting_frame = time.perf_counter()
            if args.headless:
                keys = set()
                timing.accumulator += timing.dt
            else:
                event_based_inputs(window.display.events(), state, window, camera)
                keys = window.display.keys()
                if 'escape' in keys:
                    state.running = False
                update_frame(timing)

            # same order as C++: keys, move, then camera
            while timing.accumulator >= timing.dt:
                polling_based_inputs(player, camera, timing.dt, keys)
                animation.prepare(player, keys)
                move_player(player, map, timing.dt)
                animation.update(player, keys, timing.dt)
                move_camera(camera, player, window)
                timing.accumulator -= timing.dt

            # camera also needs a value before the first tick, and after a resize
            move_camera(camera, player, window, level)

            # little optional trigger area, swap these bounds for your own
            inside_zone = args.demo_zone and check_boundary(player, (-3, 3), (5, 9))
            if state.rejected and (not inside_zone):
                state.rejected = False
            state.active = inside_zone and (not state.rejected)
            if state.clicked_positively:
                state.running = False

            # map first, claw next, prompt on top
            r_r.clear()
            if level:
                level.draw(r_r, camera.view, camera.proj, mode=args.mode)
            else:
                Draw3D(r_r, identity_matrix(), camera.proj, camera.view, map.buffer, args.mode)
            modeling.set_operations(translate(player.physical.position), rotate_y(player.yaw - math.pi / 2), scale(CLAW_SCALE))
            DrawScene(r_r, player.physical.skin, camera.proj, camera.view, modeling.collapse(), mode=args.mode)
            Draw3D(r_r, cube.matrix(player, character), camera.proj, camera.view,
                   cube.model.buffer, mode=args.mode)
            if not args.headless:
                prompt = 'Click here to finish; click outside to dismiss' if state.active else None
                action = 'drop' if cube.held else ('grab' if cube.can_grab(player) else 'enter cube cell')
                window.display.present(f'WASD move | arrows / wheel camera | Space jump | Shift sprint | E {action} | R reset [{animation.state}]', prompt=prompt)
                sync_frame(timing)
            frame += 1
        if args.output:
            r_r.save_ppm(args.output)
        if args.headless:
            print(f'Rendered {frame} frames; final frame: {r_r.points_drawn} pixel writes.')
    finally:
        if not args.headless:
            cleanup(window)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene', nargs='?', type=Path)
    parser.add_argument('--mode', choices=('edges', 'points'), default='edges')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--procedural', action='store_true', help='Use the infinite square grid (the default)')
    parser.add_argument('--demo-zone', action='store_true', help='Enable the sample interaction zone at x=-3..3, z=5..9')
    parser.add_argument('--frames', type=int, default=0)
    parser.add_argument('--width', type=int, default=960)
    parser.add_argument('--height', type=int, default=540)
    parser.add_argument('--output', type=Path, help='Save final CPU framebuffer as PPM')
    args = parser.parse_args()
    if args.width < 1 or args.height < 1 or args.frames < 0:
        parser.error('Invalid dimensions or frame count')
    if args.headless and (not args.frames):
        args.frames = 120
    run(args)
