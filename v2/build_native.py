"""Build the optional C++ Bresenham library. No packages or global installation."""
from pathlib import Path
import os
import shutil
import subprocess

root = Path(__file__).resolve().parent / 'graphics_abstraction' / 'native'
compiler = os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++')
if not compiler:
    raise SystemExit('Install a C++ compiler or set CXX to its path.')
output = root / ('bresenham.dll' if os.name == 'nt' else 'libbresenham.so')
command = [compiler, '-std=c++17', '-O3', '-ffp-contract=off', '-shared',
           str(root / 'bresenham.cpp'), '-o', str(output)]
command += ['-static', '-static-libgcc', '-static-libstdc++'] if os.name == 'nt' else ['-fPIC']
subprocess.run(command, check=True)
print(f'Built {output}')
