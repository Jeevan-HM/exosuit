"""Run the actual SOFA scene with the SOFA-enabled Python interpreter."""
import argparse
import json
import math
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seconds",type=float,default=5.)
    ap.add_argument("--config",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--chamber",action="store_true")
    ap.add_argument("--psi",type=float,default=2.)
    args=ap.parse_args()
    if not math.isfinite(args.seconds) or args.seconds<=0:ap.error("seconds must be positive and finite")
    try:
        import Sofa
        import SofaRuntime
        import Sofa.Simulation
    except ImportError as error:
        raise SystemExit("SOFA Python bindings are unavailable in this interpreter. Activate your SOFA/SofaPython3 environment, then rerun.\n"+str(error))
    root=Sofa.Core.Node("ExosuitHeadless")
    if args.chamber:
        from chamber_fem import createScene
        createScene(root,visuals=False)
        controller=root.getObject("ChamberPressure_PSI")
        controller.targetPsi.value=args.psi
    else:
        from knee_exosuit import createScene
        createScene(root,args.config,visuals=False,log_path=args.output)
        controller=root.getObject("ExosuitControls_PSI")
    init=getattr(Sofa.Simulation,"initRoot",None) or Sofa.Simulation.init
    init(root)
    try:
        for _ in range(round(args.seconds/float(root.dt.value))):
            Sofa.Simulation.animate(root,float(root.dt.value))
        if args.chamber:
            p=root.getChild("IllustrativeChamber_FEM").getObject("dofs").position.array()
            if not all(math.isfinite(float(x)) for row in p for x in row):raise RuntimeError("Non-finite FEM state")
            result={"engine":"SOFA","scene":"chamber_fem","time_s":float(root.time.value),"pressure_psi":float(controller.measuredPsi.value)}
        else:
            q=float(root.getChild("KneeDynamics").getObject("angle").position.value[0][0])
            if not math.isfinite(q):raise RuntimeError("Non-finite knee angle")
            c=controller.plant.cfg
            if not c["min_angle_deg"]-1e-6<=math.degrees(q)<=c["max_angle_deg"]+1e-6:raise RuntimeError("Knee outside limits")
            result={"engine":"SOFA","scene":"knee_exosuit","time_s":float(root.time.value),"angle_deg":math.degrees(q),"pressure_psi":controller.plant.pressure}
        print(json.dumps(result,indent=2))
    finally:
        if not args.chamber:controller.close_log()
        Sofa.Simulation.unload(root)


if __name__=="__main__":main()
