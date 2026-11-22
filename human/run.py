"""Run native human diagnostics or the gated stride-level environment."""
import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np


def save_trace(rows,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    # CSV is for scalar diagnostics; JSONL retains every sample and all muscles.
    keys=['time_s','knee_angle_rad','knee_velocity_rad_s','left_grf_n','right_grf_n',
          'activation_vl_proxy','activation_rf_proxy','activation_bf_proxy',
          'forward_position_m','forward_speed_m_s','pelvis_height_m','fallen',
          'pressure_command_psi','pressure_psi','assistance_torque_nm']
    keys+=['device_mass_kg','extension_command_psi','extension_pressure_psi',
           'flexion_command_psi','flexion_pressure_psi','exosuit_passive_torque_nm',
           'exosuit_net_torque_nm','active_joint_power_w','active_joint_work_j',
           'applied_active_joint_work_j','applied_active_joint_power_w']
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for row in rows:w.writerow({key:row.get(key) for key in keys})
    with path.with_suffix('.jsonl').open('w') as f:
        for row in rows:f.write(json.dumps(row,allow_nan=False)+'\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--diagnostic',action='store_true',help='Test true forward dynamics without requiring successful walking')
    ap.add_argument('--seconds',type=float,default=10.)
    ap.add_argument('--torque',type=float,default=0.,help='Diagnostic constant left-knee torque, positive flexion, N m')
    ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--config',type=Path)
    ap.add_argument('--output',type=Path,default=Path('human_output'))
    ap.add_argument('--actions',type=int,default=1)
    ap.add_argument('--action',nargs=4,type=float,default=[0,0,0,0])
    args=ap.parse_args()
    if not np.isfinite(args.seconds) or args.seconds<=0 or not np.isfinite(args.torque):ap.error('Invalid duration or torque')
    if args.actions<1:ap.error('--actions must be positive')
    args.output.mkdir(parents=True,exist_ok=True)
    from .native_backend import HumanBackend
    if args.diagnostic:
        human=HumanBackend();state=human.reset(args.seed);rows=[state]
        while state['time_s']<args.seconds-1e-9 and not state['fallen']:
            state=human.step(human.human_control_dt_s,args.torque);rows.append(state)
        save_trace(rows,args.output/'diagnostic.csv')
        report={'mode':'native_forward_dynamics_diagnostic','requested_seconds':args.seconds,
                'simulated_seconds':state['time_s'],'fall_detected':state['fallen'],
                'ready_for_policy_ranking':False,'baseline_gait_validated':False,
                'status':'failed_walk_test' if state['fallen'] else 'integration_completed_gait_still_requires_validation',
                'muscle_actuators':int(human.model.nu),'body_mass_kg':float(human.model.body_mass.sum()),
                'torque_nm_positive_flexion':args.torque,'muscle_signal':'activation proxy, not EMG',
                'native_model_validation':state.get('validation_status')}
        (args.output/'diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        return 2 if state['fallen'] else 0
    from .environment import HumanExoEnv,HumanReadinessError
    env=HumanExoEnv(config=args.config)
    try:
        obs,info=env.reset(seed=args.seed);summaries=[{'reset':info}]
        for _ in range(args.actions):
            obs,reward,terminated,truncated,info=env.step(args.action)
            summaries.append({'observation':obs.tolist(),'reward':reward,'terminated':terminated,'truncated':truncated,'info':info})
            if terminated or truncated:break
        save_trace(env.trace,args.output/'rollout.csv')
        (args.output/'rollout.json').write_text(json.dumps(summaries,indent=2)+'\n')
        print(json.dumps(summaries,indent=2));return 2 if info.get('failure') else 0
    except HumanReadinessError as error:
        save_trace(env.trace,args.output/'baseline_failure.csv')
        (args.output/'baseline_readiness.json').write_text(json.dumps(error.diagnostics,indent=2)+'\n')
        print(json.dumps(error.diagnostics,indent=2));return 2
    finally:env.close()


if __name__=='__main__':sys.exit(main())
