# SOFA knee soft-exosuit package — PSI inputs

Open `knee_exosuit.py` for the exosuit controller and knee-motion simulation. Open `chamber_fem.py` for a separate deformable pneumatic-chamber experiment.

**Validation status:** 16 local Python/model/mesh/callback tests pass. SOFA and SofaPython3 are not installed on the authoring machine. Native scene loading, GUI rendering, plugin compatibility and solver convergence have **not** been verified. The callback checks use an explicitly labeled test double; they are not a SOFA execution result.

## Start in SOFA

Target: stable SOFA 25.12 / 26.06 with SofaPython3, using the classic component names included in those releases. The code has not been tested with the newer SOFA-NG development branch. Use an official SOFA distribution and its matching Python version. The official 26.06 distribution specifies Python 3.12. No hardware communication library is required by either scene.

Extract the complete folder, open a terminal in it, and run:

```sh
runSofa -l SofaPython3 knee_exosuit.py
```

Alternatively, enable SofaPython3 in SOFA's plugin manager and open the Python scene. The scene starts paused. Press SOFA's Play button. Double-click `ExosuitControls_PSI` in the scene graph to edit the inputs and see telemetry. `F` selects manual flexion, `E` manual extension, `T` timed switching, `M` manual pressure, `A` toggles pneumatic actuation, `H` toggles the assumed muscle controller, and `0` commands venting. SOFA Play/Pause freezes the entire simulation; `actuationEnabled=false` vents while the leg keeps moving.

If `runSofa` is not on your path, replace it with the full path to the executable in your SOFA installation. These files are ordinary Python SOFA scenes, not an installer.

## What is taken from your control code

The archive contains `nogrf_pressure_commands.py`, `nogrf_heuristic_controller.py` and `main_RL_online.py`. Their data and code were inspected; the hardware/experiment programs were not executed or modified.

| Behavior | Simulation implementation |
|---|---|
| Pressure command `Pd=[p0,p1]` | Same two-element order, exposed in PSI gauge |
| RL pressure level | 10 PSI |
| RL default switching times | 0.130, 0.264, 0.632, 1.270 seconds |
| Switching order | `[0,P]`, `[P,0]`, `[0,P]`, `[P,0]` |
| Heuristic preset | 5 PSI; 15%, 50%, 80%, 100% of a 1.1 s cycle |
| Command sampling | 300 Hz; pressure and knee integration at 600 Hz |
| RL actions | Four switching times, not four pressure magnitudes |
| Normalized action conversion | Same fractional ranges: `[.05,.20]`, `[.21,.41]`, `[.50,.70]`, `[.90,1.00]`, multiplied by cycle duration |

The isolated bench scene generates synthetic cycle resets. It does not infer heel strikes from IMUs or reproduce a walking human. A heel-strike event can reset the controller phase through the file adapter. The original RL pressure script resets at a hard-coded 1.27 s and can retain its previous command after `tD`; this simulation explicitly commands `[0,0]` after `tD` until the configured cycle resets. It validates threshold ordering.

**Channel mapping is an unconfirmed assumption.** `config.json` currently maps `p0` to flexion and `p1` to extension. The archive does not identify the physical direction of each element. If your plumbing is reversed, change:

```json
"channel_map": ["extension", "flexion"]
```

Select `profile=heuristic` in the SOFA controller to load its 5 PSI amplitude preset. If editing the initial JSON instead, set both `profile` and `pressure_amplitude_psi` explicitly.

## Pressure units

Every editable pressure input, channel command and main telemetry value is in **PSI gauge**. Internally, the FEM traction uses pascals to match metre–kilogram–second units:

`1 PSI = 6894.757293168 Pa`; `10 PSI = 68947.57293168 Pa`.

The main knee scene interpolates torque directly against PSI, so it never applies a second pressure conversion to the measured torque table. Its CSV additionally includes explicitly named `p0_pa` and `p1_pa` columns for SI interoperability. Do not enter PSI directly into a SOFA field that expects force per square metre.

The 20 PSI main-scene ceiling is the maximum pressure in the available characterization grid. It is a **simulation/data-domain limit**, not a verified device pressure rating.

## Main knee model

SOFA integrates an actual `MechanicalObject<Vec1d>` angular state with `EulerExplicitSolver` in symplectic mode, a `UniformMass<Vec1d>` entry representing rotational inertia, and `ConstantForceField<Vec1d>` for generalized torque. Python computes the applied torque and pressure response; it does not set a prescribed knee trajectory.

The thigh is fixed horizontally. Positive angle means flexion, with 0° straight and 90° vertically down. A combined shank/foot is approximated as a uniform rod:

`J = m L² / 3`

`J θ̈ = τflex − τextension + τwearer + m g L/2 cos(θ) − b θ̇ − k θ`

Default mass 4 kg, length 0.43 m, damping 0.7 N·m·s/rad, passive stiffness 0.4 N·m/rad and fill/vent time constants of 0.25 s are **assumptions**. The default wearer is relaxed. Optional tracking is an assumed bounded PD muscle drive following a slow 10–85° reference; it is not a physiological or EMG model. Ideal inelastic limits project position/velocity to 0–90° at the end of each step. The SOFA root gravity is zero because gravity is already included once in generalized torque.

The knee scene's chamber inflation, fabric, cuffs and hinge are **schematic display geometry**. Their deformation, stress, contacts and slip are not FEM solutions. The actual knee mechanics are solved by SOFA, with the actuator moment supplied by the torque table.

## Torque characterization

The project folder beside your archived code contains `Actuator_Characterization/Flexion_Angle_Char.xlsx` and `Extension_Angle_Char.xlsx`. `extract_calibration.py` reads those workbooks without modifying them and produces the included `data/torque_calibration.json`.

- 7 knee angles: 0°, 15°, 30°, 45°, 60°, 75°, 90°.
- 5 pressures: 0, 5, 10, 15, 20 PSI.
- 70 mean torque values in total, with sample SD, sample counts, source hashes and an explicit flag for an assigned empty zero-pressure reference.
- The adjacent MATLAB loader reads torque directly in N·m and currently sets `N_PARALLEL=1`, meaning the measured pair values are used without halving. Its introductory comment mentions per-actuator reporting, but the active setting reports the pair. This package follows the **active setting**. No additional actuator-count multiplier is applied.
- Bilinear interpolation is used between measured angles and pressures. Measured mode rejects configured motion/pressure ranges outside the table. It does not extrapolate past 90° or 20 PSI.
- Sample SD represents variation among recorded samples. It is not a confidence interval from independent trials. Static characterization does not validate pressure lag, dynamic torque, tissue coupling or the complete suit.

Check that these are the characterization files for the photographed configuration. `torque_scale` is an explicit multiplier if a confirmed actuator-count/interface correction is needed. Set `torque_model=assumed` to use the earlier conceptual gain instead. The original workbook files are not needed to run the included table.

To regenerate the table, using a Python environment with `openpyxl`:

```sh
python extract_calibration.py "/path/to/Actuator_Characterization"
```

## Separate deformable chamber test

```sh
runSofa -l SofaPython3 chamber_fem.py
```

Open `ChamberPressure_PSI`, set `targetPsi` to a small value such as 2 PSI and press Play. `+` and `-` adjust it by 0.5 PSI; `0` vents. The initial target is 0 PSI.

This scene contains a generated hollow tetrahedral solid, a fixed end, corotational `TetrahedronFEMForceField`, and a closed mapped cavity loaded by `SurfacePressureForceField`. It uses pressure traction in Pa, not a prescribed geometric inflation. A stiff bottom layer gives the illustrative specimen a bending bias. No external mesh files or SoftRobots plugin are required.

The assumed specimen is 200 × 48 × 36 mm, with a one-cell wall (12.5 mm at its ends and 6 mm on its sides), 876 vertices and 2,592 tetrahedra. The soft and stiff regions use assumed Young's moduli of 2 MPa and 30 MPa with Poisson ratio 0.30. The chamber model is a corotational elastic solid; it does not represent the suit's sewn fabric layers or large-strain bladder behavior.

**The FEM test is separate from the knee scene and its measured torque lookup.** It is a starting point for validating a chamber mesh and material model. It has not been coupled to the cuffs/knee or calibrated to predict this prototype's torque. A device-specific FEM model needs actual chamber surfaces, material tests, seam/reinforcement definitions, cuff attachments and contact geometry.

## Replay and your RL code

For offline pressure replay, change `mode` to `replay` in `config.json` and load the scene again. The example CSV has `time_s,p0_psi,p1_psi` columns and uses a zero-order hold. It vents after the last timestamp plus `replay_tail_s`. Nonmonotonic times, non-finite values and out-of-range pressures are rejected.

For sending your timing arrays to SOFA without hardware communication:

```sh
python sim_adapter.py --timings 0.13 0.264 0.632 1.27 --duration 1.27
python sim_adapter.py --pressure 10 0
python sim_adapter.py --pressure 0 0 --disable
```

The adapter atomically writes `live_command.json`; SOFA checks for new settings at 30 Hz. It creates no network sockets and does not contact the Raspberry Pi. Settings persist until changed. This is a local parameter bridge, not a real-time networking benchmark. An invalid file causes simulated venting and a visible status message.

For a **simulation-only copy** of the RL process, replace its hardware pressure path with:

```python
from sim_adapter import write_sim_command

# timing_export_array already contains the four denormalized times in seconds.
write_sim_command(timings_s=timing_export_array,
                  cycle_duration_s=float(data[9]))
```

Make this package importable in that process, or pass the adapter's explicit `path` to match the SOFA controller's `live_command_file`. Do not run the original hardware pressure exporter alongside this offline example. None of the original experiment-launch scripts are imported by the scenes.

The trained policy weights, a calibrated EMG response model and a complete RL training environment are not included in the archive. This package preserves the pressure/timing interface; it does not claim to reproduce human-in-the-loop training or measured physiological outcomes.

## Tests and logging

Local model and Python callback checks:

```sh
python -m unittest discover -p "test_*.py" -v
python reference_run.py --seconds 10 --output reference.csv
```

`reference_run.py` is explicitly a Python numerical reference, not SOFA.

Native tests, using an interpreter configured with SOFA/SofaPython3:

```sh
python run_headless.py --seconds 5
python run_headless.py --chamber --seconds 1 --psi 2
```

The knee scene creates a timestamped CSV under `logs/` when enabled. It records simulation time, angle, velocity, both PSI command/pressure channels, mapped bank pressures, and applied torques. A SOFA Reset restarts simulated time; treat a decrease in time as a new trial segment.

Local verification covers unit conversions, source switching boundaries, action denormalization, lag/venting, all 70 lookup nodes, interpolation, mapping reversal, replay validation, mesh connectivity, positive tetra volumes, closed cavity orientation/volume and Python controller callbacks. It does not establish native FEM convergence or render correctness.

## Official API references

- [SOFA releases and matching Python prerequisites](https://github.com/sofa-framework/sofa/releases/tag/v26.06.00)
- [Loading Python scenes with SofaPython3](https://sofapython3.readthedocs.io/en/latest/content/UsingThePlugin.html)
- [EulerExplicitSolver](https://sofa-framework.github.io/doc/components/odesolver/forward/eulerexplicitsolver/)
- [UniformMass, including Vec1d](https://sofa-framework.github.io/doc/components/mass/uniformmass/)
- [ConstantForceField](https://sofa-framework.github.io/doc/components/mechanicalload/constantforcefield/)
- [SurfacePressureForceField](https://sofa-framework.github.io/doc/components/mechanicalload/surfacepressureforcefield/)
- [BarycentricMapping](https://sofa-framework.github.io/doc/components/mapping/linear/barycentricmapping/)
