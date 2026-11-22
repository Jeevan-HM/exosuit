# Knee soft-exosuit simulation

An interactive, reduced-order simulation inspired by the five supplied prototype photographs. The photos inform the fabric sleeve, paired cuffs, pneumatic plumbing, and lateral hinge drawing. They do **not** determine internal chamber routing, dimensions, actuator count, material properties, or torque performance. The flexion and extension banks in the drawing are schematic functional groups.

## Model

The thigh is fixed horizontally, as in a seated leg-extension test. The shank and foot are approximated together as one uniform rod. Flexion is positive: 0° is straight and 90° is vertically down. A single ideal hinge replaces the actual moving knee axis.

`J q̈ = τhuman + τflex − τext + m g L/2 cos(q) − b q̇ − k q`

- `J = m L²/3`, `k = 0.4 N·m/rad`, and gravity is `9.81 m/s²`.
- Each chamber pressure obeys `ṗ = (pcmd − p)/T`, integrated with an exact exponential pressure update.
- The lumped pressure-to-torque coefficients are assumed: `Cf = G(1 − 0.75 q/120°)` and `Ce = G(0.35 + 0.65 q/120°)`. Robot torque is `Cf pf − Ce pe`; coefficients represent whole banks, not individual bags. These curves are placeholders, not fitted material laws.
- Cycle mode targets a smooth 10–85° seated motion. Hold mode targets a fixed angle. An idealized PD wearer controller uses gravity and acceleration feedforward. Assistance requests a fraction of the total torque demand, subject to supply pressure. The wearer covers the commanded shortfall, with a ±25 N·m limit; pressure lag remains uncompensated. This controller is a simulation assumption, not a measured human response.
- Manual pressure mode sets human torque to zero, allowing the pressure, gravity and passive impedance to determine movement. Both banks may inflate simultaneously. Switching mode restarts the simulated trial, while changes within a mode preserve the dynamic state.
- Semi-implicit Euler integration uses a fixed 1/240 s step, with ideal non-bouncing stops at 0° and 120°. Stop reactions are separate from the displayed applied robot and human torques. The pause button freezes simulation time and chamber dynamics. A background tab pauses rather than catching up.

All initial numbers are illustrative: 4 kg effective distal mass, 0.43 m length, 120 kPa gauge supply, 0.12 N·m/kPa bank gain, 0.25 s pressure time constant and 0.7 N·m·s/rad damping. The 0–250 kPa slider is an exploration range, **not** a rated operating pressure.

This model does not simulate fabric stresses, chamber contact, pneumatic flow thermodynamics, tissue compliance, cuff slip, gait, fatigue, or a hardware control interface. It cannot establish safe operating limits or clinical performance.

## Use and maintain

`knee-exosuit.template.html` is the editable interface source. `model.js` is its separately testable dynamics source. `build.py` embeds the model in `knee-exosuit.html` and copies the completed fragment to the conversation visualization directory. Run `node test-model.js` after changing the dynamics, followed by `python3 build.py`. The fragment is designed for the conversation renderer, which supplies styles and state support.

Validation includes 24 extreme-parameter model trials and browser checks for run/pause, manual pressure, venting, mode selection, legend toggles, and control and chart-label fit at phone and desktop widths. The browser check uses the installed Chrome and the bundled Playwright package; its preview file is temporary.

## Calibration needed

Measure static flexion and extension torque across pressure and knee angle, pressure step responses under load, actual segment/cuff geometry, and passive joint impedance. Replace the assumed coefficients with measured two-dimensional lookup tables. The bilateral internal chamber arrangement and which air line drives each direction also need confirmation.

## Sources informing the modeling approach

- [Harvard Soft Robotics Toolkit: textile actuator testing](https://softroboticstoolkit.com/textile-actuators/testing) describes measuring constrained torque across joint angle and pressure; its reported directional trends motivate the schematic coefficient curves, not the numerical values.
- [Sridar et al., A Soft-Inflatable Exosuit for Knee Rehabilitation](https://pmc.ncbi.nlm.nih.gov/articles/PMC7805964/) discusses angle- and pressure-dependent actuator stiffness in knee assistance. This prototype is not assumed to be that device.

The scientific sources motivate model structure only. No performance result from another suit is assigned to this prototype.
