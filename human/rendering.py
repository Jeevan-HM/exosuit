"""Display a solid human while preserving the underlying anatomical physics."""
import mujoco


def prepare_human_appearance(model,options):
    """Hide existing bones and muscle paths in the renderer, not the solver.

    geom_group is a compiled visibility field. No mass, collision filter,
    muscle parameter or body pose is changed, and the model is not recompiled.
    """
    model.geom_group[model.geom_bodyid!=0]=5
    options.geomgroup[5]=0
    options.sitegroup[:]=0
    options.tendongroup[:]=0
    options.flags[mujoco.mjtVisFlag.mjVIS_TENDON]=0
    options.flags[mujoco.mjtVisFlag.mjVIS_ACTUATOR]=0
