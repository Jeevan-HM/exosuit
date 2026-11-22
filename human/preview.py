"""Render a PNG from the actual native forward trajectory (no pose replay)."""
import argparse
from pathlib import Path
import struct
import zlib
import mujoco
from .native_backend import HumanBackend
from .environment import load_config
from .device_factory import make_device
from .exosuit_visuals import visuals_from_config,configure_rendering
from .rl_contract import action_to_timing
from .human_avatar import HumanAvatar
from .rendering import prepare_human_appearance


def write_png(pixels,path):
    height,width,_=pixels.shape
    def chunk(kind,data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\x00'+row.tobytes() for row in pixels)
    output=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',width,height,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--at',type=float,default=2.)
    parser.add_argument('--config')
    parser.add_argument('--assist',action='store_true')
    parser.add_argument('--close-up',action='store_true')
    parser.add_argument('--anatomy',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('human_output/human_preview.png'))
    args=parser.parse_args()
    if not 0<=args.at<=60:parser.error('--at must be between 0 and 60 seconds')
    cfg=load_config(args.config)
    human=HumanBackend(exosuit=cfg.get('exosuit'));state=human.reset()
    device=make_device(cfg);device.enabled=args.assist
    device.set_timings(action_to_timing([0]*4,cfg['action_profile'],1.15).require_valid().as_tuple())
    contact=state['left_grf_n']>cfg['grf_threshold_n']
    while state['time_s']<args.at-1e-9 and not state['fallen']:
        torque=(device.advance(state['time_s'],human.human_control_dt_s,
                knee_angle_rad=state['knee_angle_rad'],knee_velocity_rad_s=state['knee_velocity_rad_s'])
                if hasattr(device,'telemetry') else device.advance(state['time_s'],human.human_control_dt_s))
        state=human.step(human.human_control_dt_s,torque)
        current=state['left_grf_n']>cfg['grf_threshold_n']
        if current and not contact:device.heel_strike(state['time_s'])
        contact=current
    human.model.vis.global_.offwidth=1000;human.model.vis.global_.offheight=800
    camera=mujoco.MjvCamera();camera.azimuth=-100;camera.elevation=-7;camera.distance=2.8
    camera.lookat[:]=human.data.body('pelvis').xpos
    camera.lookat[2]-=.10
    if args.close_up:
        camera.distance=1.2;camera.lookat[:]=human.data.body('tibia_l').xpos;camera.lookat[2]+=.08
    configure_rendering(human.model)
    visual=visuals_from_config(cfg)
    avatar=HumanAvatar(human.model) if not args.anatomy else None
    options=mujoco.MjvOption()
    if avatar is not None:prepare_human_appearance(human.model,options)
    with mujoco.Renderer(human.model,height=800,width=1000) as renderer:
        renderer.update_scene(human.data,camera=camera,scene_option=options)
        if avatar is not None:avatar.draw(renderer.scene,human.model,human.data)
        if cfg.get('exosuit',{}).get('enabled',False):
            visual.draw(renderer.scene,human.model,human.data,device.telemetry() if hasattr(device,'telemetry') else {})
        write_png(renderer.render(),args.output)
    human.close()
    print(f'Rendered native human at {state["time_s"]:.2f} s, fallen={state["fallen"]}: {args.output}')


if __name__=='__main__':main()
