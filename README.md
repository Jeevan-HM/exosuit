# Legacy conceptual browser simulation

This folder preserves the earlier seated-knee browser demonstration and its
source/tests. See [the original documentation](LEGACY_CONCEPTUAL_README.md).
It is separate from the OpenSim and MuJoCo human-walking models.

```sh
python3 build.py
node test-model.js
```

`knee-exosuit.html` is the built local demo. `MOVE_MANIFEST.json` records the
relocation. The builder now writes only this local HTML file.
