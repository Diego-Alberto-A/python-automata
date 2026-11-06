"""A few snapshots of the actual controller, not just playing clips by hand."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import math
import pygame
from tests.test_cube import CubeTests
from graphics_abstraction import SoftwareRenderer
from math_functions import v3, perspective, look_at
from cube_logic import player_matrix
from renderer_handler import DrawScene, Draw3D


def preview():
    case = CubeTests()
    case.setUp()
    pygame.font.init()
    font = pygame.font.Font(None, 24)
    renderer = SoftwareRenderer(480, 400)
    sheet = pygame.Surface((1440, 800))
    index = 0

    def snapshot(label):
        nonlocal index
        target = case.player.physical.position + v3(0, .85, 0)
        view = look_at(target + v3(1.3, 1.2, 4), target, v3(0,1,0))
        projection = perspective(math.radians(45), 1.2, .1, 100)
        renderer.clear()
        case.floor.draw(renderer, view, projection)
        DrawScene(renderer, case.scene, projection, view, player_matrix(case.player))
        Draw3D(renderer, case.cube.matrix(case.player, case.scene), projection,
               view, case.cube.model.buffer)
        image = pygame.image.frombuffer(renderer.pixels, (480,400), 'RGB')
        x, y = index % 3 * 480, index // 3 * 400
        sheet.blit(image, (x,y))
        sheet.blit(font.render(label, True, (240,240,230)), (x+12,y+12))
        index += 1

    snapshot('Grid cell (0, 0)')
    case.tick({'e'}, 114)
    snapshot('Pickup: jaws meet the cube')
    case.tick(set(), 80)
    snapshot('Carrying: cube follows the wrist')
    case.tick({'w'}, 55)
    case.tick(set())
    snapshot('Stopped: falling into the slam')
    case.tick(set(), 70)
    case.tick({'w','e'}, 60)
    snapshot('Drop: snapped to the next cell')
    case.tick(set(), 100)
    snapshot('Released: center of the square')
    output = Path(__file__).with_name('grid_actions.png')
    pygame.image.save(sheet, str(output))
    pygame.font.quit()
    print(output)


if __name__ == '__main__':
    preview()
