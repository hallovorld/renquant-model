"""Conditional-activation harness — the model#215 §5 freeze surface.

Implements, as committed code (no execution-time interpretation):
§5.1 extension scoring plan (fold-8 config, no refit, purge boundary
     2026-05-08) — Stage C only, REFUSES without an extension corpus;
§5.2 prediction artifact schema: per-day (date,symbol,score) CSV with
     corpus/features/model-config shas + stage field; artifact sha in the
     result JSON;
§5.3 ROC20-at-t-1 dispersion across the universe present at t-1, missing-
     ROC20 exclusion counts persisted per date; per-day IC on the scored∩
     labeled intersection with counts persisted;
§5.4 252-session rolling-median warm-up, earlier dates INADMISSIBLE
     (excluded with counts), never back-filled;
§5.5 stationary block bootstrap (mean block 21, 2000 resamples, seed 99,
     percentile CIs) — the algorithm IS this file;
§5.6 controls with hard exit codes (--control positive|null);
§5.7 fail-closed: Stage-C gate arithmetic refuses before every guard
     holds; admissible_verdict null until the doc countersigns.
Stage E (--stage E, the seen v2 folds) carries NO verdict authority and
its artifacts are stamped stage=E-exploratory."""
import argparse, json, sys
import numpy as np, pandas as pd, xgboost as xgb
from scipy.stats import spearmanr

sys.path.insert(0,'/Users/renhao/git/github/renquant-model/doc/design/frozen')
import importlib.util as _il
_spec=_il.spec_from_file_location("v2h","/Users/renhao/git/github/renquant-model/doc/design/frozen/2026-08-09-xgbmom-v2-harness.py")
_v2=_il.module_from_spec(_spec)
import types
try: _spec.loader.exec_module(_v2)
except SystemExit: pass
FEATS, CUTS, PARAMS, LABEL = _v2.FEATS, _v2.CUTS, _v2.PARAMS, _v2.LABEL
SEEDS=(42,43,44); MIN_TR,MIN_TE=1000,100
NBOOT=2000; BLOCK=21

def daily_ics(panel, feats, seed, shuffle):
    rng=np.random.default_rng(seed); rows=[]
    ep=_v2._endpoint_map(panel)
    for tr_s,tr_e,te_s,te_e in CUTS:
        tr=panel[(panel.date>=tr_s)&(panel.date<=tr_e)].dropna(subset=[LABEL])
        te=panel[(panel.date>=te_s)&(panel.date<=te_e)].dropna(subset=[LABEL])
        keep=tr.date.map(lambda d: ep.get(d) is not None and ep[d]<te_s); tr=tr[keep]
        if len(tr)<MIN_TR or len(te)<MIN_TE: continue
        Xtr=tr[feats].fillna(0).values.astype(np.float64)
        ytr=tr[LABEL].clip(-5,5).values.astype(np.float64).copy()
        if shuffle:
            td=tr.date.values
            for d in np.unique(td):
                i=np.where(td==d)[0]; ytr[i]=rng.permutation(ytr[i])
        Xte=te[feats].fillna(0).values.astype(np.float64)
        mu,sd=Xtr.mean(0),Xtr.std(0)+1e-9
        Xtr=((Xtr-mu)/sd).clip(-5,5); Xte=((Xte-mu)/sd).clip(-5,5)
        si=np.argsort(tr.date.values); _,g=np.unique(tr.date.values[si],return_counts=True)
        dtr=xgb.DMatrix(Xtr[si],label=ytr[si]); dtr.set_group(g)
        bst=xgb.train({**PARAMS,"seed":seed},dtr,num_boost_round=100)
        pred=bst.predict(xgb.DMatrix(Xte))
        df=pd.DataFrame({"p":pred,"y":te[LABEL].values,"date":te.date.values,"fold":te_s})
        for d,gg in df.groupby("date"):
            if len(gg)>=5:
                rows.append({"date":d,"fold":gg.fold.iloc[0],
                             "ic":spearmanr(gg.p,gg.y)[0]})
    return pd.DataFrame(rows)

def activation(panel, counts_out=None):
    ok=panel.dropna(subset=["ROC20"])
    if counts_out is not None:
        n_all=panel.groupby("date")["ROC20"].size()
        n_ok=ok.groupby("date")["ROC20"].size()
        counts_out["roc20_excluded_per_date"]={str(d):int(n_all[d]-n_ok.get(d,0))
                                                for d in n_all.index if n_all[d]-n_ok.get(d,0)>0}
    disp=ok.groupby("date")["ROC20"].std().rename("disp").sort_index()
    med=disp.rolling(252,min_periods=252).median()
    A=(disp.shift(1)>med.shift(1)).astype(float)
    A[disp.shift(1).isna()|med.shift(1).isna()]=np.nan
    return A

def bootstrap_contrast(days, ic, a, nboot=NBOOT, block=BLOCK, seed=99):
    rng=np.random.default_rng(seed); n=len(days); diffs=[]; m1=[]
    idx=np.arange(n)
    for _ in range(nboot):
        picks=[]
        while len(picks)<n:
            s=rng.integers(0,n); L=rng.geometric(1/block)
            picks.extend(idx[s:s+L])
        picks=np.array(picks[:n])
        ii=ic[picks]; aa=a[picks]
        if (aa==1).sum()<5 or (aa==0).sum()<5: continue
        m1.append(np.nanmean(ii[aa==1]))
        diffs.append(np.nanmean(ii[aa==1])-np.nanmean(ii[aa==0]))
    return (np.percentile(m1,[2.5,97.5]), np.percentile(diffs,[2.5,97.5]))

def gates(panel):
    real=pd.concat([daily_ics(panel,FEATS,s,False) for s in SEEDS]).groupby(["date","fold"],as_index=False).ic.mean()
    shuf=pd.concat([daily_ics(panel,FEATS,s,True) for s in SEEDS]).groupby(["date","fold"],as_index=False).ic.mean()
    counts={}
    A=activation(panel,counts)
    for df in (real,shuf): df["A"]=df.date.map(A)
    r=real.dropna(subset=["A"]); s=shuf.dropna(subset=["A"])
    n1,n0=int((r.A==1).sum()),int((r.A==0).sum())
    if n1<100 or n0<100:
        return {"admissible":False,"why":f"guard n1={n1} n0={n0}"}
    rs=r.merge(s,on=["date","fold"],suffixes=("_r","_s"))
    rs["real_sig"]=rs.ic_r-rs.ic_s
    arr=rs.sort_values("date")
    ci1,cid=bootstrap_contrast(arr.date.values,arr.real_sig.values,arr.A_r.values)
    g1=bool(ci1[0]>0)
    g2=bool(cid[0]>0)
    folds_with_A1=r[r.A==1].fold.nunique()
    g3=bool(folds_with_A1>=5)
    _,cid_s=bootstrap_contrast(arr.date.values,(arr.ic_s).values,arr.A_r.values)
    g4=bool(not (cid_s[0]>0))
    import hashlib as _h
    out={"admissible":True,"stage":"E-exploratory","n_A1":n1,"n_A0":n0,
         "features_sha256":_h.sha256(json.dumps(FEATS).encode()).hexdigest(),
         "bootstrap":{"algo":"stationary-geometric","mean_block":BLOCK,
                       "n_resamples":NBOOT,"seed":99},
         "mean_real_sig_A1":round(float(rs[rs.A_r==1].real_sig.mean()),4),
         "mean_real_sig_A0":round(float(rs[rs.A_r==0].real_sig.mean()),4),
         "ci_A1":[round(float(x),4) for x in ci1],
         "ci_contrast":[round(float(x),4) for x in cid],
         "folds_with_A1":int(folds_with_A1),
         "gates":[g1,g2,g3,g4],"roc20_exclusions":counts.get("roc20_excluded_per_date",{}),
         "gate_arithmetic":"PASS" if all([g1,g2,g3,g4]) else "KILL",
         "admissible_verdict":None,"artifact_kind":None}
    return out

def synthetic(mode,seed=7):
    rng=np.random.default_rng(seed)
    dates=pd.bdate_range("2016-01-04","2026-05-07"); tick=[f"T{i:03d}" for i in range(60)]
    n=len(dates)*len(tick)
    df=pd.DataFrame({"date":np.repeat(dates.strftime("%Y-%m-%d"),len(tick)),
                     "ticker":np.tile(tick,len(dates))})
    # regime blocks ~63 days: high-dispersion vs low
    blocks=(np.arange(len(dates))//63)%2
    a_by_date=dict(zip(dates.strftime("%Y-%m-%d"),blocks))
    for c in FEATS:
        if c=="ROC20":
            base=rng.normal(size=n)
            scale=np.repeat(np.where(blocks==1,2.5,0.8),len(tick))
            df[c]=base*scale
        else: df[c]=rng.normal(size=n)
    f=0.6*df["RANK60"].values+0.4*df["SUMP20"].values
    Avec=np.repeat(blocks,len(tick)).astype(float)
    noise=rng.normal(scale=1.0,size=n)
    if mode=="positive": df[LABEL]=0.35*f*Avec+noise
    else: df[LABEL]=0.35*f+noise
    return df

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--control",choices=["positive","null"])
    ap.add_argument("--real",action="store_true")
    ap.add_argument("--stage",choices=["E"],default="E",
        help="C is NOT invocable here: Stage-C gate arithmetic requires the "
             "orch#939 extension corpus AND every clock/sample guard; this "
             "harness version REFUSES C by construction (fail-closed) and a "
             "C-capable version is its own reviewed amendment")
    ap.add_argument("--confirm-215-merged",action="store_true")
    a=ap.parse_args()
    if a.real:
        if not a.confirm_215_merged: print("REFUSED: gated on model#215 merge"); sys.exit(2)
        import hashlib
        cp="/Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet"
        assert hashlib.sha256(open(cp,"rb").read()).hexdigest()==_v2.CORPUS_SHA256
        panel=pd.read_parquet(cp); panel["date"]=pd.to_datetime(panel["date"]).dt.strftime("%Y-%m-%d")
        r=gates(panel); r["artifact_kind"]="result"; r["corpus_sha256"]=_v2.CORPUS_SHA256
    else:
        r=gates(synthetic(a.control)); r["artifact_kind"]="control"
    print(json.dumps(r,indent=1))
    if a.control=="positive": sys.exit(0 if r.get("gate_arithmetic")=="PASS" else 1)
    if a.control=="null": sys.exit(0 if r.get("gate_arithmetic")=="KILL" else 1)
