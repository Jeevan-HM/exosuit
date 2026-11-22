# OpenSim pneumatic knee exosuit

This package builds a native OpenSim model of the project's **left-knee pneumatic
exosuit**, using the official Gait2392 human model. The full model retains
**92 muscles and 23 movement coordinates**. The suit adds welded cuff/sleeve
mass and inertia, passive knee resistance, and a commandable knee moment.

The ready-to-open model is `output/knee_exosuit.osim`. Keep its adjacent
`Geometry/` folder with it. The Python runtime is installed locally in
`simulation/.opensim-venv`; it includes OpenSim 4.6 and Moco. The OpenSim desktop
application is a separate installation. A rendered preview is already included
at `output/preview.png`.

## Build and view

On this Mac, double-click **Build_OpenSim_Model.command** in the parent
`simulation` folder. It builds the model, runs the seated mechanical check,
opens the preview/results folder and refreshes `OpenSim_Knee_Exosuit.zip`.
The first launch on another computer downloads the local Python dependencies.

From the `simulation` folder:

```sh
.opensim-venv/bin/python -m opensim_exosuit.demo
```

To build only the full models, without running the fixture:

```sh
.opensim-venv/bin/python -m opensim_exosuit.builder
```

For a fresh Python 3.12 installation:

```sh
uv venv .opensim-venv --python 3.12
uv pip install --python .opensim-venv/bin/python -r opensim_exosuit/requirements-lock.txt
```

The [official OpenSim Python guide](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085346/Scripting+in+Python)
documents the OpenSim 4.6 Python packages and supported platforms. The model
generator does not depend on the desktop application.

## Open in OpenSim desktop

### See the human walking

An official normal walking motion is included as `output/normal_walking.mot`.
It contains a one-second gait cycle and plays the human wearing the suit walking
in place. It is reference-motion playback; it does not show a simulated benefit
from assistance. The unchanged source, hashes and provenance are in
[assets/walking/PROVENANCE.md](assets/walking/PROVENANCE.md).

In **OpenSim Creator 0.8**, use the home screen's **Preview Experimental Data**
workflow. Click **load model** and choose `output/knee_exosuit.osim`, then
**load model trajectory sto/mot file** and choose `output/normal_walking.mot`.
Use the time slider to move through the walking cycle. Use the playback
controls if available in your app version.
[Creator's official motion-preview instructions](https://docs.opensimcreator.com/manual/en/latest/preview-experimental-data.html).

In the **OpenSim desktop application**, open `output/knee_exosuit.osim`, select
**File → Load Motion**, choose `output/normal_walking.mot`, and press **Play**
in the animation toolbar. Enable looping for continuous walking.
[Official OpenSim instructions](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53089231).

### Inspect the model or seated mechanics

1. Open `output/knee_exosuit.osim` through **File → Open Model** to inspect the
   full model with muscles and suit geometry.
2. To play the verified mechanical demonstration, open
   `output/seated_assisted.osim`, then load its matching
   `output/seated_assisted.mot` through the motion-loading command.
3. The unpowered and bare conditions have matching model/motion pairs. The
   `.mot` files store all coordinates in radians, with `inDegrees=no`.

The full model has a floating pelvis, all inherited coordinates free, and no
human motor controller or ground-contact forces. Forward walking requires
additional control/contact modeling or measured motion and external forces.
The model can be used as a foundation for scaling, inverse kinematics, inverse
dynamics and later muscle/control optimization; those analyses are not
configured or clinically validated by this package.

## Included conditions

| Model | Human muscles | Suit mass and drag | Active input |
|---|---|---|---|
| `human_bare.osim` | 92 enabled | None | None |
| `knee_exosuit_unpowered.osim` | 92 enabled | Included | None |
| `knee_exosuit.osim` | 92 enabled | Included | Commandable signed knee moment; zero default input |
| `seated_*.osim` | Forces disabled for the diagnostic | Depends on condition | Illustrative timed profile in the assisted condition |

The original human mass is 75.1646 kg; the two worn models have mass 75.6146 kg.
This is a different generic human from the project's MuJoCo model. Matching
device parameters does not establish matching human responses between engines.
Original human anatomy and muscle properties are preserved. The source model,
20 anatomical meshes, exact source hashes and credits are in
[assets/PROVENANCE.md](assets/PROVENANCE.md).

## Device mechanics and conventions

Edit [config.json](config.json), then rebuild. All default device parameters
are **assumptions** inherited from the earlier simulator:

- Thigh assembly: 0.25 kg, COM 0.22 m distal to the femur origin.
- Shank assembly: 0.20 kg, COM 0.18 m distal to the tibia origin.
- Thin-shell-equivalent cuff inertia, carried by separate welded bodies.
- Passive knee damping: 0.03 Nm·s/rad, applied continuously by a native
  `SpringGeneralizedForce` with zero stiffness.
- Nominal command: one selected bank, with 25 PSI and 20 PSI timed bursts.
- Pressure response: assumed 0.08 s filling and 0.12 s exhaust time constants.
- Pressure-to-moment mapping: assumed 0.4 Nm/PSI, with a 15 Nm surrogate cap.

These values and the 30 PSI simulation pressure clamp are not hardware ratings.
Blue cuffs and red actuator envelopes are schematic geometry. The model has no
fabric deformation, cuff slip, skin/tissue pressure, pressure-volume model,
compressor energy estimate or patient-specific impairment.

Both Gait2392 knees have **negative native flexion**. The helper API and CSV
telemetry use positive flexion:

```text
flexion angle    = -OpenSim knee coordinate
flexion velocity = -OpenSim knee speed
OpenSim moment  = -flexion-positive moment
```

The actuator `exosuit_knee_moment` has `optimal_force=1`: a native control of
+1 produces +1 Nm generalized force, toward extension. The actuator's min/max
controls are **optimization bounds, not a forward-dynamics clamp**. Future
external controllers must enforce their limits. [control.py](control.py)
provides a finite, capped software input boundary, with saturation reporting:

```python
import opensim as osim
from opensim_exosuit.control import set_knee_moment
from opensim_exosuit.settings import load_settings

model = osim.Model("opensim_exosuit/output/knee_exosuit.osim")
state = model.initSystem()
report = set_knee_moment(model, state, load_settings(), -4.0)  # extension, Nm
```

Set the held moment before initializing an OpenSim `Manager`. For subsequent
sample-and-hold changes, copy the returned integrated State and create a new
Manager; an existing Manager owns its integration state. The seated demo uses
a native `PrescribedController` instead, avoiding per-sample Manager resets.

The `.osim` holds a **joint-moment surrogate**, not native pneumatic state
variables. [profile.py](profile.py) uses the package-local [pneumatic.py](pneumatic.py) to precompute
pressure lag and capped torque. Only the diagnostic assisted model embeds this
time-dependent torque function. Controller knots follow the command grid
independently of the reporting interval. Nominal heel strikes are test inputs,
not inferred gait events; both bursts use the same selected physical-bank
assumption. The linear lookup is interpolated between controller knots.

The separate `../../sofa_simulation/sofa/data/torque_calibration.json` contains an angle-dependent
bench dataset over 0–90° flexion and 0–20 PSI. It is not silently substituted
for the current linear surrogate: its experimental mounting and joint-moment
transfer need verification, and it cannot justify the 25 PSI command through
extrapolation. No physical-device commands are sent by this package.

## What the diagnostic verifies

The seated fixture locks every coordinate except the selected knee. It disables
muscle forces and adds a clearly named return spring (25 Nm/rad) and fixture
damping (1.5 Nm·s/rad), centered at the initial 60° knee flexion. Those fixture
elements appear only in `seated_*.osim`, not in the full model.

OpenSim integrates the actual knee response to gravity, the fixture, device
inertia/drag and the example moment. No knee trajectory is prescribed. The
files include:

- `pressure_profile.csv`: commanded and modeled gauge PSI and moment.
- `seated_*.csv`: actual diagnostic knee motion, applied moment and work.
- `seated_*.mot`: actual coordinate trajectories for native playback.
- `seated_*_states.sto`: continuous OpenSim states in SI units.
- `model_manifest.json`, `configuration.json`, `validation.json`: assumptions,
  source/version information and the completed diagnostic results.
- `preview.png`: official meshes posed using OpenSim frame transforms, with
  actual simulated pressure and knee-response plots.

Joint work is mechanical output, not metabolic expenditure or pneumatic input
energy. The fixture checks mechanics and export; it does not establish muscle
benefit, gait stability, human adaptation or rehabilitation efficacy.

Run the checks:

```sh
.opensim-venv/bin/python -m unittest discover -s opensim_exosuit/tests -v
```

Tests cover original asset integrity, preservation of human anatomy, carried
mass/inertia, the causal acceleration effect of torque sign, dissipative drag,
pressure lag and single-bank timing, input clamping, reporting-independent
controller input, and native loading after relocation in a fresh process.

## Personalizing for rehabilitation

A patient-specific study needs measured anthropometry and segment scaling,
joint ranges, strength and gait impairment, device mounting and pressure/moment
calibration, and matched assisted/unassisted motion and external-force data.
Clinical movement goals and assessment of progress without the suit should
guide the objective. The generic model does not represent stroke, spasticity,
contracture, fatigue or neural adaptation automatically.

Preserve the original model attribution and CC BY 3.0 license when sharing
derived models. The source license and change description travel in the bundle.
