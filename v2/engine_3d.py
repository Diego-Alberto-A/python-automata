"""Window setup and fixed steps, drawing stuff lives further down."""
from dataclasses import dataclass, field
import math
import time
from math_functions import v3, identity_matrix


@dataclass
class camera:
    yaw: float = 0.0
    pitch: float = 0.0
    distance: float = 8.0
    fwd: object = field(default_factory=lambda: v3(0, 0, 1))
    rgt: object = field(default_factory=lambda: v3(1, 0, 0))
    proj: tuple = field(default_factory=identity_matrix)
    view: tuple = field(default_factory=identity_matrix)

    def update_basis(self):
        self.fwd = v3(math.sin(self.yaw) * math.cos(self.pitch), math.sin(self.pitch), math.cos(self.yaw) * math.cos(self.pitch))
        self.rgt = v3(math.cos(self.yaw), 0, -math.sin(self.yaw))


@dataclass
class window_context:
    display: object
    window_width: int
    window_height: int


@dataclass
class timing_context:
    fps_cap: int = 60
    accumulator: float = 0.0
    last_counter: float = field(default_factory=time.perf_counter)
    starting_frame: float = field(default_factory=time.perf_counter)

    @property
    def dt(self):
        return 1 / self.fps_cap


def init(initial_width=960, initial_height=540, window_title='Shell3D Python'):
    from graphics_abstraction import Display
    return window_context(Display(initial_width, initial_height, window_title), initial_width, initial_height)


def timing_setup(context=None, desired_fps_cap=60):
    if desired_fps_cap <= 0:
        raise ValueError('FPS cap must be positive')
    return timing_context(desired_fps_cap)


def update_frame(timing):
    now = time.perf_counter()

    # window stalled? only catch up a bit, not the whole lost afternoon
    timing.accumulator += min(0.25, now - timing.last_counter)
    timing.last_counter = now


def sync_frame(timing):
    remaining = timing.dt - (time.perf_counter() - timing.starting_frame)
    if remaining > 0:
        time.sleep(remaining)


def cleanup(context):
    context.display.close()
