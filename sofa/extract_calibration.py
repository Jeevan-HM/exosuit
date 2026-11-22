"""Read-only workbook extraction. Run with Python + openpyxl; never writes sources."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
from openpyxl import load_workbook


def extract(directory):
    directory = Path(directory)
    result = {"schema_version": 1, "pressure_unit": "psi", "torque_unit": "N m",
              "angles_deg": [0,15,30,45,60,75,90], "pressures_psi": [0,5,10,15,20],
              "torque_basis": "measured pair; no division or additional actuator-count multiplier",
              "method": "Arithmetic means; sample SD (ddof=1). Empty zero-PSI column assigned a zero reference, matching the adjacent MATLAB loader. SD is variation of recorded samples, not independent-trial uncertainty.",
              "sources": []}
    for bank, name in [("flexion","Flexion_Angle_Char.xlsx"),("extension","Extension_Angle_Char.xlsx")]:
        path = directory/name
        book = load_workbook(path, read_only=True, data_only=True)
        grid = {"mean_nm": [], "sd_nm": [], "sample_count": [], "zero_reference_assigned": []}
        for angle in result["angles_deg"]:
            sheet = book[f"{angle}degrees"]
            rows = list(sheet.iter_rows(values_only=True))
            headers = list(rows[0])
            means, stds, counts, assigned = [], [], [], []
            for pressure in result["pressures_psi"]:
                if headers.count(pressure) != 1:
                    raise ValueError(f"Missing or duplicated header: {name}/{sheet.title}/{pressure}")
                j = headers.index(pressure)
                samples = [float(row[j]) for row in rows[1:] if len(row)>j
                           and isinstance(row[j], (float,int)) and not isinstance(row[j],bool)
                           and math.isfinite(row[j])]
                was_missing = not samples
                if was_missing:
                    if pressure != 0:
                        raise ValueError(f"Missing nonzero-pressure observations at {name}/{sheet.title}")
                    samples = [0.0]
                means.append(statistics.mean(samples)); stds.append(statistics.stdev(samples) if len(samples)>1 else 0.0)
                counts.append(0 if was_missing else len(samples)); assigned.append(was_missing)
            grid["mean_nm"].append(means); grid["sd_nm"].append(stds)
            grid["sample_count"].append(counts); grid["zero_reference_assigned"].append(assigned)
        book.close()
        result[bank] = grid
        result["sources"].append({"file":name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "sheets":[f"{a}degrees" for a in result["angles_deg"]],
                                  "header_range":"B1:F1","sample_range":"B2:F(last populated row)",
                                  "unit_evidence":"Adjacent plot_angle_torque_characterization.m: PSI headers, torque values read directly in N m; N_PARALLEL=1"})
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--output",type=Path,default=Path(__file__).parent/"data/torque_calibration.json")
    args=parser.parse_args()
    result=extract(args.directory)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print(f"Extracted 70 pressure-angle means to {args.output}; source workbooks unchanged.")
