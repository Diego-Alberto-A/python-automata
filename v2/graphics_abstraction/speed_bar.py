"""Shared speed selector artwork for both presentation backends."""
def draw_speed_bar(pg, font, index):
    surface = pg.Surface((280, 38), pg.SRCALPHA)
    surface.fill((20, 29, 40, 245))
    for i, label in enumerate(('x0.5', 'x1', 'x2', 'x4', 'x8')):
        box = pg.Rect(i * 56 + 3, 3, 50, 32)
        pg.draw.rect(surface, (65, 155, 190) if i == index else (35, 46, 60), box, border_radius=4)
        text = font.render(label, True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=box.center))
    return surface
