"""Build the portable SOFA delivery; omit source experiment programs and logs."""
import hashlib
import json
from pathlib import Path
import zipfile

base=Path(__file__).resolve().parent
files=[*base.glob('*.py'),base/'config.json',base/'README.md',base/'.gitignore',
       base/'data/torque_calibration.json',base/'examples/pressure_replay.csv',
       base/'validation/validation_report.json',base/'data/source_manifest.json']
destination=base.parent/'Exosuit_SOFA_PSI.zip'
for file in files:
    if not file.is_file():raise FileNotFoundError(file)
with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for file in sorted(files):z.write(file,Path('Exosuit_SOFA_PSI')/file.relative_to(base))
print(json.dumps({'output':str(destination),'files':len(files),'bytes':destination.stat().st_size,
                  'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()},indent=2))
