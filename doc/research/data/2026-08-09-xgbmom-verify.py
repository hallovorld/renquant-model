"""Recompute the four legs + verdict from the committed result JSON; exit 1 on drift."""
import json, sys
from pathlib import Path
import numpy as np
r=json.load(open(Path(__file__).with_name('2026-08-09-xgbmom-result.json')))
rs=np.array(r['real_signal_per_fold'],dtype=float)
legs=[bool(np.nanmean(rs)>0), bool(np.nansum(rs>0)>=6), bool(r['aa_seed_std']<=0.01),
      bool(np.nansum(rs[5:]>0)>=2 or not (rs[7]>0 and rs[5]<=0 and rs[6]<=0))]
bad=[]
if abs(np.nanmean(rs)-r['mean_real_signal'])>1e-4: bad.append('mean')
if int(np.nansum(rs>0))!=r['n_folds_pos']: bad.append('n_pos')
if legs!=r['legs']: bad.append(f'legs {legs} vs {r["legs"]}')
v='PASS' if all(legs) else 'KILL'
if v!=r['verdict']: bad.append('verdict')
if bad: print('DRIFT:',bad); sys.exit(1)
print(f'VERIFIED — legs recomputed from committed JSON: {v} (mean real signal {np.nanmean(rs):+.4f}, {int(np.nansum(rs>0))}/8 folds positive)')
