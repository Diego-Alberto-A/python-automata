"""CPU drawing, only pull in Pygame when we actually open a window."""
from .software import SoftwareRenderer, bresenham, clip_line


class Display:

    def __init__(self, width=960, height=540, title='Shell3D Python', hidden=False):
        try:
            import pygame
        except ImportError as exc:
            raise RuntimeError('Install Pygame with: python -m pip install -r requirements.txt') from exc
        self.pygame = pygame
        pygame.display.init()
        pygame.font.init()

        # regular window here, no OpenGL flag or shader setup
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE | (pygame.HIDDEN if hidden else 0))
        pygame.display.set_caption(title)
        self.renderer = SoftwareRenderer(width, height)
        self.font = pygame.font.Font(None, 24)

    def events(self):
        pg = self.pygame
        result = []
        for event in pg.event.get():
            if event.type == pg.QUIT:
                result.append(('quit', None))
            elif event.type == pg.VIDEORESIZE:
                w, h = (max(1, event.w), max(1, event.h))
                self.screen = pg.display.set_mode((w, h), pg.RESIZABLE)
                self.renderer.resize(w, h)
                result.append(('resize', (w, h)))
            elif event.type == pg.MOUSEWHEEL:
                result.append(('wheel', event.y))
            elif event.type == pg.MOUSEBUTTONDOWN:
                result.append(('click', event.pos))
        return result

    def keys(self):
        pg = self.pygame
        keys = pg.key.get_pressed()
        names = {'w': pg.K_w, 'a': pg.K_a, 's': pg.K_s, 'd': pg.K_d, 'left': pg.K_LEFT, 'right': pg.K_RIGHT, 'up': pg.K_UP, 'down': pg.K_DOWN, 'space': pg.K_SPACE, 'r': pg.K_r, 'e': pg.K_e, 'escape': pg.K_ESCAPE, '1': pg.K_1, '2': pg.K_2, '3': pg.K_3, '4': pg.K_4, 'q': pg.K_q, 'home': pg.K_HOME, 'h': pg.K_h, 'n': pg.K_n}
        result = {name for name, key in names.items() if keys[key]}
        if keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT]:
            result.add('shift')
        return result

    def present(self, message=None, prompt=None, speed_index=None):
        pg = self.pygame
        r = self.renderer
        surface = pg.image.frombuffer(r.pixels, (r.width, r.height), 'RGB')
        self.screen.blit(surface, (0, 0))
        if message:
            for row, text in enumerate(message.splitlines()):
                self.screen.blit(self.font.render(text, True, (255, 255, 255)), (12, (58 if speed_index is not None else 12) + row * 25))
        if speed_index is not None:
            from .speed_bar import draw_speed_bar
            self.screen.blit(draw_speed_bar(pg, self.font, speed_index), (max(0, r.width - 292), 10))
        if prompt:
            rectangle = pg.Rect(round(r.width * 0.17), round(r.height * 0.18), round(r.width * 0.66), round(r.height * 0.64))
            pg.draw.rect(self.screen, (28, 40, 55), rectangle)
            pg.draw.rect(self.screen, (160, 210, 235), rectangle, 2)
            text = self.font.render(prompt, True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=rectangle.center))
        pg.display.flip()

    def close(self):
        self.pygame.quit()
