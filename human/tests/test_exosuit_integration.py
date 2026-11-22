"""Verify that wearable inertia, pressure and appearance are coupled correctly."""
import unittest
import numpy as np
import mujoco
from human.environment import HumanExoEnv,load_config
from human.native_backend import HumanBackend
from human.exosuit_visuals import visuals_from_config


class ExosuitIntegrationTests(unittest.TestCase):
    def test_mass_and_damping_change_without_adding_motor_coordinates(self):
        cfg=load_config();bare=HumanBackend();worn=HumanBackend(exosuit=cfg['exosuit'])
        self.addCleanup(worn.close);self.addCleanup(bare.close)
        self.assertEqual((bare.model.nq,bare.model.nu),(worn.model.nq,worn.model.nu))
        self.assertAlmostEqual(worn.model.body_mass.sum()-bare.model.body_mass.sum(),.45)
        dof=int(worn.model.joint('knee_angle_l').dofadr[0])
        self.assertAlmostEqual(worn.model.dof_damping[dof]-bare.model.dof_damping[dof],.03)
        self.assertAlmostEqual(worn.sample()['device_mass_kg'],.45)
        self.assertAlmostEqual(worn.sample()['human_mass_kg'],bare.sample()['body_mass_kg'])
        self.assertFalse(np.array_equal(worn.data.qM,bare.data.qM))

    def test_loaded_human_and_pressure_lag_produce_actual_assisted_strides(self):
        env=HumanExoEnv();self.addCleanup(env.close)
        _,baseline=env.reset()
        self.assertEqual(baseline['baseline_condition'],'wearing_unpowered_exosuit')
        _,_,terminated,truncated,info=env.step([0]*4)
        self.assertFalse(terminated or truncated)
        self.assertEqual(info['strides_averaged'],5)
        rows=env.trace
        self.assertEqual(set(r['extension_command_psi'] for r in rows),{0.,20.,25.})
        self.assertTrue(all(r['flexion_pressure_psi']==0 for r in rows))
        self.assertTrue(any(0<r['extension_pressure_psi']<r['extension_command_psi'] for r in rows))
        self.assertTrue(all(r['assistance_torque_nm']<=0 for r in rows))
        self.assertTrue(np.isfinite([r['active_joint_work_j'] for r in rows]).all())
        actual_work=sum(b['assistance_torque_nm']*(b['knee_angle_rad']-a['knee_angle_rad'])
                        for a,b in zip(rows[:-1],rows[1:]))
        self.assertAlmostEqual(rows[-1]['applied_active_joint_work_j'],actual_work)

    def test_visuals_follow_limb_and_pressure_without_altering_physics(self):
        cfg=load_config();h=HumanBackend(exosuit=cfg['exosuit']);self.addCleanup(h.close)
        visual=visuals_from_config(cfg);scene=mujoco.MjvScene(h.model,maxgeom=1000)
        before=h.data.qpos.copy();mass=h.model.body_mass.copy()
        visual.draw(scene,h.model,h.data,{'extension_pressure_psi':0},clear=True)
        vented=np.array([scene.geoms[i].size.copy() for i in range(scene.ngeom)])
        first=scene.geoms[0].pos.copy()
        visual.draw(scene,h.model,h.data,{'extension_pressure_psi':25},clear=True)
        inflated=np.array([scene.geoms[i].size.copy() for i in range(scene.ngeom)])
        self.assertGreater(scene.ngeom,250);self.assertGreater(np.max(inflated-vented),0)
        np.testing.assert_array_equal(h.data.qpos,before)
        np.testing.assert_array_equal(h.model.body_mass,mass)
        h.step(.2,0);visual.draw(scene,h.model,h.data,{},clear=True)
        self.assertGreater(np.linalg.norm(scene.geoms[0].pos-first),.001)


if __name__=='__main__':unittest.main()
