# Choosing a human-centered simulator for this knee exosuit

Research and source-code review: 24 October 2026.

The current implementation now also includes a photo-inspired wearable, actual
carried inertia and passive drag, separate pressure states and inflation/exhaust
lag. It remains a reduced device model; see [EXOSUIT.md](EXOSUIT.md).

## Recommendation

Use **muscle-driven forward walking in MuJoCo**, starting with the **bilateral planar MyoSim/MyoAssist human**, as the main environment for testing the existing timing-based RL controller. Keep the device as a compact PSI-to-knee-moment layer. Use **OpenSim/Moco for subject scaling, biomechanical calibration and independent checks of selected assistance conditions**. Do not extend the previous SOFA soft-chamber model as the main human simulator.

This is a task-specific engineering recommendation. Neither the engine name nor a realistic-looking animation establishes that a model predicts a person's response. The decisive requirements are a responsive human controller, muscle mechanics, foot contact, correctly computed gait events, and validation under assistance.

The delivered prototype uses a pinned historical 22-muscle planar model and a matching published reflex parameter vector adapted from MyoSim/MyoAssist assets. It includes passive arms and trunk but no active upper-body control. It does not include the complete MyoAssist training framework or participant-specific adaptation. This matched generic model/controller completed 30 seconds of unassisted forward walking in local diagnostics. That establishes a functioning baseline in this configuration, not personalized physiology or reliable ranking of assistance policies.

The first useful human model should have both legs, hip/knee/ankle motion, a moving pelvis and passive trunk, foot–ground contact, muscle activation dynamics and force–length–velocity behavior. A unilateral knee hinge misses contralateral support, balance, biarticular muscles and redistribution of effort across joints. Begin in the sagittal plane for controlled straight walking. Move to a 3D model for lateral balance, substantial asymmetry, turns, uneven terrain or a population whose compensations require it.

## Why the recommendation fits new-RL

The inspected folder is `/Users/g1/Developer/exosuite/new-RL`. It contains several historical controller versions rather than one unambiguous entry point. The online scripts named `main_v9_noemgstate.py` and `main_v1_noemgstate_percent.py` both use five policy inputs and four action outputs, but they use different timing units and costs. The older six-state offline variant is not interchangeable with them.

The four action outputs describe **stance onset, stance duration, swing onset and swing duration**. They are not four ordered switching boundaries. `pressure_commands_v3.py` produces one scalar pressure channel, with 25 PSI in the stance assistance window and 20 PSI in the swing window, and samples commands at 100 Hz. This differs materially from the earlier two-channel 10 PSI archive. The muscle terms in these online versions are VL, RF and BF. Those observations should therefore come from the simulated human and its contact events, not from the commanded action or a constant data stream.

The local `simulate data streams` programs are useful communications fixtures. Their constant gait values and arbitrary EMG values do not encode a causal human response. Training against them cannot demonstrate that assistance changes gait or effort. Likewise, replaying the same recorded next-state sequence for every assistance action does not produce an action-conditioned environment.

Two compatibility issues are corrected explicitly: `gait_timing_v6.py` emits fractions while `main_v9_noemgstate.py` expects seconds; and the original averaging loop adds four strides but divides by five. The simulator selects a named units profile and averages five valid strides. The percent version's unusual single-support-duration divided by two is preserved. Invalid overlapping or overlong assistance windows are flagged rather than silently reordered, clipped, or presented as valid actions.

The project-linked [Zhong et al. ICML 2025 paper](https://proceedings.mlr.press/v267/zhong25f.html) describes offline imitation followed by online personalization on the physical human–device system. A simulator can support debugging, robustness experiments and pretraining for that workflow. It does not replace the human evidence or inherit the paper's experimental conclusions or convergence guarantees.

## Comparison of the main options

| Method | Strength for this task | Main limitation | Recommended role |
|---|---|---|---|
| MuJoCo + MyoSim/MyoAssist human | Forward muscle dynamics, ground contact and separately controlled human/device; convenient Python interaction with timing RL | Human motor controller still needs tuning and validation; converted muscle paths and tendon assumptions matter | Main interactive simulator and policy evaluation environment |
| OpenSim + Moco | Established musculoskeletal workflow for subject-specific models, muscle estimates, tracking and predictive optimal control | Optimal-control solves and repeated adaptation studies need more setup; prescribed-motion inverse solutions do not predict a new gait | Calibration and independent biomechanical cross-checks; primary tool if offline physiological inference becomes the main aim |
| SCONE with an appropriate dynamics backend | Reflex-based predictive gait and controller-parameter optimization | Different controller/optimization workflow from the current actor–critic scripts; check current backend licensing and platform support | Strong alternative if optimizing human reflex parameters is more important than keeping the current Python RL structure |
| SOFA + SoftRobots/FEM | Deformable materials, cavities, contacts and suit mechanics | Those are no longer the central uncertainties; a human locomotor/muscle controller would still have to be built | Retain for later cuff/tissue or actuator studies if those questions become important |
| Angle replay or a single controlled knee | Fast, deterministic interface tests | Removes the human response that RL is supposed to influence | Regression tests only |

MyoAssist explicitly separates human and device control and includes both RL and reflex-controller optimization. Its current model catalog includes a 22-muscle planar human and a larger 80-muscle lower-limb model. A custom knee-moment interface is still needed for this particular device; a model catalog entry for another assistive device is not validation for this suit. See the official [MyoAssist overview](https://myoassist.neumove.org/) and [musculoskeletal model definitions](https://myoassist.neumove.org/modeling/msk-models.html).

## Tracking, prediction and adaptation are different questions

1. **Inverse/strong tracking:** Estimate forces and muscle activity while closely reproducing measured motion. This is useful for checking whether the human model can explain baseline measurements. An apparent reduction in required muscle effort under fixed motion is not evidence that a person will actually choose that motion when assisted.
2. **Forward response with a fixed reflex or neural controller:** Apply the external knee moment and let contact, joint motion and muscle feedback evolve. This exposes immediate gait perturbations and compensations. A fixed controller can be out of distribution when assistance changes, so an assisted fall is not proof that the human could never adapt.
3. **Human co-adaptation:** Allow the human controller to change across many strides or an inner optimization loop. This asks a different question: what behavior might emerge after adaptation? Re-optimizing instantly for every exosuit action exaggerates how quickly a human can learn. An adaptation rate or fatigue state must be identified from time-resolved experiments rather than chosen to make a policy look effective.

The [MocoInverse API](https://opensim-org.github.io/opensim-moco-site/docs/1.3.0/html_user/classOpenSim_1_1MocoInverse.html) explicitly prescribes kinematics. [MocoTrack](https://opensim-org.github.io/opensim-moco-site/docs/1.3.0/html_user/classOpenSim_1_1MocoTrack.html) instead trades tracking and effort objectives in an optimal-control problem. The original [OpenSim Moco paper](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008493) demonstrates both movement prediction and assistive-device optimization. These are useful complementary tools, not interchangeable evidence.

For long-term behavior, ["Exploration-based learning of a stabilizing controller predicts locomotor adaptation"](https://pmc.ncbi.nlm.nih.gov/articles/PMC11532365/) distinguishes a fast stabilizing response from slower performance-driven learning. That supports testing the two time scales separately. It does not supply a fitted adaptation model for this participant or suit.

## What the human controller and exosuit controller should each do

The **human controller** supplies muscle excitations using body state, contact state, muscle feedback and any explicitly modeled neural delays. Muscle dynamics convert excitation into activation and force. The baseline controller should first walk without assistance at the intended speed and condition. Keep its parameters fixed for an immediate-response evaluation. For an adapted evaluation, optimize or fine-tune a separate copy under an explicit human objective and report that distinction.

The **existing exosuit actor** continues to output four timing parameters. Decode them with the exact selected source version, apply the single-channel pressure schedule, then apply a bounded knee moment to the human. Both the five policy observations and the three muscle proxies must be measured from the resulting trajectory. Do not set observed gait onset/duration equal to commanded onset/duration.

The full simulated state includes muscle activations, controller delay buffers and body velocity that the five-element actor input does not reveal. Therefore the actor sees a partially observed process. Preserve the five-element interface for a controlled comparison with the old policy, but evaluate whether histories or a recurrent policy are needed once adaptation or sensor delay is introduced.

## EMG and reward: the most important validity issue

**Simulated activation is not measured surface EMG.** The legacy code uses processed, MVC-normalized and subsequently rescaled EMG integrals. A generic muscle activation value in `[0,1]` cannot simply replace those numbers and retain the old cost's physiological meaning. The planar model's grouped vasti and hamstring actuators are also only proxies for individual VL and BF recordings.

For initial simulator testing, record these separately:

- Individual modeled muscle excitation and activation, and activation-group proxies corresponding approximately to VL/RF/BF.
- All-muscle effort proxies, such as time- or distance-normalized squared activation, with the exact definition and scaling reported.
- Gait speed, valid foot-contact events, stride duration, swing knee flexion, falls and any device work.
- The legacy cost only as an explicitly labeled compatibility calculation. If converting to a reward-maximizing algorithm, use `reward = -cost`; the inspected DHDP actor minimizes its critic output directly.

A reward based only on three knee channels can favor moving work to other muscles or slowing down. Keep speed/task constraints and a broader muscle-effort diagnostic. Do not call an activation proxy "metabolic cost". A metabolic prediction requires a specified physiological model, appropriate states and independent validation. Matching one set of EMG channels does not validate metabolic savings.

Matching baseline gait does not uniquely identify the human's objective. Different objective functions can produce plausible unassisted walking while recommending different assistive torques, so compare policy rankings across reasonable objective weights. [Nikoo and Uchida (2022)](https://www.mdpi.com/2073-8994/14/12/2534) studies this cost-function sensitivity in predictive exoskeleton simulation.

[Hicks et al., "Is My Model Good Enough?"](https://pmc.ncbi.nlm.nih.gov/articles/PMC4321112/) recommends validation appropriate to the intended use and cautions against direct numerical equivalence between normalized EMG and predicted activation. Compare onset/offset, relative changes and muscle coordination after accounting for delays, and separate calibration from validation data. The [MuJoCo muscle documentation](https://mujoco.readthedocs.io/en/stable/modeling.html#muscle-actuators) also documents simplifying assumptions in its native muscle actuator; model conversion does not make it identical to every OpenSim muscle formulation.

In particular, MuJoCo's native muscle actuator assumes inelastic biological tendons and zero pennation. This limits direct interpretation of muscle-fiber energetics and tendon behavior. If these become central outcomes, assess a compliant-tendon OpenSim formulation and validate that formulation for the intended use.

## Minimal device model

Retain PSI at the interface and use an explicit bounded pressure-to-moment gain, optional lag and an explicit direction convention. The legacy single-channel path does not encode a separately commanded flexion and extension bank. Its direction and its actual pressure-to-knee-moment relation must be confirmed for the hardware configuration.

The earlier torque-characterization table stops at 20 PSI and concerns a particular measured assembly. Do not silently extrapolate it to the new code's 25 PSI stance command or assume the same actuator count/configuration. The human-centered prototype therefore labels its simple gain as an assumption. Sensitivity to that gain is part of the evaluation, not a substitute for calibration.

Ignoring detailed soft-material mechanics is reasonable for the requested focus. Ignoring the sign, magnitude and time of assistance is not: these determine the perturbation applied to the human.

## Validation sequence before using the simulator to rank policies

1. **Verify the software contract.** Test timing units, onset/duration interpretation, pressure levels, sampling, sign conventions, action boundaries, cost sign, resets, missing events and termination. Never import the source hardware launchers in the simulator.
2. **Establish unassisted human behavior.** At a fixed speed and level ground, compare knee/hip/ankle trajectories, bilateral GRFs and event timing. Check muscle activation onset/offset and plausible coordination. Report model/controller failures, not only successful trials.
3. **Fit identifiable properties.** Use anthropometry and baseline data for scaling, muscle strength and controller tuning. Use measured joint assistance or a suitable calibration test for the device gain. IMU knee angle plus three EMG channels alone do not uniquely identify every muscle and neural-control parameter.
4. **Validate assistance on held-out conditions.** Hold out entire trials or participants and assistance timings/levels. Compare assisted–unassisted changes, not just visual agreement or the data used to fit the controller. Use multiple seeds/initial states and report fall rates and uncertainty.
5. **Separate immediate and adapted evaluations.** For adaptation, collect time-resolved responses across strides, parameterize the slow learning process and test it on a separate change in assistance. Do not treat a generic optimized controller as a personalized digital twin.
6. **Then train or compare the exosuit policy.** Use the same speed/task constraints across policies, randomize only defensible uncertainties and test sensitivity. A learned policy that exploits an invalid event extractor or proxy scaling has not solved human assistance.

The recommended starting experiment is controlled, straight, level walking. Inclines, pathologies and clinical outcomes require additional validation. A planar model cannot establish lateral balance performance.

## Evidence quality and reproducibility

The package should pin its model, controller and dependency versions, retain source licenses, include deterministic seeds and save full trajectories and failed-trial diagnostics. The installed general-purpose MuJoCo version may differ from the range supported by MyoAssist, so use the tested isolated environment rather than changing global packages.

For SCONE, distinguish its [Apache-2.0 core](https://github.com/tgeijten/scone-core), [GPL3+ Studio](https://github.com/tgeijten/scone-studio), and separately licensed [Hyfydy backend](https://scone.software/doku.php?id=hyfydy). Licensing depends on the chosen components.

The 2024 Nature article ["Experiment-free exoskeleton assistance via learning in simulation"](https://www.nature.com/articles/s41586-024-07382-4) is relevant precedent, but its page currently carries a July 2026 editor's note concerning supporting code/data availability. It is not used here as evidence that this simulator can eliminate experiments, nor are its reported benefit percentages assigned to this knee suit.

## Decision

For the current Python timing-RL project, use a **MuJoCo muscle-driven bilateral human with reflex/neural motor control**, retain a simple, clearly parameterized device moment, and use **OpenSim/Moco plus held-out experimental measurements** for calibration and validation. The first deliverable is a working research prototype with explicit failures and proxy labels. A validated personalized human model is a subsequent empirical result, not something obtained by changing simulation engines.
