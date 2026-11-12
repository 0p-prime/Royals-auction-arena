"""Standalone driver for the v3 runs/wickets components stage (no model refit)."""
import json
from pathlib import Path
import pandas as pd
from bpf_components import run_components

cfg = json.loads(Path('config.json').read_text())
s = pd.read_csv('outputs/delivery_scores.csv.gz')
s = s.assign()
from bpf_continuous import add_centered_rae
full, val = run_components(add_centered_rae(s, cfg), cfg)
full.to_csv('outputs/components_bowlers.csv', index=False)
Path('outputs/validation_components.json').write_text(json.dumps(val, indent=2, default=str))
print(json.dumps(val, indent=2, default=str))
