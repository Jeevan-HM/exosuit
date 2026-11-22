# Bare human walking

For **live OpenSim physics and knee angles**, double-click
`../Run_OpenSim_Physics.command`. Keep its window open and use the viewer at
http://127.0.0.1:8765/. Both the human pose and plot come from integrated joint
states. This is supported torque-controlled motion: virtual pelvis support,
muscle forces off, no foot–floor contact. All coordinates remain free.
See [the simulation instructions](../README.md) for controls and scope.

Open `human_walking.osim` with its adjacent `Geometry/` folder, then load `normal_walking.mot`. This is the generic Gait2392 human with no exosuit, cuffs, added device inertia, damping or assistance actuator.

For recorded gait playback with synchronized degree-based knee plots, open `live_walking.html`, or double-click `../View_Reference_Walking.command`. The one-second reference cycle loops indefinitely. Pause, restart, speed, knee selection and the timeline affect the anatomy and plots together.

For the green Run button in OpenSim Creator, open `human_walking_playback.osim`. This explicitly kinematic version prescribes the gait, so it does not fall through the displayed floor. It plays for 120 seconds, settles over its final cycle and then holds the final pose. Its motion is imposed, not predicted by a human motor controller. The separate unconstrained `human_walking.osim` has no ground-contact forces or walking controller; using free forward dynamics on that research model will fall under gravity.

In OpenSim Creator: Preview Experimental Data → load model → human_walking.osim → load model trajectory sto/mot file → normal_walking.mot. Move the 0–1 second time slider. In standard OpenSim: File → Open Model, File → Load Motion, then Play/Loop.

`knee_angle_trajectory.png` is the phase-annotated right-knee figure. An editable vector version is `knee_angle_trajectory.svg`. The CSV stores both knees; flexion is positive. Phase divisions are based on knee extrema, not measured heel strike/toe off. No error band is estimated.

`human_walking.gif` is the looping human-only preview when the animation export has been run. It uses native OpenSim bone geometry and anatomical muscle paths; their color does not estimate muscle activity.

Source anatomy and credits: [official Gait2392 model](https://github.com/opensim-org/opensim-models/blob/d9b05d470b1a481c222372c85b75772faf8f7792/Models/Gait2392_Simbody/gait2392_thelen2003muscle.osim). The original model credits are retained; CC BY 3.0 legal text is in MODEL_LICENSE.txt. Changes: model name/description and relative geometry paths only.

Source motion: [official normal.mot](https://github.com/opensim-org/opensim-models/blob/d9b05d470b1a481c222372c85b75772faf8f7792/Tutorials/Intro_to_Musculoskeletal_Modeling/normal.mot). The original motion is unchanged and contains 17 coordinates over 1 second. Six omitted coordinates remain at zero defaults for in-place playback. This is reference motion, without a human motor controller, force/contact data, muscle activity estimates or a prediction of patient behavior.

Rebuild from the simulation folder: `.opensim-venv/bin/python -m opensim_exosuit.walking`. Then export the animation with `.opensim-venv/bin/python -m opensim_exosuit.walking_animation`.
Build the live viewer with `.opensim-venv/bin/python -m opensim_exosuit.live_viewer`.
Build the native Run-button playback with `.opensim-venv/bin/python -m opensim_exosuit.prescribed_walk`.
