"""Transparent Markov chase win-probability (batting side) from pre-ball score, balls and wickets.

Bowler pressure here means "the batting side is in a strong position and the bowler has to stop them
or bring it back". That needs a state measure using runs needed, legal balls left and wickets lost
together. This module computes pb = P(batting side wins) under a simple model by exact dynamic
programming over (runs needed, legal balls left, wickets lost).

TRAINING FIELDS (per delivery, from EARLIER seasons only): legal balls bowled so far in the innings
(-> over index), wickets lost so far, team runs on the delivery (total, capped at run_clip), legal flag,
dismissal flag. Frequencies by (over, wickets-lost bucket) are shrunk toward the all-delivery
frequencies with a pseudo-count of `context_pseudo_deliveries`.
INFERENCE FIELDS (pre-ball): target, runs scored so far, legal balls bowled so far, wickets lost.
Outcomes of the delivery being scored and later deliveries are never used.
CHRONOLOGY: a delivery in season Y <= train_end uses tables from seasons < Y only (2019 onward, so
2022 uses 2019-21); deliveries after train_end use one fixed table from seasons <= train_end. No match
informs its own pb.

Assumptions/limits: outcome mix depends only on over and wickets-lost bucket (no batter/bowler identity,
no change in risk-taking when ahead or behind); team runs per delivery clipped at run_clip; runs needed
must stay <= nmax (checked); illegal-delivery repeats are solved by fixed-point iteration (truncation
error tested); not Duckworth-Lewis-Stern; pb is an ORDINAL model-defined score, not a calibrated
probability (see outputs/winprob_check.json).
"""
import numpy as np
import pandas as pd


def prepare_training(raw):
    """Add legal balls bowled and wickets lost before each delivery (pre-ball) to raw delivery data."""
    d = raw.sort_values(['match_id', 'innings', 'sequence']).copy()
    g = d.groupby(['match_id', 'innings'])
    d['pre_balls'] = g.legal.cumsum() - d.legal
    d['wickets_lost'] = g.dismissals.cumsum() - d.dismissals
    return d


def wbucket(w, buckets):
    for i, (a, b) in enumerate(buckets):
        if a <= w <= b:
            return i
    return len(buckets) - 1


def outcome_tables(df, seasons, wp):
    """df: deliveries with season, pre_balls, wickets_lost, total, legal, dismissals.
    seasons: iterable of seasons whose deliveries may be used (caller enforces chronology)."""
    B = wp['wicket_buckets']
    d = df[df.season.isin(list(seasons))]
    key = pd.DataFrame({'o': (d.pre_balls // 6).clip(0, wp['max_over_index']).astype(int),
                        'wb': d.wickets_lost.astype(int).map(lambda w: wbucket(w, B)),
                        'r': d.total.astype(int).clip(0, wp['run_clip']),
                        'l': d.legal.astype(int), 'k': (d.dismissals > 0).astype(int)})
    all_out = key.groupby(['r', 'l', 'k']).size()
    tabs = {}
    for o in range(wp['max_over_index'] + 1):
        for b in range(len(B)):
            sub = key[(key.o == o) & (key.wb == b)]
            c = sub.groupby(['r', 'l', 'k']).size().reindex(all_out.index, fill_value=0).astype(float)
            p = (c + wp['context_pseudo_deliveries'] * all_out / all_out.sum()) / (c.sum() + wp['context_pseudo_deliveries'])
            tabs[(o, b)] = [(r, l, k, float(x)) for (r, l, k), x in p.items() if x > 0]
    return tabs


def solve(tabs, wp, iters=None):
    """V[b][w][n]: P(batting wins) with b legal balls left, w wickets lost, n runs still needed."""
    nmax, balls, wk, B = wp['nmax'], wp['balls'], wp['wickets'], wp['wicket_buckets']
    iters = wp['illegal_repeat_iters'] if iters is None else iters
    V = np.zeros((balls + 1, wk + 1, nmax + 1))
    V[:, :, 0] = 1.0
    idx = np.arange(nmax + 1)

    def sh(arr, r):
        return arr[np.maximum(idx - r, 0)]
    for b in range(1, balls + 1):
        o = min((balls - b) // 6, wp['max_over_index'])
        for w in range(wk - 1, -1, -1):
            base = np.zeros(nmax + 1)
            ill = []
            for r, l, k, p in tabs[(o, wbucket(w, B))]:
                w2 = min(w + k, wk)
                if l:
                    base += p * sh(V[b - 1, w2], r)
                elif k and w2 != w:
                    base += p * sh(V[b, w2], r)
                else:
                    ill.append((r, p))
            v = base.copy()
            for _ in range(iters if ill else 0):
                v = base + sum(p * sh(v, r) for r, p in ill)
            v[0] = 1.0
            V[b, w] = v
    return V


def pbat(V, runs_needed, legal_left, wickets_lost):
    n = np.asarray(runs_needed)
    if (n > V.shape[2] - 1).any():
        raise ValueError('runs needed exceeds nmax; raise config v4.winprob.nmax')
    n = np.clip(n, 0, V.shape[2] - 1).astype(int)
    b = np.clip(np.asarray(legal_left), 0, V.shape[0] - 1).astype(int)
    w = np.clip(np.asarray(wickets_lost), 0, V.shape[1] - 1).astype(int)
    return V[b, w, n]


def forward_tables_by_season(train_df, cfg):
    """{season: V} following the chronology rule above."""
    wp = cfg['v4']['winprob']
    te = cfg['train_end']
    seasons = sorted(set(cfg['years']))
    out = {}
    fixed = None
    for y in seasons:
        if y <= te:
            use = range(cfg['warmup_year'], y)
            out[y] = solve(outcome_tables(train_df, use, wp), wp)
        else:
            if fixed is None:
                fixed = solve(outcome_tables(train_df, range(cfg['warmup_year'], te + 1), wp), wp)
            out[y] = fixed
    return out
