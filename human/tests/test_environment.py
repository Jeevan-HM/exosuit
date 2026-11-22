"""Check wrapper failures and units using an explicitly synthetic test fixture.

Walking capability and action-dependent biomechanics are tested separately with
native MuJoCo; this fixture must never be used as a training human.
"""
import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from human.assistance import AssistanceConfig, KneeAssistance
from human.environment import HumanExoEnv, HumanReadinessError, load_config


class EventFixture:
    human_control_dt_s = .01

    def __init__(self, fail_after=None, contact_events=True):
        self.fail_after=fail_after;self.contact_events=contact_events
        self.reset()

    def reset(self,seed=0):
        self.tick=0;self.torques=[]
        return self.sample()

    def step(self,duration_s,external_knee_torque_nm):
        self.tick+=1;self.torques.append(external_knee_torque_nm)
        return self.sample()

    def sample(self):
        t=self.tick*.01;p=round(t%1,8)
        return dict(time_s=t,knee_angle_rad=.2+.7*math.exp(-((p-.82)/.07)**2),
                    knee_velocity_rad_s=0.,left_grf_n=700.*(self.contact_events and .1<=p<.65),
                    right_grf_n=700.*(self.contact_events and (p<.15 or p>=.6)),
                    activation_vl_proxy=.2,activation_rf_proxy=.3,activation_bf_proxy=.1,
                    all_activations=[.2,.3,.1],forward_position_m=1.25*t,
                    forward_speed_m_s=1.25,pelvis_height_m=.95,
                    fallen=self.fail_after is not None and t>=self.fail_after)


class AssistanceTests(unittest.TestCase):
    def test_source_pressure_endpoints_and_extension_sign(self):
        device=KneeAssistance();device.enabled=True
        device.set_timings([.1,.2,.7,.2]);device.heel_strike(0)
        for t,expected in ((.1,0),(.11,25),(.3,25),(.31,0),(.7,0),(.71,20),(.91,0)):
            torque=device.advance(t,.01)
            self.assertEqual(device.actual_psi,expected)
            self.assertAlmostEqual(torque,-.4*expected)

    def test_no_pressure_before_first_actual_heelstrike(self):
        d=KneeAssistance();d.enabled=True
        self.assertEqual(d.advance(1,.01),0)
        self.assertEqual(d.command_psi,0)

    def test_heelstrike_restarts_phase_and_lag_is_explicit(self):
        d=KneeAssistance(AssistanceConfig(pressure_time_constant_s=.1))
        d.enabled=True;d.heel_strike(0)
        d.advance(.13,.01)
        self.assertGreater(d.actual_psi,0);self.assertLess(d.actual_psi,25)
        d.heel_strike(.14);d.advance(.14,.01)
        self.assertEqual(d.command_psi,0)

    def test_disabled_and_saturation(self):
        d=KneeAssistance(AssistanceConfig(maximum_torque_nm=2))
        d.enabled=True;d.heel_strike(0)
        self.assertEqual(d.advance(.13,.01),-2)
        d.enabled=False
        self.assertEqual(d.advance(.14,.01),0)


class EnvironmentTests(unittest.TestCase):
    def make_env(self,backend=None,**changes):
        c=load_config();c.update(strides_per_action=1,maximum_reset_time_s=4,
                                maximum_action_time_s=4)
        c.update(changes)
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'config.json';path.write_text(json.dumps(c))
        return HumanExoEnv(path,backend or EventFixture())

    def test_baseline_then_measured_stride_obs_and_negative_reward(self):
        env=self.make_env(device_enabled=True)
        obs,info=env.reset()
        self.assertEqual(obs.shape,(5,));self.assertTrue(info['ready_for_training'])
        self.assertTrue(all(t==0 for t in env.human.torques))
        obs,reward,terminated,truncated,info=env.step([0,0,0,0])
        self.assertEqual(obs.shape,(5,));self.assertFalse(terminated or truncated)
        self.assertTrue(info['observation_valid']);self.assertEqual(info['strides_averaged'],1)
        self.assertEqual(reward,-info['cost']);self.assertLess(reward,0)
        self.assertAlmostEqual(info['measurement_end_time_s']-info['measurement_start_time_s'],1)
        self.assertAlmostEqual(info['activation_squared_integral_s'],(.2**2+.3**2+.1**2)/3)
        self.assertLess(min(env.human.torques),0)
        self.assertEqual(set(r['pressure_command_psi'] for r in env.trace),{0.,20.,25.})
        self.assertTrue(all(0<=r['pressure_psi']<=25 for r in env.trace))
        self.assertTrue(any(0<r['pressure_psi']<20 for r in env.trace))
        # These observations came from fixture contact/angle events, not actor output.
        self.assertNotAlmostEqual(obs[0],.1)

    def test_baseline_fall_refuses_fabricated_observation(self):
        env=self.make_env(EventFixture(fail_after=.5))
        with self.assertRaises(HumanReadinessError) as error:env.reset()
        self.assertFalse(error.exception.diagnostics['ready_for_training'])
        self.assertEqual(error.exception.diagnostics['reason'],'baseline_fall')
        self.assertIsNone(env.features)

    def test_missing_contacts_refuse_gait(self):
        env=self.make_env(EventFixture(contact_events=False))
        with self.assertRaises(HumanReadinessError) as error:env.reset()
        self.assertEqual(error.exception.diagnostics['reason'],'missing_baseline_gait_events')

    def test_assisted_fall_terminates_without_new_valid_obs(self):
        backend=EventFixture();env=self.make_env(backend)
        previous,_=env.reset();backend.fail_after=backend.sample()['time_s']+.02
        obs,reward,terminated,truncated,info=env.step([0,0,0,0])
        np.testing.assert_array_equal(obs,previous)
        self.assertTrue(terminated);self.assertFalse(truncated)
        self.assertFalse(info['observation_valid']);self.assertIsNone(info['features9'])
        self.assertEqual(reward,-100)

    def test_invalid_action_and_step_after_done(self):
        env=self.make_env();env.reset()
        _,reward,terminated,_,info=env.step([1,1,1,1])
        self.assertTrue(terminated);self.assertEqual(info['failure'],'invalid_action')
        self.assertEqual(reward,-20)
        with self.assertRaises(RuntimeError):env.step([0]*4)

    def test_legacy_proxy_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValueError,'uncalibrated'):
            self.make_env(reward_mode='legacy_proxy')

    def test_episode_limit_does_not_wait_for_whole_strides(self):
        env=self.make_env(maximum_episode_time_s=1.2);env.reset()
        obs,reward,terminated,truncated,info=env.step([0]*4)
        self.assertFalse(terminated);self.assertTrue(truncated)
        self.assertLessEqual(env.human.sample()['time_s'],1.2+1e-9)
        self.assertFalse(info['observation_valid'])
        self.assertEqual(info['termination_reason'],'episode_time_limit')


if __name__=='__main__':unittest.main()
