"""File-only bridge for timing actions or pressure commands; no hardware I/O."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from control import validate_timings
from units import finite

DEFAULT_PATH = Path(__file__).resolve().parent / "live_command.json"


def write_sim_command(*, timings_s=None, pressure_psi=None, cycle_duration_s=1.27,
                      enabled=True, heel_strike=False, path=DEFAULT_PATH):
    if (timings_s is None) == (pressure_psi is None):
        raise ValueError("Supply exactly one of timings_s or pressure_psi")
    payload={"schema_version":1,"sequence":time.time_ns(),"enabled":bool(enabled),
             "heel_strike":bool(heel_strike)}
    if timings_s is not None:
        duration=finite(cycle_duration_s)
        payload.update(mode="timed",timings_s=list(validate_timings(timings_s,duration)),cycle_duration_s=duration)
    else:
        if len(pressure_psi)!=2 or any(finite(v)<0 for v in pressure_psi):
            raise ValueError("pressure_psi needs two nonnegative PSI values")
        payload.update(mode="manual",pressure_psi=[finite(v) for v in pressure_psi])
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",dir=path.parent,prefix=".sim-command-",suffix=".json",delete=False) as f:
        tmp=Path(f.name);json.dump(payload,f,allow_nan=False);f.write("\n")
    try:os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()
    return payload


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--timings",nargs=4,type=float,metavar=("TA","TB","TC","TD"))
    group.add_argument("--pressure",nargs=2,type=float,metavar=("P0_PSI","P1_PSI"))
    ap.add_argument("--duration",type=float,default=1.27)
    ap.add_argument("--disable",action="store_true")
    ap.add_argument("--heel-strike",action="store_true")
    ap.add_argument("--output",type=Path,default=DEFAULT_PATH)
    args=ap.parse_args()
    result=write_sim_command(timings_s=args.timings,pressure_psi=args.pressure,
                             cycle_duration_s=args.duration,enabled=not args.disable,
                             heel_strike=args.heel_strike,path=args.output)
    print(json.dumps(result))
