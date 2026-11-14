# Batting Pressure Analysis (supplied matches, 2022-26)

Ranks batsmen in the supplied matches (IPL, T20I and Asia Cup tournaments) by pressure
performance vs normal performance. Descriptive analysis of recorded data.

## Setup

Requires Python 3 with the dependencies in `requirements.txt`. Unpack Cricsheet IPL JSON under `data/raw/ipl_json`, or set `IPL_JSON_DIR` to that directory. Run commands from this directory; create `outputs/` and `logs/` before the pipeline.

```sh
python3 -m pip install -r requirements.txt
mkdir -p outputs logs
```

The source distribution does not contain raw match data or intermediate parquet files. Data-dependent tests require the pipeline outputs. The previously reported 18-test result belongs to the supplied verified analysis run, not a fresh fit in the website build.

## Reproduce
1. `python3 data_loader.py`   - Cricsheet IPL JSON -> deliveries.parquet (Step 0 audit)
2. `python3 features.py`      - pre-ball features + targets (Steps 1-2)
3. `python3 mpi_lpi_models.py` - MPI/LPI models, grouped OOF (Step 3)
4. `python3 stacker.py`       - nested-OOF stacked BPI (Step 4)
5. `python3 relation_analysis.py` - MPI/LPI/BPI relation, calibration, heatmap (Step 4B)
6. `python3 expected_runs.py` - situation-only E[runs]/E[dismissal], wicket penalty, RAE (Step 5)
7. `python3 ppf.py`           - buckets, PPF, EB shrinkage, match bootstrap CIs (Steps 6-7)
8. `python3 selector.py`      - selection funnel, role quota variant, 2x2 context (Step 8)
9. `python3 validate.py`      - temporal/split-half/baseline/stability diagnostics (Step 9)
10. `python3 -m pytest tests/ -q` - 18 tests (leakage, buckets, shrinkage, funnel, calibration, regression)

Raw data for the published run: the supplied ball-by-ball CSV (867 playable fixtures, 2022-26),
not stored in the repository. Config: config.yaml. Outputs: outputs/.
Deviations from the original written spec: no batter-hand/bowler-type features (absent
in Cricsheet); centered RAE (dismissal minus expected dismissal); decile monotonicity
treated as a diagnostic (passed strictly anyway).

Dependencies are minimum supported targets, not a lockfile from the historical run. Regeneration may vary across library versions. The website imports the verified aggregate exports rather than silently refitting them. The only source portability change in this distribution is the raw-input path override; estimator functions are unchanged.
