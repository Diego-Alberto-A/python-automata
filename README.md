# Automata

Autonomous claws collect cubes on a 3D grid. AgentPy runs the automata and Python handles
animation; a C++ Bresenham renderer draws the scene with per-pixel depth testing.
A Python Bresenham backend is also available.

- `v1/`: original manually controlled claw.
- `v2/`: autonomous claws, floating camera, and optimized renderer.

## Run

The local Windows environment is `.venv` (Python 3.12), with both Pygame and
AgentPy installed. Double-click `run.cmd` to run the game with this environment.
For Python commands, use `.\.venv\Scripts\python.exe` rather than the MSYS2 Python
on PATH. `v2/automata.py` uses real AgentPy agents, model, grid, and agent list;
the viewer advances their turns individually to animate them.

For a fresh setup, use standard Python 3.12 and a C++17 compiler (`g++` or `clang++` on PATH).
Run these commands from the project root using the same Python installation:

```sh
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r v2/requirements.txt
.venv\Scripts\python.exe v2/build_native.py
run.cmd
```

The native library is generated locally and excluded from Git. Set `CXX` to a
compiler executable path if needed. To run without compiling:

```sh
run.cmd --renderer software
```

## Controls

- WASD: fly; E/Q: rise/descend; arrows: look; wheel: move forward/back.
- Space: pause simulation and animation while keeping the camera free.
- Shift: cycle x0.5, x1, x2, x4, x8. The top-right bar shows the speed.
- H: toggle red, undiscovered cubes; R: restart; Home: overview; Escape: exit.
- N: advance one robot turn while paused.

Default: 20×20 grid, seven claws, 20 cubes. Use `--size 100` for a larger grid;
run `run.cmd --help` for all options.