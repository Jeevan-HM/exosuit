# Official OpenSim base model and geometry

## Source and integrity

- Repository: [opensim-org/opensim-models](https://github.com/opensim-org/opensim-models).
- Pinned commit: [`d9b05d470b1a481c222372c85b75772faf8f7792`](https://github.com/opensim-org/opensim-models/commit/d9b05d470b1a481c222372c85b75772faf8f7792).
- Retrieved: 4 November 2026.
- Official model path: [`Models/Gait2392_Simbody/gait2392_thelen2003muscle.osim`](https://github.com/opensim-org/opensim-models/blob/d9b05d470b1a481c222372c85b75772faf8f7792/Models/Gait2392_Simbody/gait2392_thelen2003muscle.osim).
- Local model path: `base/gait2392_simbody.osim`. This is a filename alias; its contents are byte-for-byte unchanged from the official Thelen2003-muscle model.
- Model SHA-256: `3af1ca20aa87bc88b0b8cd54f2504331afa2aa03537cc868f1175fa1f50f3c0f`.
- `base/source_manifest.json` records source paths, byte counts, SHA-256 hashes and upstream Git blob SHA-1 hashes for all 21 source assets. Each downloaded asset was checked against the pinned repository tree and parsed as XML.

No muscles, dimensions, inertias, joint definitions, default coordinate values, or anatomical meshes in `base/` were modified. Derived exosuit models are generated separately.

## Attribution and license

The original model credits Delp S.L., Loan J.P., Hoy M.G., Zajac F.E., Topp E.L., Rosen J.M., Thelen D.G., Anderson F.C., and Seth A. Its embedded credits identify the Gait2392 3D model as work by D.G. Thelen (University of Wisconsin-Madison), and Ajay Seth, Frank C. Anderson and Scott L. Delp (Stanford University), based on Delp et al. (1990), Anderson and Pandy (1999, 2001), and the knee model of Yamaguchi and Zajac (1989). The complete original credits and publications remain embedded in the `.osim` file.

The model's embedded license is [Creative Commons Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/). The full legal code, downloaded from the official Creative Commons site, is included in `LICENSE_CC_BY_3.0.txt`. Preserve this attribution, source links, license and a description of changes when redistributing derived models. The anatomical visualization meshes are the official companion geometry referenced by this model and are distributed here with the same model attribution. The upstream Geometry README contains mesh-maintenance instructions and does not declare a separate mesh license.

## Geometry dependencies

All 20 distinct `<mesh_file>` dependencies are included unchanged from the same commit's `Geometry/` directory in `base/Geometry/`:

- `bofoot.vtp`
- `femur_l.vtp`
- `femur_r.vtp`
- `fibula.vtp`
- `foot.vtp`
- `hat_jaw.vtp`
- `hat_ribs.vtp`
- `hat_skull.vtp`
- `hat_spine.vtp`
- `l_bofoot.vtp`
- `l_fibula.vtp`
- `l_foot.vtp`
- `l_pelvis.vtp`
- `l_talus.vtp`
- `pelvis.vtp`
- `sacrum.vtp`
- `talus.vtp`
- `tibia_l.vtp`
- `tibia_r.vtp`
- `treadmill.vtp`

For direct loading of the base model, OpenSim can discover its adjacent `Geometry/` folder. When a generated model is written elsewhere, copy this folder beside the output `.osim`, use explicit relative mesh paths, or register its absolute directory with `OpenSim::ModelVisualizer::addDirToGeometrySearchPaths`. The meshes are display surfaces, not collision/contact meshes. The base model does not include a ground-contact force model or a human motor controller; loading it alone does not generate walking.

## Model conventions and scope

- 23 coordinates, 92 `Thelen2003Muscle` actuators, 12 rigid bodies and total body mass 75.1646 kg.
- SI units: metres, kilograms, seconds, newtons; rotational states use radians.
- Ground axes: +X forward, +Y up; gravity is `(0, -9.80665, 0)` m/s².
- Bilateral custom knees use `knee_angle_l` / `knee_angle_r`; negative coordinate motion is knee flexion. The nominal range is approximately -120° flexion to +10° hyperextension. These ranges are not clamped in the source model.
- For the project's convention of positive flexion, `project_knee_angle = -opensim_knee_angle` and `project_knee_moment = -opensim_generalized_knee_force`. Check this sign explicitly when attaching a device actuator; positive OpenSim knee force drives extension.
- Left thigh/shank bodies: `femur_l`, `tibia_l`; right: `femur_r`, `tibia_r`.
- Knee extensors include `rect_fem_*`, `vas_med_*`, `vas_int_*`, `vas_lat_*`; knee flexors include `semimem_*`, `semiten_*`, `bifemlh_*`, `bifemsh_*`, and biarticular gastrocnemius channels. These are model muscle activations/forces, not surface EMG.
- Preserve the full 3D model as the base; lock coordinates only in explicitly labeled task-specific derivatives.

This is a generic musculoskeletal foundation, not a subject-calibrated rehabilitation model. Scale geometry and mass properties, assess muscle strength and range of motion, fit device mechanics, and validate assisted and unassisted behavior against held-out measurements before drawing patient-specific conclusions. An illustrative seated model, prescribed-motion preview, or short forward dynamics check does not validate assisted gait or treatment benefit.
