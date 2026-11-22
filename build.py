from pathlib import Path

root = Path(__file__).resolve().parent
source = (root / 'knee-exosuit.template.html').read_text()
model = (root / 'model.js').read_text()
fragment = source.replace('/*__MODEL_SOURCE__*/', model)
assert '/*__MODEL_SOURCE__*/' not in fragment
assert len(fragment.encode()) < 1_000_000
output = root / 'knee-exosuit.html'
output.write_text(fragment)
print(f'Built {output} ({len(fragment.encode())} bytes)')
