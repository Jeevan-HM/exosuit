"""Native SOFA knee-dynamics scene. Open with runSofa -l SofaPython3.

The Vec1d state is a generalized angle in radians and its UniformMass entry is
rotational inertia in kg m². SOFA, not Python, integrates this mechanical state.
Fabric chambers are schematic display geometry driven by chamber pressure;
their material stresses are not solved in this reduced-order scene.
"""
import atexit
import csv
from datetime import datetime
import json
import math
import os
from pathlib import Path
import sys

BASE=Path(__file__).resolve().parent
if str(BASE) not in sys.path:sys.path.insert(0,str(BASE))
import Sofa
from plant import ExosuitPlant, load_config, validate_config
from control import validate_timings
from geometry import SuitGeometry
from units import clamp, finite

PLUGINS=["Sofa.Component.AnimationLoop","Sofa.Component.ODESolver.Forward",
         "Sofa.Component.StateContainer","Sofa.Component.Mass",
         "Sofa.Component.MechanicalLoad"]
VISUAL_PLUGINS=["Sofa.Component.Visual","Sofa.GL.Component.Rendering3D"]


class ExosuitController(Sofa.Core.Controller):
    def __init__(self,root,joint,load,plant,visuals=None,geometry=None,log_path=None):
        super().__init__(name="ExosuitControls_PSI")
        self.root,self.joint,self.load,self.plant=root,joint,load,plant
        self.visuals,self.geometry=visuals or {},geometry
        c=plant.cfg
        controls=[("mode","string",c["mode"],"timed, manual, or replay (CSV selected at scene load)"),
                  ("profile","string",c["profile"],"rl = 10 PSI preset; heuristic = 5 PSI preset"),
                  ("actuationEnabled","bool",c["actuation_enabled"],"False commands venting; SOFA keeps moving"),
                  ("pressureAmplitudePsi","double",c["pressure_amplitude_psi"],"Gauge PSI; simulation limit comes from config.json"),
                  ("manualP0Psi","double",c["manual_pressure_psi"][0],"First Pd element, PSI gauge"),
                  ("manualP1Psi","double",c["manual_pressure_psi"][1],"Second Pd element, PSI gauge"),
                  ("timingsSeconds","vector<double>",c["timings_s"],"tA,tB,tC,tD in seconds"),
                  ("cycleDurationSeconds","double",c["cycle_duration_s"],"Synthetic cycle length; must be >= tD"),
                  ("wearerTracking","bool",c["wearer_tracking"],"False = relaxed seated leg; true = assumed PD muscle drive")]
        for name,type_,value,help_ in controls:
            self.addData(name,type=type_,value=value,help=help_,group="Inputs (PSI)")
        for name in ("p0Psi","p1Psi","kneeAngleDeg","suitTorqueNm","wearerTorqueNm"):
            self.addData(name,type="double",value=0.0,group="Telemetry")
        self.addData("status",type="string",value="Ready; press SOFA Play",group="Telemetry")
        self.last_time=-1.0;self.last_live_mtime=None;self.telemetry=None
        self.last_profile=c["profile"]
        self.live_path=BASE/c["live_command_file"]
        self.next_live_poll=0.0;self.last_error=None;self.log=None
        if c["log_enabled"]:
            if log_path is None:
                stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                log_path=BASE/"logs"/f"knee_{stamp}.csv"
            log_path=Path(log_path);log_path.parent.mkdir(parents=True,exist_ok=True)
            self.log=log_path.open("x",newline="")
            self.writer=None;self.log_count=0;self.next_log=0.0
            atexit.register(self.close_log)

    def close_log(self):
        if self.log is not None and not self.log.closed:self.log.close()

    def _input(self):
        c=self.plant.cfg
        profile=str(self.profile.value).strip().lower()
        if profile!=self.last_profile:
            if profile not in ("rl","heuristic"):raise ValueError("profile must be rl or heuristic")
            self.pressureAmplitudePsi.value=10.0 if profile=="rl" else 5.0
            self.last_profile=profile
        updates={"mode":str(self.mode.value).strip().lower(),"profile":profile,
                 "actuation_enabled":bool(self.actuationEnabled.value),
                 "pressure_amplitude_psi":finite(self.pressureAmplitudePsi.value),
                 "manual_pressure_psi":[finite(self.manualP0Psi.value),finite(self.manualP1Psi.value)],
                 "timings_s":[float(x) for x in self.timingsSeconds.value],
                 "cycle_duration_s":finite(self.cycleDurationSeconds.value),
                 "wearer_tracking":bool(self.wearerTracking.value)}
        candidate={**c,**updates};validate_config(candidate)
        if candidate["mode"]=="replay" and self.plant.controller.replay is None:
            raise ValueError("To use CSV replay, set mode=replay in config.json and reload the scene")
        c.update(updates)

    def _poll_live_file(self,t):
        if t<self.next_live_poll:return
        self.next_live_poll=t+1/30
        if not self.live_path.exists():return
        stat=self.live_path.stat();signature=(stat.st_mtime_ns,stat.st_size)
        if signature==self.last_live_mtime:return
        if stat.st_size>16384:raise ValueError("Live command JSON is too large")
        obj=json.loads(self.live_path.read_text())
        if obj.get("schema_version")!=1:raise ValueError("Invalid live command schema")
        mode=obj.get("mode")
        if mode=="timed":
            duration=finite(obj["cycle_duration_s"])
            timing=validate_timings(obj["timings_s"],duration)
            self.timingsSeconds.value=list(timing);self.cycleDurationSeconds.value=duration
            self.profile.value="rl"
        elif mode=="manual":
            values=obj["pressure_psi"]
            if len(values)!=2 or any(not 0<=finite(v)<=self.plant.cfg["max_pressure_psi"] for v in values):
                raise ValueError("Live pressures must be two PSI values within the configured limit")
            self.manualP0Psi.value=finite(values[0]);self.manualP1Psi.value=finite(values[1])
        else:raise ValueError("Live mode must be timed or manual")
        self.mode.value=mode;self.actuationEnabled.value=bool(obj.get("enabled",True))
        if obj.get("heel_strike",False):self.plant.controller.heel_strike(t)
        self.plant.next_command_time=t
        self.last_live_mtime=signature

    def onAnimateBeginEvent(self,event):
        t,dt=float(self.root.time.value),float(self.root.dt.value)
        if t<self.last_time-1e-10 or (t<=1e-12 and self.last_time>=0):
            self.plant.reset();self.next_live_poll=0.0
            if self.log:self.next_log=0.0
        self.last_time=t
        try:
            self._poll_live_file(t);self._input()
            self.last_error=None
            self.status.value="Running: "+self.plant.cfg["mode"]
        except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as error:
            self.plant.cfg["actuation_enabled"]=False
            self.status.value="Venting: "+str(error)
            if self.last_error!=str(error):print("[Exosuit] "+str(error));self.last_error=str(error)
        q=float(self.joint.position.value[0][0]);v=float(self.joint.velocity.value[0][0])
        out=self.plant.applied_torque(t,q,v,dt)
        self.load.forces.value=[[out["net_torque_nm"]]]
        self.telemetry=out
        for name,key in [("p0Psi","p0_psi"),("p1Psi","p1_psi"),("kneeAngleDeg","angle_deg"),
                         ("suitTorqueNm","suit_torque_nm"),("wearerTorqueNm","human_torque_nm")]:
            self.findData(name).value=out[key]
        if self.log and t+1e-12>=self.next_log:
            if self.writer is None:
                self.writer=csv.DictWriter(self.log,fieldnames=list(out));self.writer.writeheader()
            self.writer.writerow(out);self.log_count+=1;self.next_log=t+1/self.plant.cfg["command_rate_hz"]
            if self.log_count%30==0:self.log.flush()

    def onAnimateEndEvent(self,event):
        q=float(self.joint.position.value[0][0]);v=float(self.joint.velocity.value[0][0])
        newq,newv=self.plant.project_limits(q,v)
        if (newq,newv)!=(q,v):
            self.joint.position.value=[[newq]];self.joint.velocity.value=[[newv]]
        self.kneeAngleDeg.value=math.degrees(newq)
        if self.geometry:
            bank=dict(zip(self.plant.cfg["channel_map"],self.plant.pressure))
            for name,(vertices,_) in self.geometry.meshes(newq,bank["flexion"],bank["extension"],self.plant.cfg["max_pressure_psi"]).items():
                self.visuals[name].position.value=vertices

    def onKeypressedEvent(self,event):
        key=str(event.get("key","")).upper()
        if key=="A":self.actuationEnabled.value=not self.actuationEnabled.value
        elif key=="T":self.mode.value="timed"
        elif key=="M":self.mode.value="manual"
        elif key=="H":self.wearerTracking.value=not self.wearerTracking.value
        elif key=="0":
            self.manualP0Psi.value=0;self.manualP1Psi.value=0;self.actuationEnabled.value=False
        elif key in ("F","E"):
            self.mode.value="manual";self.actuationEnabled.value=True
            channel=self.plant.cfg["channel_map"].index("flexion" if key=="F" else "extension")
            self.manualP0Psi.value=self.pressureAmplitudePsi.value if channel==0 else 0
            self.manualP1Psi.value=self.pressureAmplitudePsi.value if channel==1 else 0


def createScene(root,config_path=None,visuals=True,log_path=None):
    cfg=load_config(config_path or os.environ.get("EXOSUIT_CONFIG"))
    plant=ExosuitPlant(cfg)
    root.dt=cfg["dt_s"];root.gravity=[0,0,0];root.animate=False
    # Gravity is included once as generalized knee torque, rather than as a
    # translational force on an angular coordinate.
    root.addObject("RequiredPlugin",name="required",pluginName=PLUGINS+(VISUAL_PLUGINS if visuals else []))
    root.addObject("DefaultAnimationLoop")
    knee=root.addChild("KneeDynamics")
    knee.addObject("EulerExplicitSolver",name="integrator",symplectic=True)
    joint=knee.addObject("MechanicalObject",name="angle",template="Vec1d",
                         position=[[math.radians(cfg["initial_angle_deg"])]],velocity=[[0.0]])
    knee.addObject("UniformMass",name="rotationalInertia",template="Vec1d",vertexMass=plant.inertia)
    load=knee.addObject("ConstantForceField",name="appliedTorque",template="Vec1d",indices=[0],forces=[[0.0]])
    visual_objects={};geometry=None
    if visuals:
        root.addObject("VisualStyle",displayFlags="showVisualModels hideBehaviorModels hideForceFields")
        root.addObject("DefaultVisualManagerLoop")
        root.addObject("BackgroundSetting",color=[0.065,0.075,0.095])
        root.addObject("InteractiveCamera",name="camera",position=[.65,.35,1.4],lookAt=[-.05,-.15,0],zNear=.01,zFar=10)
        geometry=SuitGeometry(cfg["length_m"])
        display=root.addChild("SchematicSuit_VisualOnly")
        for name,(vertices,triangles) in geometry.meshes(math.radians(cfg["initial_angle_deg"]),0,0,cfg["max_pressure_psi"]).items():
            node=display.addChild(name)
            visual_objects[name]=node.addObject("OglModel",name="surface",position=vertices,
                                                triangles=triangles,color=geometry.COLORS[name])
    root.addObject(ExosuitController(root,joint,load,plant,visual_objects,geometry,log_path))
    return root
