# MuJoCo human and knee-exosuit simulation

This project was moved out of the OpenSim folder. Run its commands from this
`mujoco_simulation` folder. The source, models, previous outputs, original
archive, Python project and local `.venv` are preserved.

On this Mac, double-click **Launch_Human_Simulation.command**. For command-line
work:

```sh
.venv/bin/python -m human.run --actions 1 --output human_output/assisted
.venv/bin/mjpython -m human.view
.venv/bin/python -m unittest discover -s human/tests -v
```

See [human/README.md](human/README.md), [suit assumptions](human/EXOSUIT.md), and
[model provenance](human/native_backend/THIRD_PARTY.md).

OpenSim models and the continuous walking/plot viewer are in
[../simulation/](../simulation/README.md). SOFA and the legacy browser demo
have their own sibling folders. `MOVE_MANIFEST.json` records the relocation;
`PREVIOUS_SIMULATION_README.md` preserves the former mixed-project overview.
