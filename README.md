# Automata

Autonomous claws collect cubes on a 3D grid. Python runs the automata and
animation; a C++ Bresenham renderer draws the scene with per-pixel depth testing.
A Python Bresenham backend is also available.

- `v1/`: original manually controlled claw.
- `v2/`: autonomous claws, floating camera, and optimized renderer.

## Run

Requires Python 3.10+, Pygame, and a C++17 compiler (`g++` or `clang++` on PATH).
Run these commands from the project root using the same Python installation:

```sh
python -m pip install -r v2/requirements.txt
python v2/build_native.py
python v2/main.py
```

The native library is generated locally and excluded from Git. Set `CXX` to a
compiler executable path if needed. To run without compiling:

```sh
python v2/main.py --renderer software
```

## Controls

- WASD: fly; E/Q: rise/descend; arrows: look; wheel: move forward/back.
- Space: pause simulation and animation while keeping the camera free.
- Shift: cycle x0.5, x1, x2, x4, x8. The top-right bar shows the speed.
- H: toggle red, undiscovered cubes; R: restart; Home: overview; Escape: exit.
- N: advance one robot turn while paused.

Default: 20×20 grid, seven claws, 20 cubes. Use `--size 100` for a larger grid;
run `python v2/main.py --help` for all options.

## Checks

After building the native library:

```sh
cd v2
python -m unittest -v
python main.py --headless --frames 120
python benchmark_native.py --frames 30
```

The benchmark uses hidden windows and saves local timing results. Tests compare
C++ and Python rendering pixel-for-pixel and check the automata's collection rules.
