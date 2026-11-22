"""Stride-level exosuit RL interface around a forward musculoskeletal human.

This module never fabricates gait observations when the human falls or lacks
contact/peak events. Native integration and human-walking readiness are distinct.
"""
import json
import math
from pathlib import Path
import numpy as np
from .assistance import AssistanceConfig,KneeAssistance
from .device_factory import make_device,validate_exosuit
from .rl_contract import action_to_timing,observation_from_features,legacy_cost,extract_strides

BASE=Path(__file__).resolve().parent


class HumanReadinessError(RuntimeError):
    def __init__(self,message,diagnostics):
        super().__init__(message);self.diagnostics=diagnostics


def load_config(path=None):
    c=json.loads(Path(path or BASE/'config.json').read_text())
    if c.get('schema_version')!=1:raise ValueError('Unsupported human simulation config')
    if c['action_profile'] not in ('v1_percent','v9_seconds'):raise ValueError('Unknown action profile')
    for key in ('control_dt_s','grf_threshold_n','target_speed_m_s','maximum_reset_time_s',
                'maximum_action_time_s','maximum_episode_time_s'):
        if not math.isfinite(c[key]) or c[key]<=0:raise ValueError(f'{key} must be positive and finite')
    if int(c['strides_per_action'])!=c['strides_per_action'] or c['strides_per_action']<1:
        raise ValueError('strides_per_action must be a positive integer')
    if int(c['discard_strides_after_action'])!=c['discard_strides_after_action'] or c['discard_strides_after_action']<0:
        raise ValueError('discard_strides_after_action must be a nonnegative integer')
    if c['reward_mode'] not in ('human_effort_proxy','legacy_proxy'):raise ValueError('Unknown reward mode')
    if c['reward_mode']=='legacy_proxy' and not c.get('allow_uncalibrated_legacy_proxy',False):
        raise ValueError('Legacy EMG proxy cost is uncalibrated; opt in explicitly for software compatibility only')
    gain=np.asarray(c['emg_proxy_gain'],dtype=float)
    if gain.shape!=(3,) or not np.isfinite(gain).all() or np.any(gain<0):raise ValueError('Invalid activation proxy gains')
    for key in ('speed_penalty_weight','effort_weight','fall_penalty','missing_gait_penalty','invalid_action_penalty'):
        if not math.isfinite(c[key]) or c[key]<0:raise ValueError(f'{key} must be nonnegative and finite')
    AssistanceConfig(**c['assistance']).validate()
    validate_exosuit(c)
    return c


class HumanExoEnv:
    """Gym-style API; no Gym installation is required for native diagnostics.

    reset -> (observation5, info); step -> (obs5, reward, terminated, truncated,
    info). Cost-minimizing DHDP callers should use info['cost'] rather than
    treating the returned maximizing reward as a positive cost.
    """
    def __init__(self,config=None,backend=None):
        self.cfg=load_config(config)
        if backend is None:
            from .native_backend import HumanBackend
            backend=HumanBackend(exosuit=self.cfg.get('exosuit'))
        self.human=backend
        self.device=make_device(self.cfg)
        self.device.enabled=bool(self.cfg['device_enabled'])
        if abs(self.cfg['control_dt_s']-self.human.human_control_dt_s)>1e-9:
            raise ValueError('Outer control_dt_s must match the human control interval')
        self.trace=[];self.features=None;self._ready=False;self._done=False

    def _record(self,s):
        row=dict(s)
        row['pressure_command_psi']=self.device.command_psi
        row['pressure_psi']=self.device.actual_psi
        row['assistance_torque_nm']=self.device.torque_nm
        row['applied_active_joint_work_j']=self._applied_work_j
        row['applied_active_joint_power_w']=self._applied_power_w
        if hasattr(self.device,'telemetry'):
            row['exosuit']=self.device.telemetry()
            row.update({k:v for k,v in row['exosuit'].items() if k.endswith(('_psi','_nm','_w','_j'))})
            row['exosuit_net_torque_nm']=self.device.torque_nm+row.get('exosuit_passive_torque_nm',0.)
        self.trace.append(row)

    def _advance(self):
        before=self.human.sample();dt=self.cfg['control_dt_s']
        torque=(self.device.advance(before['time_s'],dt,knee_angle_rad=before['knee_angle_rad'],
                    knee_velocity_rad_s=before['knee_velocity_rad_s']) if hasattr(self.device,'telemetry')
                    else self.device.advance(before['time_s'],dt))
        after=self.human.step(dt,torque)
        # The native solver holds this applied moment over the control interval.
        # Its coupled joint work follows the resulting angular displacement.
        work=torque*(after['knee_angle_rad']-before['knee_angle_rad'])
        self._applied_work_j+=work;self._applied_power_w=work/dt
        left=after['left_grf_n']>self.cfg['grf_threshold_n']
        if left and not self._last_left_contact:self.device.heel_strike(after['time_s'])
        self._last_left_contact=left
        self._record(after)
        return after

    def _strides(self,start_index=0):
        rows=self.trace[start_index:]
        if len(rows)<3:return []
        proxy=np.asarray([[r['activation_vl_proxy'],r['activation_rf_proxy'],r['activation_bf_proxy']] for r in rows])
        proxy*=np.asarray(self.cfg['emg_proxy_gain'])
        return extract_strides(np.asarray([r['time_s'] for r in rows]),
                               np.asarray([r['knee_angle_rad'] for r in rows]),
                               np.asarray([r['left_grf_n'] for r in rows]),
                               np.asarray([r['right_grf_n'] for r in rows]),
                               activation_proxy=proxy,profile=self.cfg['action_profile'],
                               threshold_n=self.cfg['grf_threshold_n'])

    @staticmethod
    def _valid(strides):
        return [s for s in strides if s.valid]

    def _diagnostics(self,reason):
        last=self.trace[-1] if self.trace else self.human.sample()
        return {'ready_for_training':False,'reason':reason,'time_s':float(last['time_s']),
                'fallen':bool(last['fallen']),'valid_strides':len(self._valid(self._strides())),
                'muscle_signal_semantics':'activation-group proxies; not measured EMG',
                'long_term_adaptation_modeled':False,
                'last_sample':{k:v for k,v in last.items() if isinstance(v,(float,int,bool,str))}}

    def reset(self,seed=0,options=None):
        state=self.human.reset(seed=seed);self.device.reset()
        self._applied_work_j=0.;self._applied_power_w=0.
        self.device.enabled=False;self.trace=[];self.features=None;self._ready=False;self._done=False
        self._last_left_contact=state['left_grf_n']>self.cfg['grf_threshold_n'];self._record(state)
        deadline=state['time_s']+self.cfg['maximum_reset_time_s']
        count=self.cfg['strides_per_action']
        while state['time_s']<deadline:
            state=self._advance()
            if state['fallen']:
                raise HumanReadinessError('The baseline human fell before producing valid walking observations.',self._diagnostics('baseline_fall'))
            strides=self._valid(self._strides())
            if len(strides)>=count:
                self.features=np.mean(np.asarray([s.vector for s in strides[-count:]]),axis=0)
                self._ready=True
                self.device.enabled=bool(self.cfg['device_enabled'])
                return np.asarray(observation_from_features(self.features,self.cfg['action_profile'])),{
                    'ready_for_training':True,'baseline_valid_strides':count,
                    'baseline_end_time_s':float(state['time_s']),
                    'baseline_validation_scope':'event completeness only; not subject-specific biomechanical validation',
                    'baseline_condition':('wearing_unpowered_exosuit' if self.cfg.get('exosuit',{}).get('enabled',False) else 'bare_human'),
                    'features9':self.features.tolist(),'long_term_adaptation_modeled':False}
        raise HumanReadinessError('The baseline did not produce enough valid strides.',self._diagnostics('missing_baseline_gait_events'))

    def step(self,action):
        if not self._ready:raise HumanReadinessError('Call reset and establish a valid baseline before RL steps.',self._diagnostics('baseline_not_ready'))
        if self._done:raise RuntimeError('Episode ended; call reset before another action')
        previous=np.asarray(observation_from_features(self.features,self.cfg['action_profile']))
        try:
            command=action_to_timing(action,self.cfg['action_profile'],float(self.features[8]))
            command.require_valid()
            self.device.set_timings(command.as_tuple())
        except (ValueError,TypeError) as error:
            self._done=True
            return previous,-self.cfg['invalid_action_penalty'],True,False,{
                'cost':self.cfg['invalid_action_penalty'],'failure':'invalid_action','detail':str(error),
                'observation_valid':False,'features9':None}
        self.device.enabled=bool(self.cfg['device_enabled'])
        index=max(0,len(self.trace)-2);start=self.human.sample()
        deadline=min(start['time_s']+self.cfg['maximum_action_time_s'],self.cfg['maximum_episode_time_s'])
        needed=self.cfg['strides_per_action']+self.cfg['discard_strides_after_action']
        state=start
        while state['time_s']<deadline:
            state=self._advance()
            if state['fallen']:
                self._done=True
                return previous,-self.cfg['fall_penalty'],True,False,{
                    'cost':self.cfg['fall_penalty'],'failure':'human_fall','observation_valid':False,
                    'features9':None,'diagnostics':self._diagnostics('assisted_fall')}
            strides=self._valid(self._strides(index))
            if len(strides)>=needed:break
        else:
            self._done=True
            if state['time_s']>=self.cfg['maximum_episode_time_s']-1e-9:
                return previous,0.,False,True,{
                    'cost':0.,'termination_reason':'episode_time_limit',
                    'observation_valid':False,'features9':None,
                    'partial_measurement_discarded':True}
            return previous,-self.cfg['missing_gait_penalty'],False,True,{
                'cost':self.cfg['missing_gait_penalty'],'failure':'missing_gait_events',
                'observation_valid':False,'features9':None}
        selected=strides[self.cfg['discard_strides_after_action']:needed]
        self.features=np.mean(np.asarray([s.vector for s in selected]),axis=0)
        # Score the same measured interval as the averaged observations. Settling
        # strides and samples before the action do not belong in this reward.
        begin=selected[0].heelstrike_start;end=selected[-1].heelstrike_end
        rows=[r for r in self.trace[index:] if begin-1e-9<=r['time_s']<=end+1e-9]
        times=np.asarray([r['time_s'] for r in rows])
        activations=np.asarray([r['all_activations'] for r in rows],dtype=float)
        squared_activation=np.mean(activations**2,axis=1)
        effort=float(np.sum(.5*(squared_activation[:-1]+squared_activation[1:])*np.diff(times)))
        duration=float(times[-1]-times[0]);distance=float(rows[-1]['forward_position_m']-rows[0]['forward_position_m'])
        mean_speed=distance/max(duration,1e-9)
        # Prevent reward improvement by standing still or walking backward.
        effort_per_m=effort/max(distance,.05)
        speed_cost=(mean_speed-self.cfg['target_speed_m_s'])**2
        compatibility_cost=float(legacy_cost(self.features,action,self.cfg['action_profile']))
        cost=(compatibility_cost if self.cfg['reward_mode']=='legacy_proxy' else
              self.cfg['effort_weight']*effort_per_m+self.cfg['speed_penalty_weight']*speed_cost)
        truncated=state['time_s']>=self.cfg['maximum_episode_time_s'];self._done=truncated
        return np.asarray(observation_from_features(self.features,self.cfg['action_profile'])),-float(cost),False,truncated,{
            'cost':float(cost),'reward_mode':self.cfg['reward_mode'],'features9':self.features.tolist(),
            'observation_valid':True,'strides_averaged':len(selected),'command_seconds':list(command.as_tuple()),
            'measurement_start_time_s':float(begin),'measurement_end_time_s':float(end),
            'applied_active_joint_work_j':float(rows[-1]['applied_active_joint_work_j']-rows[0]['applied_active_joint_work_j']),
            'mean_speed_m_s':mean_speed,'activation_squared_integral_s':effort,
            'activation_squared_per_m':effort_per_m,'legacy_cost_from_uncalibrated_activation_proxy':compatibility_cost,
            'muscle_signal_semantics':'activation-group proxies; not measured EMG',
            'metabolic_cost_computed':False,'long_term_adaptation_modeled':False}

    def close(self):
        close=getattr(self.human,'close',None)
        if close:close()
