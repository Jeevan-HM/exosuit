"""Native physics integration tests, distinct from physiological validation."""
import importlib.util
import unittest
import numpy as np


@unittest.skipUnless(importlib.util.find_spec('mujoco'),'Install human/requirements.txt for native checks')
class NativeHumanTests(unittest.TestCase):
    def backend(self):
        import mujoco
        if mujoco.__version__!='3.4.0':self.skipTest('Tested native configuration pins MuJoCo 3.4.0')
        from human.native_backend import HumanBackend
        return HumanBackend()

    def test_native_muscles_contact_and_repeatable_reset(self):
        human=self.backend();start=human.reset()
        self.assertEqual(human.model.nu,22)
        self.assertAlmostEqual(human.physics_dt_s,.001)
        for _ in range(200):state=human.step(.01,0)
        final_position=human.data.qpos.copy()
        self.assertFalse(state['fallen']);self.assertGreater(state['distance_m'],1)
        self.assertTrue(np.isfinite(state['all_activations']).all())
        human.reset()
        for _ in range(200):state=human.step(.01,0)
        np.testing.assert_allclose(human.data.qpos,final_position,rtol=0,atol=1e-12)

    def test_torque_changes_forward_dynamics_and_uses_positive_flexion(self):
        human=self.backend();human.reset()
        baseline=human.step(.1,0);q0=human.data.qpos.copy()
        human.reset();human.step(.1,-8)
        self.assertGreater(np.linalg.norm(human.data.qpos-q0),1e-5)
        dof=human.env.external_dof
        self.assertEqual(human.data.qfrc_applied[dof],8)

    def test_fall_stops_without_silent_reset(self):
        human=self.backend();human.reset()
        for _ in range(300):
            state=human.step(.01,8)
            if state['fallen']:break
        self.assertTrue(state['fallen'])
        fallen_time=state['time_s'];state=human.step(.5,0)
        self.assertEqual(state['time_s'],fallen_time)
        self.assertTrue(state['fallen'])


if __name__=='__main__':unittest.main()
