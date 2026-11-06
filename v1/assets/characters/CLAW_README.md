# Claw lamp

Eight-joint mechanical skeleton, 780 triangles, four materials. GLB and embedded
buffer glTF versions are equivalent. The game loads GLB directly; the generator
in tests is only for rebuilding assets.

Clips:

0. Jump: 2.2 seconds, loops in place.
1. Pickup: 3.0 seconds, closes and lifts, ends holding.
2. Drop: 2.3 seconds, lowers, releases, retracts.
3. Slam: 0.85 seconds, freefall, compression, recovery.

The runtime slam starts from the current walking pose rather than blindly
starting the exported clip. Pickup and drop are now separate, non-looping actions.
The finger pads close vertically around a cube approximately 0.1644 local units
across (0.1315 world units with the player's 0.8 scale). Grip measurements live in
cube_logic.py and are shared with the builder.

Actual attachment and cell placement are gameplay logic, not glTF constraints.
The exported mesh contains JOINTS_0, WEIGHTS_0 and inverse bind matrices, with
rigid weights for metal links. Y is up.

From Automata:

```sh
python tests/claw_demo.py
python tests/claw_demo.py --animation 2
python tests/create_claw.py
python tests/claw_demo.py --preview
python -m unittest tests.test_claw tests.test_cube -v
```

Viewer keys: 1 jump, 2 pickup, 3 drop, 4 slam, Space pause, R restart.
