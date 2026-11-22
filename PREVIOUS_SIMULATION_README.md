# Knee exosuit simulations

For **human walking without the suit**, use [human_walking/](human_walking/README.md).
It contains the bare OpenSim human, a normal walking motion and a phase-annotated
[knee-angle plot](human_walking/knee_angle_trajectory.png). Rebuild with
`.opensim-venv/bin/python -m opensim_exosuit.walking` from this folder.

An **OpenSim 4.6 model** is now available in [opensim_exosuit/](opensim_exosuit/README.md):
92 muscles, 23 coordinates, left-knee cuff mass/inertia, passive resistance and
a commandable assistance moment. Double-click **Build_OpenSim_Model.command**
to rebuild it and view the verified seated mechanical test. The main model is
`opensim_exosuit/output/knee_exosuit.osim`; keep its `Geometry/` folder beside it.

The current coupled human–exosuit simulation is in **human/**.
It now includes visible photo-inspired cuffs, pouches and hardware plus actual
carried inertia, passive drag and pressure-driven knee assistance.
See [exosuit controls and assumptions](human/EXOSUIT.md). It was updated from the
adjacent `new-RL` code on 24 October 2026. It uses native muscle-driven MuJoCo
walking and a simple adjustable PSI-to-knee-moment layer.

- [Open/run the human simulator](human/README.md)
- [Research: best simulation method for this project](human/RESEARCH.md)
- [Actual forward-simulation traces](human/validation/human_response.png)
- [Model/controller provenance and licenses](human/native_backend/THIRD_PARTY.md)

On this Mac, double-click **Launch_Human_Simulation.command**. The first launch
creates a local Python environment and installs project-local runtime dependencies; then it
opens the human–exosuit viewer. Press Space to pause, A to toggle illustrative
assistance and R to reset. The measured RL environment and tests are documented
in `human/README.md`.

The recommended workflow is MuJoCo/MyoSim/MyoAssist-derived forward human control
for timing-RL experiments, with OpenSim/Moco and held-out measurements for
personalization and independent biomechanical validation. The delivered model
is a functioning generic research prototype; activation proxies are not EMG,
and its pressure-to-torque gain is an adjustable assumption.

The earlier **sofa/** package remains available for SOFA actuator/soft-body
studies. Its source archive used a different two-pressure-channel control
contract; it is not the `new-RL` human environment. See its own README.

The earlier `knee-exosuit.html`, `model.js`, `build.py` and their tests are a
conceptual seated single-knee demonstration. Their documentation is preserved
in `LEGACY_CONCEPTUAL_README.md`. Use `human/` for the new walking work.
