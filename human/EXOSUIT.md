# Coupled human and knee exosuit

Open the wearing-and-assisting simulation from the `simulation` folder:

```sh
uv run mjpython -m human.view --assist
```

The default viewer shows a solid human in athletic clothing, with skin, hair,
hands and shoes. This surface is a rendering layer following the existing
musculoskeletal model; it changes no mass, contacts or muscle mechanics.
Use `--anatomy` only when you want the underlying skeletal diagnostic view.

The viewer draws the photo-inspired blue cuffs, red fasteners, dark textile
sleeves, knee hinge, tubing and pneumatic pouches on the left leg. The geometry
follows the human's actual limb poses. Pouch thickness responds to modeled
pressure, not the target command. Its shape is an illustrative display rather
than a prediction of fabric deformation.

The exosuit also changes the forward dynamics: fixed thigh and shank inertias
add 0.45 kg, and an extra native knee damping coefficient adds passive drag.
These are not just drawing objects. There are no additional driven joint
coordinates or prescribed knee trajectories. The physical coupling assumes
perfect attachment: no cuff slip or tissue indentation is modeled.

| Viewer control | Action |
|---|---|
| Space / R | Pause or reset |
| A | Enable or vent the pressure commands |
| M / T | Independent manual banks / timed selected bank |
| E / F, then Up / Down | Select extension/flexion and adjust its manual PSI |
| V | Hide/show appearance; mass and drag remain |
| Mouse drag / wheel | Rotate / zoom |

`--manual 10 0` starts a 10 PSI extension experiment; `--manual 0 10` starts
flexion. These independent banks are a simulation option. The inspected
`new-RL` hardware path still sends one scalar pressure, so the timed mode routes
both its 25 and 20 PSI bursts to one selected bank (`--bank extension` by default).
`--no-exosuit` removes the device mass, drag, appearance and active assistance.

All editable assumptions live in `human/config.json`: `exosuit.mechanics`,
`exosuit.pneumatics`, `exosuit.geometry`, and the existing `assistance` gain,
direction and torque cap. The 30 PSI clamp is a simulation setting, not a rated
hardware pressure. No mass, dimensions or lag were measured from the photos.

For matched assistance comparisons, use the **same worn device** powered and
unpowered. The unpowered baseline retains the suit's mass and drag:

```sh
uv run python -m human.run --actions 1 --output human_output/exosuit_assisted
uv run python -m human.run --config human/examples/baseline_config.json --actions 1 --output human_output/exosuit_unpowered
uv run python -m human.run --config human/examples/bare_config.json --actions 1 --output human_output/bare
```

The CSV and full JSONL now include both pressure banks, signed assistance,
passive drag, total device moment, power and mechanical work.
`applied_active_joint_work_j` uses the actual applied moment times the measured
knee angle change in each control interval. The pneumatic telemetry's separate
`active_joint_work_j` is the pressure model's within-step approximation using
held sampled velocity. Neither is air consumption or human metabolic energy.

The integrated default passed 54 software/native checks. Both powered and
unpowered worn trials produced five valid measured strides. The rendered
previews and actual trajectories are in `human/validation/exosuit/`. A frozen
human controller can still fall under other settings; those failures remain
reported. Hardware forces, detailed soft materials and subject physiology
require calibration and validation.

## Pneumatic model

`pneumatic.py` simulates extension and flexion pressure states and their joint
moments. All pressure inputs and telemetry use **gauge PSI**. The pressure-to-
torque gain, pressure lag, pressure limits and torque limits are adjustable
assumptions until measured on the actual suit.

The legacy mode reproduces the `new-RL` controller's **single pressure command**:
25 PSI during the stance window and 20 PSI during the swing window. Its four
timing values mean `[stance onset, stance duration, swing onset, swing duration]`
in seconds from left heelstrike. Both bursts route to the explicitly selected
`legacy_bank`, extension by default. They do not imply two independently wired
hardware channels. Manual mode is a separate simulation experiment:
`set_manual_pressures(extension_psi=..., flexion_psi=...)` controls each bank.
`set_legacy_mode(bank="extension")` returns to the legacy schedule.

Each bank obeys a first-order pressure response,
`dP/dt = (Pcommand - P)/tau`, with separate filling and exhaust time constants.
The default assumptions are:

| Parameter | Default |
| --- | ---: |
| Pressure command sampling | 100 Hz |
| Filling time constant | 0.08 s |
| Exhaust time constant | 0.12 s |
| Maximum gauge pressure per bank | 30 PSI |
| Linear torque magnitude gain per bank | 0.4 Nm/PSI |
| Pressure deadband | 0 PSI |
| Maximum torque magnitude per bank | 15 Nm |
| Maximum total applied joint torque | 15 Nm |
| Extra damping inside this pressure model | 0 Nm·s/rad |

Disabling the device commands both banks to vent. Residual pressure and torque
decay with the exhaust lag; `reset()` explicitly initializes zero pressure.
Flexion torque is positive; extension torque is negative. Independently active
banks oppose one another. The total torque cap includes any damping configured
inside this model, and telemetry shows pressure and torque saturation.

Optional pressure/torque curves use interpolation only. A supplied curve must
start at zero pressure and torque, and the bank's pressure limit must not exceed
the curve's measured range. A curve ending at 20 PSI cannot predict torque at
25 PSI: a 25 PSI request to a bank limited to 20 PSI is visibly saturated to
20 PSI. The default linear gain is explicitly an uncalibrated assumption.

The caller supplies the human's actual simulated knee angular velocity to
`advance(time_s, dt_s, knee_angle_rad=..., knee_velocity_rad_s=...)`. Joint power
is applied torque times that velocity. Signed, positive and absorbed mechanical
work accumulate from sampled power; static pressurization produces no joint
work. These values are **not compressor energy, air consumption, efficiency or
human metabolic expenditure**. Work uses trapezoidal integration within the
device's command updates while holding the supplied velocity over each human
control interval.

`telemetry()` reports both banks' requested, limited and actual pressures,
signed bank torques, active/passive/net joint torque, power and accumulated
mechanical work. Compatibility properties `command_psi` and `actual_psi` refer
only to the selected legacy bank; use the full telemetry in manual mode.

Carried mass/inertia and garment damping belong in the separate native
mechanics layer. The integrated model's provisional 0.25 kg thigh mass,
0.20 kg shank mass and 0.03 Nm·s/rad passive knee damping are assumptions,
not quantities inferred from the photographs. Keep pneumatic damping at zero
when native garment damping is enabled to avoid counting it twice.

Photo-inspired cuffs, hardware, tubing and pressure-driven pouch swelling are
rendered schematics following the actual limb poses. This reduced model does
not perform soft-tissue contact, fabric mechanics, chamber FEM or validated
soft-actuator deformation. It does not import or command hardware.

Run the independent checks from the simulation project with
`uv run python -m unittest -v human.tests.test_pneumatic`. The existing `KneeAssistance` implementation is unchanged.
