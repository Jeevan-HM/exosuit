"""Numerical reference for model tests; this runner does not use SOFA."""
import argparse
import csv
import json
import math
from pathlib import Path
from plant import ExosuitPlant, load_config


def simulate(config,seconds=5.,output=None):
    plant=ExosuitPlant(config)
    dt=config["dt_s"];q=math.radians(config["initial_angle_deg"]);v=0.
    rows=[]
    for i in range(round(seconds/dt)):
        out=plant.applied_torque(i*dt,q,v,dt)
        rows.append(out)
        v+=out["net_torque_nm"]*dt/plant.inertia
        q+=v*dt
        q,v=plant.project_limits(q,v)
    if output:
        path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("w",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    return {"engine":"Python numerical reference (not SOFA)","time_s":len(rows)*dt,"angle_deg":math.degrees(q),
            "pressure_psi":plant.pressure,"rows":rows}


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--config",type=Path)
    ap.add_argument("--seconds",type=float,default=5.);ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    if not math.isfinite(args.seconds) or args.seconds<=0:ap.error("seconds must be positive and finite")
    result=simulate(load_config(args.config),args.seconds,args.output)
    result.pop("rows");print(json.dumps(result,indent=2))
