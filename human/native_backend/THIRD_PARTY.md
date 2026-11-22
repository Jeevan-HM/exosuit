# Third-party model and controller provenance

This folder contains adapted Apache-2.0 project material and a historical
human model whose header attributes its OpenSim ancestor under CC BY 3.0.
Preserve this notice, all LICENSE_* files, original XML attribution, and
provenance.json when copying the backend. Original authors' model/data rights
and attribution are preserved; the repository license does not erase them.

## Default historical model

The default historical/human22_historical.xml is derived from the official
NeuMove MyoAssist model models/22muscle_2D/myoLeg22_2D_BASELINE.xml at commit
88e9894b47e7dd48fba279dac8227b06f387d182. The original XML is retained as
historical/original_baseline.xml, including its full credits and modifications.

Original model lineage credited in that XML includes Ajay Seth, Carmichael
Ong, Scott Delp, Darryl Thelen, Frank Anderson, and other OpenSim contributors;
NeuMove modifications credit Chun Kwang Tan and Calder Robbins. The header
identifies the reduced OpenSim model as Creative Commons Attribution 3.0:
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
The XML also cautions that its reduced muscle set is not intended for
individual-muscle research conclusions.

Changes: preserve original dynamic parameters and initialization keyframes;
copy the referenced official meshes; resolve historical case mismatches in
mesh filenames; replace the original flat heightfield scene include with a
flat plane named terrain and matching foot contact-pair references; use
portable asset paths. Original Euler integration and disabled warmstarting
are preserved. No body or muscle parameters were personalized.

parameters/tutorial_prep.txt is the published 77-element human reflex vector
from ctrl_optim/results/optim_results/tutorial_prep in the current repository.
It contains 51 reflex gains and 26 pose/activation initialization parameters.
No gains were optimized for this task. The matched baseline completes the
30-second diagnostic described in VALIDATION.md.

## Optional newer model

human22.xml is composed from [MyoHub/myo_sim](https://github.com/MyoHub/myo_sim)
myolegs26, reduced using official assist_sim/reduce_legs.py, and exported with
assist_sim.load_msk('myolegs22'). The official export pipeline fixes nested
classless-default inheritance and preserves compiled collision flags. Bare
MjSpec.to_xml output is insufficient for this model.

Changes to this optional model: a flat ground plane, explicit gravity,
a 1 ms implicitfast timestep, and portable asset paths. Its 39 coordinates
include knee translations and muscle-routing constraints; they are not
39 independent anatomical degrees of freedom. Its historical controller
transfer failed; see diagnostic_results.json. The 81-element published
parameters/walking_1_25ms.txt and parameters/tutorial.txt vectors include
four original ankle-exoskeleton parameters. Only their first 77 human
parameters are used by this backend.

## Reflex controller adaptation

vendor/reflex_ctrl.py, vendor/reflex_interface.py, and vendor/param_layout.py
come from [NeuMove MyoAssist](https://github.com/neumovelab/myoassist).
Original controller authors include Chun Kwang Tan and Calder Robbins.
The source credits the Song and Geyer reflex-control architecture.
It is separate from the user's exosuit RL timing policy.

Changes to the interface: imports point to local copied modules and a minimal
native MuJoCo adapter; unused ankle-exoskeleton spline imports were removed;
mutable dictionaries were moved onto the instance; an explicit model path
option selects the matched historical or optional newer model. Only the
unassisted 2D human-controller branch is exposed. No controller gains changed.
native_env.py provides native stepping and the original object-velocity API
without importing Gym, MyoSuite, PyTorch, or SciPy. The added knee torque uses
qfrc_applied, separate from the frozen muscle controller.

Exact source commits and SHA256 hashes are in provenance.json. Sources were
accessed on 2026-10-24. No pickle files were opened or redistributed in this
portable folder. A separate historical PPO checkpoint was inspected only as
zip JSON metadata in the research working directory; it is not included here.
