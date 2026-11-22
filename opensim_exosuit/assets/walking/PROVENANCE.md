# Official OpenSim normal-walking motion

## Source and integrity

- Repository: [opensim-org/opensim-models](https://github.com/opensim-org/opensim-models).
- Pinned commit: [`d9b05d470b1a481c222372c85b75772faf8f7792`](https://github.com/opensim-org/opensim-models/commit/d9b05d470b1a481c222372c85b75772faf8f7792), matching the bundled Gait2392 model.
- Official source: [`Tutorials/Intro_to_Musculoskeletal_Modeling/normal.mot`](https://github.com/opensim-org/opensim-models/blob/d9b05d470b1a481c222372c85b75772faf8f7792/Tutorials/Intro_to_Musculoskeletal_Modeling/normal.mot).
- Retrieved: 4 November 2026.
- Local file: `normal.mot`; unchanged from the official file.
- SHA-256: `3251f79bc763b79f7edefff1fd314eb5ded0848ef195b94de983c7b4b8271da3`.
- Upstream Git blob SHA-1: `e8c78759b338e000b41533d0dadd6208ff6454a4`; verified against the pinned official repository tree.
- Size: 5,372 bytes.

This is OpenSim's distributed introductory tutorial motion, titled `normal_gait` in its header. Retain the official source attribution when sharing it. The motion header does not specify a separate data license or participant identity. The bundled anatomical model's attribution and CC BY 3.0 license are documented in `../PROVENANCE.md` and `../LICENSE_CC_BY_3.0.txt`.

## Native OpenSim verification

The file was loaded using OpenSim 4.6 `TimeSeriesTable`, then every frame was applied to the bundled official Gait2392 model. All 51 frame positions realized successfully with a finite whole-body mass-center position. Complete machine-readable results and source hashes are in `source_manifest.json`.

- 51 frames, from 0.00 to 1.00 seconds inclusive, sampled every 0.02 seconds.
- 18 columns: time plus 17 coordinate columns.
- `inDegrees=yes`: convert rotational coordinates from degrees to radians before assigning native OpenSim state values. The translational `pelvis_ty` column remains in metres.
- Every motion coordinate name matches a coordinate in the bundled Gait2392 model.
- Six model coordinates are omitted: `pelvis_tx`, `pelvis_tz`, `subtalar_angle_l`, `subtalar_angle_r`, `mtp_angle_l`, and `mtp_angle_r`. Leave these at their model defaults (all zero) for in-place walking playback.
- The bilateral knee columns use the model's native negative-flexion convention.

The source file does not contain all 23 model coordinates, muscle activations/excitations, joint forces, ground reaction forces, or a walking controller. It shows kinematic playback of a tutorial gait, without predicting how this person or a rehabilitating patient would respond to the exosuit.

When constructing a `StatesTrajectory` programmatically, start from finite model state defaults and fill the provided coordinate values explicitly. `createFromStatesTable(..., allowMissingColumns=True)` fills missing state variables with NaN, and a table marked `inDegrees=yes` is rejected by that states-trajectory method. A `.mot` can instead be associated directly with the model in the OpenSim GUI for motion playback.
