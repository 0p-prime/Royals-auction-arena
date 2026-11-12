"""Standalone driver for the bounded continuous-pressure revision.

Reads the saved scored deliveries (outputs/delivery_scores.csv.gz, produced by
run.py) so the revision runs without refitting models, and writes
outputs/continuous_slopes.csv and outputs/validation_continuous.json.
run.py calls the same bpf_continuous.run_continuous stage in-memory, so a full
pipeline run and this driver produce identical outputs from the same scores.
"""
import argparse, json
from pathlib import Path
import pandas as pd
from bpf_continuous import run_continuous


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scores', default='outputs/delivery_scores.csv.gz')
    ap.add_argument('--config', default='config.json')
    ap.add_argument('--out', default='outputs')
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    out = Path(args.out)
    out.mkdir(exist_ok=True, parents=True)
    s = pd.read_csv(args.scores)
    full, val = run_continuous(s, cfg)
    full.to_csv(out / 'continuous_slopes.csv', index=False)
    (out / 'validation_continuous.json').write_text(json.dumps(val, indent=2, default=str))
    print(json.dumps(val, indent=2, default=str))


if __name__ == '__main__':
    main()
