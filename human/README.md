# Human-centered knee assistance simulation

The default view now shows a solid, clothed human wearing the knee exosuit.
The underlying muscle-driven walking physics is unchanged.
See [the exosuit controls and assumptions](EXOSUIT.md) for the current wearable model. Foot contact, joint
motion and muscle feedback evolve when assistance changes. The exosuit is a
simple, adjustable pressure-to-knee-moment layer; pressures remain in **PSI**.

The recommended method is MuJoCo with a MyoSim/MyoAssist-derived human and a
separate human motor controller. Use OpenSim/Moco and held-out measurements for
personalization and independent biomechanical checks. See [the research report](RESEARCH.md)
for the method comparison, primary sources, validation plan and limitations.

## Open the simulation on this Mac

Double-click `Launch_Human_Simulation.command` in the parent `simulation` folder.
The first launch creates a project-local Python environment and installs the two
runtime dependencies. It then opens the native human–exosuit viewer. Press A to enable the timed assistance.
Additional manual bank controls appear in the viewer and in `EXOSUIT.md`.

- **Space:** pause/resume.
- **A:** enable/disable the illustrative 25/20 PSI assistance preset.
- **R:** reset the human; falls remain visible until reset.
- Drag to rotate; scroll to zoom.

The viewer's preset uses four normalized zeros decoded with an explicit 1.15 s
reference stride. It is a visual experiment, not a trained RL policy. Use the
stride environment below to measure and update the policy every five strides.

## Run with uv

From the parent `simulation` project directory:

```sh
source .venv/bin/activate
uv run python -m human.run --actions 1 --output human_output/assisted
uv run python -m human.run --config human/examples/baseline_config.json --actions 1 --output human_output/baseline
uv run mjpython -m human.view --assist
```

`human.run` is a Python module, so it needs `python -m`; `uv run human.run`
looks for an executable literally named `human.run`. The project environment
is `.venv`. If the terminal still points at `.human-venv`, activating `.venv`
clears the environment mismatch warning. Run these commands from this project
root so the `human` package is available.

## Run measured rollouts without uv

From the parent `simulation` directory:

```sh
python3 -m venv .human-venv
.human-venv/bin/python -m pip install -r human/requirements-lock.txt
.human-venv/bin/python -m human.run --actions 1 --output human_output/assisted
.human-venv/bin/python -m human.run --config human/examples/baseline_config.json --actions 1 --output human_output/baseline
.human-venv/bin/mjpython -m human.view
```

On macOS the viewer requires **mjpython**. Other platforms can use the environment's
ordinary Python for `python -m human.view`. Headless rollouts do not require a
display. No SOFA, PyTorch, MyoSuite, Gymnasium, hardware driver or network socket
is required at runtime. MuJoCo is pinned to **3.4.0**; use the isolated environment.
`requirements-lock.txt` records the complete tested Python 3.12 runtime;
`requirements.txt` gives the minimal direct dependencies for other environments.

`run` saves scalar trajectory CSV, complete per-sample JSONL including all 22
muscle activations/excitations, and JSON summaries. Failed or incomplete gait
observations are flagged. CLI exit 2 means a fall, invalid action, missing gait
events or failed baseline. A normal episode time limit is reported as truncation.

## What is modeled

The default is a pinned historical bilateral planar human and a matching
published 77-parameter reflex vector. It contains 22 lumped muscle actuators,
activation and force–length–velocity dynamics, hip/knee/ankle motion, a moving
pelvis, passive torso/arms and bilateral foot–ground contact. The model is a
generic **83.42 kg** human, with **1 ms physics** and **10 ms human control**.
It is initialized once; joint angles are then integrated from muscle/contact
forces. No reference knee trajectory or external pelvis support drives walking.

Positive public knee angle and torque mean **flexion**. Extension assistance is
negative torque. The model's native knee sign is reversed inside the backend.
Default torque is `−min(15 Nm, 0.4 Nm/PSI × pressure_PSI)` in extension mode.
The gain and limit are adjustable assumptions, not measured ratings or a fitted
law for this suit. The previous torque table ends at 20 PSI, so it is not silently
extrapolated to the new 25 PSI command. Both timed bursts act in the selected
direction; “stance” and “swing” do not imply separate flexion/extension channels.

`config.json` also sets wearable mass, drag, geometry, bank inflation/exhaust lag,
direction, gain, torque limit, optional legacy pressure lag and
pressure levels. `device_enabled=false` gives an unpowered worn comparison. Set
`exosuit.enabled=false` and `device_enabled=false` for the bare human. `reset()`
always collects unassisted baseline strides before enabling configured assistance.
`target_speed_m_s` sets a **reward target**; it does not retune the frozen human
controller or prescribe treadmill speed. This prototype uses flat ground.

## new-RL contract

The audited sources are in the adjacent `new-RL` folder. They are never imported
or executed here. Several versions coexist; a checkpoint name does not establish
its units profile.

| Setting | Implemented behavior |
|---|---|
| Four actions | Stance onset, stance duration, swing onset, swing duration |
| Pressure channel | One scalar; 25 PSI in stance burst, 20 PSI in swing burst, 0 otherwise |
| Command sampling | 100 Hz; original source-ordered endpoint semantics |
| Default `v1_percent` | Fractions `[0–.2, 0–.25, .5–.74, 0–.28]` × latest measured stride duration |
| Optional `v9_seconds` | Seconds `[0–.3, .3–.8, .7–1.4, .2–.4]` |
| Contact | Actual simulated GRF strictly greater than 100 N; initial contact is not an invented heelstrike |
| Gait events | Left single-support onset/duration; first strict swing knee peak; time from peak to next left heelstrike |
| Actor observation | Five values; percent profile preserves the source's single-support-duration/2 convention |
| Stride features | Four timings, peak knee angle in radians, three activation proxies, stride seconds |
| Averaging | Five valid strides, explicitly correcting the source's four-summed/divided-by-five bug |

The original `gait_timing_v6.py` emits fractions; feeding it unchanged into the
seconds-based v9 actor mixes units. The simulator calculates the selected units
explicitly. Overlapping windows or windows beyond the estimated next heelstrike
are rejected rather than sorted or silently clipped; this intentionally tightens
the permissive legacy pressure script. A changed actual stride can still reset
the schedule earlier when its real heelstrike occurs.

## Use with the timing actor

```python
from human.environment import HumanExoEnv

env = HumanExoEnv()  # v1_percent; baseline first, assistance after baseline
observation5, baseline_info = env.reset(seed=0)
action4 = [0.0, 0.0, 0.0, 0.0]  # replace with your actor output in [-1, 1]
next_observation5, reward, terminated, truncated, info = env.step(action4)
positive_cost_for_legacy_DHDP = info["cost"]
env.close()
```

The human's reflex controller generates 22 muscle excitations. Your exosuit
actor generates four timing parameters. They are separate controllers.
Actions influence external knee moment, which changes the forward human
trajectory; observations come from that trajectory. This is a Gym-style API,
not a `gymnasium.Env` subclass or an automatic loader for historical checkpoints.

Each step retains the action for one discarded settling stride and five measured
strides. Observations and reward use the same measured interval. Missing events
and falls never create replacement gait features: `features9=None` and
`observation_valid=false` identify incomplete transitions. The returned array is
the previous valid observation on such a transition; trainers must check the
termination and validity flags. A partially completed block at the episode time
limit is discarded and truncated.

Default positive cost is:

`mean-over-22-muscles(activation²) integrated over measured time / forward distance`
`+ 2 × (mean forward speed − target speed)²`.

Distance has a 0.05 m denominator floor; falling and missing gait have separate
penalties. This is a transparent **effort proxy**, not metabolic energy. The
legacy positive cost is also reported for compatibility, with uncalibrated
activation-group inputs. To make that the optimizing objective, explicitly set
`reward_mode="legacy_proxy"` and `allow_uncalibrated_legacy_proxy=true`.
Legacy DHDP minimizes cost; reward-maximizing algorithms use the negative reward.

VL is represented by lumped vasti, RF by rectus femoris and BF by lumped
hamstrings. These are **activation proxies, not surface EMG**. No arbitrary
“assistance lowers EMG” formula or long-term human learning is included. Reflex
feedback gives immediate response; subject adaptation requires a separately
identified model and evidence.

## Verification and scientific limits

The package passes 54 interface, pneumatic, wearable and native integration checks:

```sh
.human-venv/bin/python -m unittest discover -s human/tests -v
.human-venv/bin/python -m human.run --diagnostic --seconds 30 --output human_output/diagnostic
.human-venv/bin/python -m human.native_backend.run_diagnostics
```

The current coupled-suit results and rendered previews are in `validation/exosuit/`.
Earlier bare-human diagnostics are retained in the parent `validation/` directory. The generic
baseline completed 30 s; a constant −8 Nm extension perturbation also completed
30 s; +8 Nm flexion caused a fall at 1.72 s. Actual timed 25/20 PSI assistance and
the unassisted comparison each returned five valid measured strides. These
are software and stability checks, not evidence of physiological benefit.
See [native validation details](native_backend/VALIDATION.md).

The current 22-muscle model is suitable for initial sagittal-plane controller
experiments. Use a more detailed personalized 3D model for lateral balance,
turns, substantial asymmetry or individual-muscle/joint-load conclusions.
Calibrate anthropometry, strength, gait and the pressure-to-moment relation;
validate assisted changes on held-out trials before interpreting policy rankings
as predictions about a person. The report distinguishes immediate response,
tracking/inverse estimates and slow human adaptation.

The optional newer model is retained for diagnostics; its inherited controller
falls quickly. It is not the default. Exact asset commits, original model
credits, CC BY 3.0 attribution and Apache licenses are preserved in
[third-party notices](native_backend/THIRD_PARTY.md) and `native_backend/provenance.json`.
