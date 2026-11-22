"""Add carried exosuit mass/inertia and passive knee damping to a human MJCF.

The mass values are adjustable assumptions, not estimates inferred from photos.
Fixed child bodies are intentional: anatomical limb bodies already declare
their own inertial elements, so adding massive visual geoms alone would not
reliably change the compiled parent body's inertia.
"""
from dataclasses import dataclass
from pathlib import Path
import math
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class DeviceMechanics:
    thigh_mass_kg: float = 0.25
    shank_mass_kg: float = 0.20
    thigh_cuff_radius_m: float = 0.075
    shank_cuff_radius_m: float = 0.060
    thigh_assembly_length_m: float = 0.22
    shank_assembly_length_m: float = 0.22
    thigh_center_distal_m: float = 0.22
    shank_center_distal_m: float = 0.18
    passive_knee_damping_nm_s_per_rad: float = 0.03
    side: str = "l"

    def validate(self):
        if self.side not in ("l", "r"):
            raise ValueError("Device side must be l or r")
        for name, value in vars(self).items():
            if name == "side":
                continue
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        for name in ("thigh_cuff_radius_m", "shank_cuff_radius_m",
                     "thigh_assembly_length_m", "shank_assembly_length_m"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in ("thigh_center_distal_m", "shank_center_distal_m"):
            if getattr(self, name) > 0.4:
                raise ValueError(f"{name} exceeds the modeled limb length")
        return self


def _absolute_assets(root, asset_base_dir):
    """Make the returned model loadable from a different output directory."""
    base = Path(asset_base_dir).resolve()
    compiler = root.find("compiler")
    meshdir = Path(compiler.get("meshdir", "")) if compiler is not None else Path()
    texturedir = Path(compiler.get("texturedir", "")) if compiler is not None else Path()
    for element in root.iter():
        if not isinstance(element.tag, str) or "file" not in element.attrib:
            continue
        filename = Path(element.get("file"))
        if filename.is_absolute():
            continue
        directory = meshdir if element.tag == "mesh" else texturedir if element.tag == "texture" else Path()
        path = directory / filename
        if not path.is_absolute():
            path = base / path
        element.set("file", str(path.resolve()))
    if compiler is not None:
        compiler.attrib.pop("meshdir", None)
        compiler.attrib.pop("texturedir", None)


def _add_fixed_assembly(parent, name, mass, radius, length, distal_center):
    if parent is None:
        raise ValueError(f"Missing anatomical body for {name}")
    if parent.find(f"body[@name='{name}']") is not None:
        raise ValueError(f"{name} is already present; refusing duplicate carried mass")
    if mass == 0:
        return
    # Homogenized thin cylindrical shell with its longitudinal axis along local
    # Y. It approximates distributed cuff/sleeve hardware, not an FEM material.
    radial_inertia = mass * (radius * radius / 2.0 + length * length / 12.0)
    axial_inertia = mass * radius * radius
    body = ET.SubElement(parent, "body", name=name, pos=f"0 {-distal_center:.12g} 0")
    ET.SubElement(body, "inertial", mass=f"{mass:.12g}", pos="0 0 0",
                  diaginertia=f"{radial_inertia:.12g} {axial_inertia:.12g} {radial_inertia:.12g}")


def augment_human_xml(xml_text, asset_base_dir, config=None):
    """Return MJCF with real carried device inertia and viscous knee drag.

    Local -Y follows both the femur and tibia distally. The knee hinge uses local
    Z. No joints, muscles, actuators, keyframes, body poses, or ground contacts
    are added or replaced. Visual cuff/pouch geoms should have mass=0 when this
    helper supplies the assembly mass.

    Relative assets resolve against asset_base_dir. MuJoCo is used once to read
    the inherited anatomical knee damping accurately, then added damping is
    made explicit on that same joint. Positive added damping dissipates energy
    in either motion direction; no torque sign conversion is required.
    """
    config = (config or DeviceMechanics()).validate()
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(xml_text, parser=parser)
    _absolute_assets(root, asset_base_dir)
    side = config.side
    thigh = root.find(f".//body[@name='femur_{side}']")
    shank = root.find(f".//body[@name='tibia_{side}']")
    knee = root.find(f".//joint[@name='knee_angle_{side}']")
    if thigh is None or shank is None or knee is None:
        raise ValueError(f"Expected femur_{side}, tibia_{side}, and knee_angle_{side}")
    if config.passive_knee_damping_nm_s_per_rad:
        import mujoco
        baseline = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
        dof = int(baseline.joint(f"knee_angle_{side}").dofadr[0])
        original = float(baseline.dof_damping[dof])
        knee.set("damping", f"{original + config.passive_knee_damping_nm_s_per_rad:.12g}")
    _add_fixed_assembly(thigh, f"exosuit_{side}_thigh_inertia", config.thigh_mass_kg,
                        config.thigh_cuff_radius_m, config.thigh_assembly_length_m,
                        config.thigh_center_distal_m)
    _add_fixed_assembly(shank, f"exosuit_{side}_shank_inertia", config.shank_mass_kg,
                        config.shank_cuff_radius_m, config.shank_assembly_length_m,
                        config.shank_center_distal_m)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def write_augmented_model(base_xml_path, output_path, config=None):
    source = Path(base_xml_path).resolve()
    target = Path(output_path).resolve()
    if source == target:
        raise ValueError("Write the augmented model separately from the source human model")
    xml = augment_human_xml(source.read_text(), source.parent, config)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(xml)
    return target
