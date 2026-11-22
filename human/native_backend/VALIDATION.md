# Native human-model diagnostic status

**The matched historical human model and frozen reflex controller complete
30 seconds of unassisted forward walking in local diagnostics. The model is
generic and has not been validated against this user's human subjects.**

Verified locally with Python 3.12 and isolated MuJoCo 3.4.0. No global package
installation was performed. The system MuJoCo 3.14.0 also compiled the newer
model diagnostically, but lies outside the upstream declared stack:
assist_sim declares >=3.4,<3.12; full MyoAssist currently narrows this to
>=3.4,<3.5. Use MuJoCo 3.4.0 for reproducibility.

## Default matched baseline

The default is the official historical myoLeg22_2D_BASELINE.xml from MyoAssist
commit 88e9894b47e7dd48fba279dac8227b06f387d182, paired with the published
77-element tutorial_prep human reflex parameter vector. The inherited model
includes passive arms and torso, coupled knee translations and muscle-routing
coordinates, and 22 muscle actuators. Its total mass is 83.421466492 kg;
it has not been scaled to a particular subject. It has 53 coordinates,
34 bodies, and 28 equality constraints. The coordinates include auxiliary
muscle routing and passive arm joints; they are not 53 independent lower-limb
anatomical degrees of freedom.

Physics timestep is 0.001 s and the frozen human reflex controller updates
every 0.010 s. The pelvis translates and rotates freely in the sagittal plane.
Foot-floor contact and muscle activation are forward simulated. No joint
angles are prescribed after initialization and no external pelvis support is
applied. A flat plane replaces the original flat-initialized heightfield.
Original Euler integration and disabled warmstarting are preserved.

The following requested 30 s rollouts were performed. A fall stops integration:
pelvis height below 0.65 m, pelvis pitch beyond 60 deg, or non-finite state.

| Constant left-knee torque | Simulated time | Distance | Result |
| --- | ---: | ---: | --- |
| 0 Nm | 30.00 s | 33.97 m | No fall |
| +8 Nm flexion | 1.72 s | 2.36 m | Fall |
| -8 Nm extension | 30.00 s | 37.37 m | No fall |

The unassisted rollout had 107 foot-contact-state transitions; the extension
rollout had 111. Muscle activation remained finite in [0.01, 1]. The published
alternate tutorial vector also completed 30 s at 0 and -8 Nm, and fell at
5.02 s at +8 Nm. Details are in historical_diagnostic_results.json.
These are implementation and stability diagnostics, not evidence that a
specific assistance protocol benefits a human. Constant torque is deliberately
a perturbation test, not the user's pressure timing policy.

The backend returns fallen=True and never hides a fall or automatically
resets. Keep fall penalties and gait eligibility checks when optimizing an
assistance policy; optimization must not interpret a shortened fallen trial
as low muscle effort.

## Model/controller compatibility matters

The newer runtime-composed myolegs22 model (human22.xml, 39 coordinates,
38 bodies, 28 equality constraints, 78.090468479 kg) also loads successfully.
However, the inherited historical controller parameters fall on that model:
the original 1.25 m/s vector fell at 0.32 s unassisted, the tutorial vector at
1.08 s, and tutorial_prep at 1.17 s. All nine initial perturbation results
are preserved in diagnostic_results.json. Reoptimizing for the newer model
or obtaining its matched policy is necessary before switching to it.

The stable historical pairing is used by default to avoid presenting that
model mismatch as successful walking. It is still a simplified model with
lumped muscle groups. The original XML credits its reduced OpenSim ancestor
and explicitly cautions against interpreting its reduced muscle set as a
research-grade, individual-muscle human model.

## Interpretation limits

VL and BF channels are explicit aliases for lumped vasti and hamstrings
activation; they are not individually modeled vastus lateralis/biceps femoris
EMG. Squared model activation is an effort proxy, not measured EMG or
metabolic power. The frozen human controller responds to sensed forces and
joint states, but does not learn long-term human adaptation. Subject-specific
geometry, muscle strength, gait, and pressure-to-knee-torque calibration remain
necessary for subject-level predictions. Use a more detailed personalized 3D
musculoskeletal model when balance, frontal-plane motion, or individual
muscle/joint loading is the target outcome.

## API

```python
from native_backend import HumanBackend
human = HumanBackend()
state = human.reset(seed=0)
state = human.step(duration_s=0.05, external_knee_torque_nm=-8.0)
```

Angle, velocity, and applied torque use positive flexion; the wrapper
reverses the native model's negative-flexion convention. Torque is in Nm, not
PSI. Pressure-to-torque calibration belongs in the separate exosuit controller.
sample() reports time, left knee angle/velocity, left/right contact load,
muscle activation proxies, all 22 activations, pelvis speed/height, and fall
status. physics_dt_s and human_control_dt_s are public attributes.

To diagnose the newer model explicitly:

```python
from pathlib import Path
import native_backend
root = Path(native_backend.__file__).parent
human = HumanBackend(model_path=root / 'human22.xml')
```

Runtime dependencies for this portable folder are only numpy and
mujoco==3.4.0. No PPO checkpoint is required. A historical official PPO
checkpoint was located and inspected as a research reference, but it uses a
44-observation/24-action custom joint human-and-ankle-exoskeleton policy and is
not a drop-in knee-assistance controller. It is not part of this runtime.
