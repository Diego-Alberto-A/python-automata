"""Try the four claw animations in our renderer.
1 jump, 2 pickup, 3 drop, 4 slam, Space pause, arrows orbit, wheel zoom, R restart.
Cyan block is just a test prop, not part of the exported claw.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import argparse
import math
from pathlib import Path
import time
from gltf_loader import load_gltf
from graphics_abstraction import Display, SoftwareRenderer
from math_functions import v3, perspective, look_at, identity_matrix, translate, scale, mult_ma
from models import demo_models
from renderer_handler import DrawScene, Draw3D
from cube_logic import GridCube, CUBE_LOCAL_SIZE, GRIP_Y

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT/"assets"/"characters"/"claw_lamp.glb"
DURATIONS = (2.2,3.0,2.3,.85)
NAMES = ('Jump', 'Pickup', 'Drop', 'Slam')


def draw(renderer,scene,clip,seconds,yaw=.30,distance=6.2):
    scene.animate(seconds,clip,loop=False)
    projection = perspective(math.radians(48),renderer.width/renderer.height,.1,100)
    target = v3(.35,1.65,0)
    eye = target+v3(math.sin(yaw)*distance,1.05,math.cos(yaw)*distance)
    view = look_at(eye,target,v3(0,1,0))
    renderer.clear((15,18,23))
    # test grid uses the same Bresenham lines, nothing fancy
    from math_functions import transform4
    vp = mult_ma(projection,view)
    for i in range(-4,5):
        for a,b in [((i,0,-4,1),(i,0,4,1)),((-4,0,i,1),(4,0,i,1))]:
            renderer.line(transform4(vp,a),transform4(vp,b),(34,48,57))
    DrawScene(renderer,scene,projection,view)
    if clip in (1,2):
        cube = GridCube()
        matrix = translate(v3(1.25,CUBE_LOCAL_SIZE/2,0))
        if (clip == 1 and seconds >= 1.9) or (clip == 2 and seconds < 1.):
            matrix = mult_ma(scene.nodes[3].machine.collapse(), translate(v3(0,GRIP_Y,0)))
        Draw3D(renderer,mult_ma(matrix,scale(CUBE_LOCAL_SIZE)),projection,view,cube.model.buffer)


def preview(scene):
    import pygame
    pygame.font.init()
    width,height = 420,360
    sheet = pygame.Surface((width*3,height*2))
    font = pygame.font.Font(None,23)
    samples = [(0,.95,"JUMP / airborne"),(3,.18,"SLAM / falling"),(3,.44,"SLAM / impact"),
               (1,1.9,"PICKUP / grip"),(1,3.,"PICKUP / hold"),(2,1.5,"DROP / released")]
    renderer = SoftwareRenderer(width,height)
    for i,(clip,seconds,label) in enumerate(samples):
        draw(renderer,scene,clip,seconds)
        surface = pygame.image.frombuffer(renderer.pixels,(width,height),"RGB")
        x,y = (i%3)*width,(i//3)*height
        sheet.blit(surface,(x,y))
        sheet.blit(font.render(label,True,(235,235,220)),(x+12,y+12))
    path = ROOT/"assets"/"characters"/"claw_preview.png"
    pygame.image.save(sheet,str(path))
    pygame.font.quit()
    print(path)


def run(args):
    scene = load_gltf(ASSET)
    if args.preview:
        preview(scene)
        return
    display = Display(960,720,"Claw Lamp | 1 Jump | 2 Pickup | 3 Drop | 4 Slam")
    clip = args.animation
    seconds = 0.
    paused = False
    previous = set()
    yaw,distance = .30,6.2
    last = time.perf_counter()
    frame = 0
    try:
        running = True
        while running and (not args.frames or frame<args.frames):
            now = time.perf_counter()
            dt = min(.1,now-last)
            last = now
            for kind,value in display.events():
                if kind=="quit": running = False
                elif kind=="wheel": distance = max(3,min(12,distance-value*.4))
            keys = display.keys()
            pressed = keys-previous
            if "escape" in keys: running = False
            for key,index in (("1",0),("2",1),("3",2),("4",3)):
                if key in pressed: clip,seconds = index,0.
            if "space" in pressed: paused = not paused
            if "r" in pressed: seconds = 0.
            yaw += (int("right" in keys)-int("left" in keys))*dt
            if not paused:
                seconds = seconds + dt
                seconds = seconds % DURATIONS[clip] if clip == 0 else min(seconds,DURATIONS[clip])
            draw(display.renderer,scene,clip,seconds,yaw,distance)
            display.present(f"{NAMES[clip]} | 1 / 2 / 3 / 4 switch | Space pause | arrows orbit | wheel zoom | R restart")
            previous = keys
            frame += 1
            time.sleep(max(0,1/30-(time.perf_counter()-now)))
    finally:
        display.close()


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animation",type=int,choices=(0,1,2,3),default=0)
    parser.add_argument("--frames",type=int,default=0)
    parser.add_argument("--preview",action="store_true")
    run(parser.parse_args())
