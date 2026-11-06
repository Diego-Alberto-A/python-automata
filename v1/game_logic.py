"""Movement, camera and capsule-ish collisions, same general deal as the C++ one."""
from dataclasses import dataclass, field
import math
from math_functions import v3, dot_product, cross_product, normalizado_vector, normalize_angle, closest_point_on_triangle, perspective, look_at


@dataclass
class entity:
    position: object = field(default_factory=lambda: v3(0, 2, 0))
    skin: object = None


@dataclass
class collide_info:
    hit: bool = False
    grounded: bool = False
    ceiling: bool = False
    hit_normal: object = field(default_factory=v3)


@dataclass
class player:
    physical: entity = field(default_factory=entity)
    intial_position: object = field(default_factory=lambda: v3(0, 2, 0))
    move: object = field(default_factory=v3)
    ci: collide_info = field(default_factory=collide_info)
    yaw: float = 0.0
    speed: float = 6.0
    radius: float = 0.8
    height: float = 1.0
    vel_y: float = 0.0
    jump_force: float = 6.0


@dataclass
class interaction_state:
    running: bool = True
    active: bool = False
    clicked_positively: bool = False
    rejected: bool = False


def event_based_inputs(events, state, window, camera):
    for kind, value in events:
        if kind == 'quit':
            state.running = False
        elif kind == 'resize':
            window.window_width, window.window_height = value
        elif kind == 'wheel':
            camera.distance = max(2.0, min(20.0, camera.distance - value))
        elif kind == 'click' and state.active:
            x, y = value
            inside = 0.17 * window.window_width <= x <= 0.83 * window.window_width and 0.18 * window.window_height <= y <= 0.82 * window.window_height
            if inside:
                state.clicked_positively = True
            else:
                state.rejected = True


def polling_based_inputs(player, camera, dt, keys):
    # turn the camera here
    if 'left' in keys:
        camera.yaw += 1.8 * dt
    if 'right' in keys:
        camera.yaw -= 1.8 * dt
    if 'up' in keys:
        camera.pitch += 1.8 * dt
    if 'down' in keys:
        camera.pitch -= 1.8 * dt
    camera.yaw = normalize_angle(camera.yaw)
    camera.pitch = max(-1.2, min(1.2, camera.pitch))
    camera.update_basis()

    # A/D kept the same way round as C++, so no relearning controls
    player.move = v3(0, 0, 0)
    if 'w' in keys:
        player.move = player.move + camera.fwd
    if 's' in keys:
        player.move = player.move - camera.fwd
    if 'a' in keys:
        player.move = player.move + camera.rgt
    if 'd' in keys:
        player.move = player.move - camera.rgt
    if 'space' in keys:
        if player.ci.grounded:
            player.vel_y = player.jump_force

    # shift means run
    if 'shift' in keys:
        player.speed = 12.0
    else:
        player.speed = 6.0

    # back to spawn
    if 'r' in keys:
        player.physical.position = player.intial_position
        player.vel_y = 0.0


def collide_and_slide_capsuleish(pos, disp, radius, height, tris):
    up = v3(0, 1, 0)
    walkable = math.cos(math.radians(85))
    skin = 0.0015
    # this fucking capsule still needs room for its spheres, even if height is tiny
    h = max(height, radius * 2 + 0.001)

    def bounds(p, target):
        return (min(p.x, target.x) - radius, max(p.x, target.x) + radius, min(p.z, target.z) - radius, max(p.z, target.z) + radius, min(p.y, target.y) - radius, max(p.y + h, target.y + h) + radius)
    target = pos + disp
    box = bounds(pos, target)
    pos = target
    info = collide_info()
    for _ in range(6):
        best_pen = 0.0
        best_n = v3()
        y0, y1 = (pos.y + radius, pos.y + h - radius)
        samples = (v3(pos.x, y0, pos.z), v3(pos.x, (y0 + y1) * 0.5, pos.z), v3(pos.x, y1, pos.z))
        candidates = tris.query(box) if hasattr(tris, 'query') else tris
        for t in candidates:
            if t.max_x < box[0] or t.min_x > box[1] or t.max_z < box[2] or (t.min_z > box[3]) or (t.max_y < box[4]) or (t.min_y > box[5]):
                continue
            tri_n = cross_product(t.b - t.a, t.c - t.a)
            if tri_n.sqr_length() < 1e-10:
                continue
            for sample in samples:
                d = sample - closest_point_on_triangle(sample, t.a, t.b, t.c)
                d2 = d.sqr_length()
                if d2 < radius * radius:
                    distance = math.sqrt(max(1e-12, d2))
                    penetration = radius - distance
                    if distance > 1e-06:
                        normal = d * (1 / distance)
                    else:
                        normal = normalizado_vector(tri_n)
                        if dot_product(normal, disp) > 0:
                            normal = normal * -1
                    if penetration > best_pen:
                        best_pen, best_n = (penetration, normal)
        if best_pen <= 0:
            break
        info.hit = True
        info.hit_normal = best_n
        align = dot_product(best_n, up)
        if align >= walkable:
            info.grounded = True
        if align <= -0.5:
            info.ceiling = True
        pos = pos + best_n * (best_pen + skin)
        into = dot_product(disp, best_n)
        if into < 0:
            disp = disp - best_n * into
        box = bounds(pos, pos + disp)
    return (pos, disp, info)


def move_player(player, map, dt):
    if player.move.length() > 0.001:
        target = math.atan2(player.move.x, player.move.z)
        step = math.pi * dt
        delta = normalize_angle(target - player.yaw)
        if abs(delta) <= step:
            player.yaw = target
        else:
            player.yaw += step * (1.0 if delta > 0 else -1.0)
    player.move = normalizado_vector(player.move)
    gravity = 10.0
    player.vel_y -= gravity * dt
    disp = v3(player.move.x * player.speed * dt, player.vel_y * dt, player.move.z * player.speed * dt)

    # dotted floor = check the height, thats it, no triangles
    if hasattr(map, 'floor_height'):
        position = player.physical.position + disp
        grounded = position.y <= map.floor_height
        if grounded:
            position = v3(position.x, map.floor_height, position.z)
        player.physical.position = position
        player.ci = collide_info(hit=grounded, grounded=grounded, hit_normal=v3(0, 1, 0) if grounded else v3())
    else:
        player.physical.position, disp, player.ci = collide_and_slide_capsuleish(player.physical.position, disp, player.radius, player.height, getattr(map.mesh, 'spatial_index', map.mesh.tris))
    if player.ci.grounded and player.vel_y < 0:
        player.vel_y = 0.0
    if player.ci.ceiling and player.vel_y > 0:
        player.vel_y = 0.0
    if player.physical.position.y < -100:
        player.physical.position = player.intial_position
        player.vel_y = 0.0


def move_camera(camera, player, window, level=None):
    cam_pos = player.physical.position + camera.fwd * -camera.distance + v3(0, 5, 0)
    target = player.physical.position + v3(0, 1, 0)
    if level is not None:
        cam_pos = level.camera_position(target, cam_pos)
    camera.proj = perspective(math.radians(60), window.window_width / max(1, window.window_height), 0.1, 500.0)
    camera.view = look_at(cam_pos, target, v3(0, 1, 0))


def check_boundary(player, x_range, z_range):
    p = player.physical.position
    return min(x_range) <= p.x <= max(x_range) and min(z_range) <= p.z <= max(z_range)
