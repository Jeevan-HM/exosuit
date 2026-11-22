# OpenSim simulations

This folder contains the OpenSim models, walking data, plots and local runtime.
The other simulation engines have separate sibling folders in the parent
`exosuite` directory.

## Live OpenSim physics and knee angles

Double-click **Run_OpenSim_Physics.command** (or **View_Human_Walking.command**).
It starts the native OpenSim solver and opens its local viewer at
**http://127.0.0.1:8765/**. Keep the launcher window open while using the viewer;
press **Control-C** in that window to stop the solver.
Closing the Terminal window that runs the solver normally stops it as well.
Closing only the browser tab leaves the solver running. Reopening a launcher
while the solver is already running reconnects to that existing process.
If Codex started the solver, it is independent of Terminal. Double-click
**Stop_OpenSim_Physics.command** to stop that instance or any existing solver
started by this project's launcher. The shortcut verifies the OpenSim service
and its process before requesting a clean shutdown.

The animation and knee plot use the same state returned by
`OpenSim.Manager.integrate()`. The plotted angle is read from the native knee
coordinate after integration and converted to degrees with flexion positive.
The browser receives no reference gait angles or recorded poses.

Use **Pause**, **Reset**, the **Right/Left knee** selector, and the **Right-knee
torque pulse** button. The pulse adds +5 N·m of native knee-extension torque
for 0.4 simulation seconds. Speed changes how quickly the solver runs relative
to wall time; the plot's horizontal axis always shows simulation seconds.
Choose **0.1×** (ten times slower) or **0.25×** (four times slower) to inspect
the pose, and **Pause** to hold a position.
If the connection stops, both the trace and human pose freeze.

The skeleton view automatically uses a compatibility renderer if the browser
cannot start or loses its 3D graphics context. Both renderers use the same native
bone geometry and current solver poses. To explicitly select the compatibility
view, open **http://127.0.0.1:8765/?renderer=canvas**.

This is a **supported, torque-controlled human** with no exosuit. All 23
coordinates remain free and unprescribed. Walking targets feed a force
controller; actual motion is integrated under gravity. Virtual pelvis support
prevents free fall. Muscle forces are disabled, and foot–floor contact is not
implemented. This prototype demonstrates real solver output; it is not yet
autonomous muscle-driven walking or a patient-specific rehabilitation model.

The delivered model is [human_physics.osim](human_walking/human_physics.osim).
Run it through this launcher: its feedback policy lives in the Python solver,
so opening that model alone and pressing Creator's Run button will not apply
the walking controller. Actual live samples are saved to timestamped CSV files
under `human_walking/physics_output/`. The 30-second native integration and
force-response checks are recorded in
[physics_validation.json](human_walking/physics_validation.json).

For a terminal launch from this folder:

```sh
.opensim-venv/bin/python -m opensim_exosuit.physics_server
```

## Reference walking files

The human-only model and reference gait are in [human_walking/](human_walking/README.md).
There is no exosuit in this model.

For OpenSim Creator's green **Run** button, use
[human_walking_playback.osim](human_walking/human_walking_playback.osim).
Its coordinates follow a prescribed reference gait. The separate
`human_walking.osim` is the unconstrained research model; its displayed floor
has no collision forces and it has no walking controller, so free forward
dynamics will fall under gravity.

- Recorded gait playback: double-click **View_Reference_Walking.command**, or open [live_walking.html](human_walking/live_walking.html).
- Model: [human_walking.osim](human_walking/human_walking.osim), with its adjacent `Geometry/` folder.
- Motion: [normal_walking.mot](human_walking/normal_walking.mot).
- Knee figure: [PNG](human_walking/knee_angle_trajectory.png), [SVG](human_walking/knee_angle_trajectory.svg).
- Both knee trajectories: [CSV](human_walking/knee_angle_trajectory.csv).
- Looping preview: [human_walking.gif](human_walking/human_walking.gif).

The reference viewer uses the same OpenSim reference poses and one clock for
the walking animation and knee plots. It repeats the reference gait; it does
not predict autonomous walking or patient response.

In OpenSim Creator, open the bare model in the normal model editor, then choose
**File → Load Motion** and select the walking motion. In the simulator tab,
enable **loop** and press **Space** to play/pause. Right-click the right knee
coordinate under **jointset → knee_r → knee_angle_r**, choose
**Watch Output → value**, and show **Window → Output Watches**. Native coordinate
output uses radians and negative flexion; the exported knee figures and custom
viewer use degrees with positive flexion.

Rebuild the human-only model and static plot from this folder:

```sh
.opensim-venv/bin/python -m opensim_exosuit.walking
.opensim-venv/bin/python -m opensim_exosuit.walking_animation
.opensim-venv/bin/python -m opensim_exosuit.live_viewer
```

## OpenSim knee-exosuit work

The independently packaged [opensim_exosuit/](opensim_exosuit/README.md) retains
the optional knee-suit model, native mechanical tests and source attribution.
Double-click **Build_OpenSim_Model.command** to rebuild that model and its
seated mechanical diagnostic. The human-only walking viewer does not attach
the suit.

## Runtime and checks

The existing local runtime is `.opensim-venv` (OpenSim 4.6, including Moco).
For a new environment:

```sh
uv venv .opensim-venv --python 3.12
uv pip install --python .opensim-venv/bin/python -r opensim_exosuit/requirements-lock.txt
```

Run native OpenSim and pneumatic-helper checks:

```sh
.opensim-venv/bin/python -m unittest discover -s opensim_exosuit/tests -v
```

The OpenSim project has no runtime dependency on MuJoCo or SOFA.

## Other simulations

- [../mujoco_simulation/](../mujoco_simulation/README.md): muscle-driven MuJoCo human, device simulation, outputs, Python project, local runtime and launcher.
- [../sofa_simulation/](../sofa_simulation/README.md): SOFA soft-actuator studies and calibration data.
- [../legacy_browser_simulation/](../legacy_browser_simulation/README.md): earlier conceptual browser knee demo and its tests.

All source files and archived packages were relocated rather than deleted.
Each moved simulation folder includes a `MOVE_MANIFEST.json` with its old and
new paths. The hardware and RL source folders elsewhere in `exosuite` remain
separate from these simulation projects.
