"""xgb_mom_60d execution harness — implements model#211's frozen table.
--control {positive,null} runs synthetic; --real requires --confirm-211-merged.
Every constant FROM THE DOC; none is a choice here."""
import argparse, json, sys
import numpy as np, pandas as pd, xgboost as xgb
from scipy.stats import spearmanr

# The frozen 70 features, EMBEDDED (identical to the merged #211 prereg
# section 5 and to this doc's inheritance) -- the harness is
# self-contained; no machine-local reads.
FEATS = ["BETA10", "BETA20", "BETA30", "BETA5", "BETA60", "CNTN10", "CNTN20", "CNTN30", "CNTN5", "CNTN60", "CNTP10", "CNTP20", "CNTP30", "CNTP5", "CNTP60", "IMAX10", "IMAX20", "IMAX30", "IMAX5", "IMAX60", "IMIN10", "IMIN20", "IMIN30", "IMIN5", "IMIN60", "MAX10", "MAX20", "MAX30", "MAX5", "MAX60", "MIN10", "MIN20", "MIN30", "MIN5", "MIN60", "QTLD10", "QTLD20", "QTLD30", "QTLD5", "QTLD60", "QTLU10", "QTLU20", "QTLU30", "QTLU5", "QTLU60", "RANK10", "RANK20", "RANK30", "RANK5", "RANK60", "ROC10", "ROC20", "ROC30", "ROC5", "ROC60", "RSV10", "RSV20", "RSV30", "RSV5", "RSV60", "SUMN10", "SUMN20", "SUMN30", "SUMN5", "SUMN60", "SUMP10", "SUMP20", "SUMP30", "SUMP5", "SUMP60"]
LABEL = 'fwd_60d_excess'
CUTS = [  # v2 (model#213): 91-calendar-day gap > ~84-day label window
    ("2016-01-01","2018-12-31","2019-04-01","2019-12-31"),
    ("2016-01-01","2019-12-31","2020-04-01","2020-12-31"),
    ("2016-01-01","2020-12-31","2021-04-01","2021-12-31"),
    ("2016-01-01","2021-12-31","2022-04-01","2022-12-31"),
    ("2016-01-01","2022-12-31","2023-04-01","2023-12-31"),
    ("2016-01-01","2023-12-31","2024-04-01","2024-12-31"),
    ("2016-01-01","2024-12-31","2025-04-01","2025-12-31"),
    ("2016-01-01","2025-12-31","2026-04-01","2026-05-07")]
PARAMS = {"objective":"rank:pairwise","eta":0.05,"max_depth":5,
          "min_child_weight":50,"subsample":0.7,"colsample_bytree":0.7,
          "nthread":10,"verbosity":0}
SEEDS = (42,43,44); MIN_TR, MIN_TE = 1000, 100

def cs_ic(p,a,d):
    df=pd.DataFrame({"p":p,"y":a,"date":d})
    ics=[spearmanr(g["p"],g["y"])[0] for _,g in df.groupby("date") if len(g)>=5]
    ics=[x for x in ics if not np.isnan(x)]
    return float(np.mean(ics)) if ics else np.nan

LABEL_SESSIONS = 60   # fwd_60d label horizon in trading sessions

def _endpoint_map(panel):
    """date -> the date of the 60th trading session AFTER it, on the
    corpus's OWN calendar (model#213 P0: per-row enforcement, no calendar
    arithmetic). Rows whose endpoint falls beyond the corpus are mapped to
    None (their labels realize after data end; they carry labels only if
    the builder computed them -- endpoint treated as +inf for purging)."""
    dates=sorted(panel.date.unique()); idx={d:i for i,d in enumerate(dates)}
    return {d:(dates[i+LABEL_SESSIONS] if i+LABEL_SESSIONS < len(dates) else None)
            for d,i in idx.items()}

def one_pass(panel, feats, seed, shuffle, purge_log=None):
    rng=np.random.default_rng(seed); out=[]
    ep=_endpoint_map(panel)
    for tr_s,tr_e,te_s,te_e in CUTS:
        tr=panel[(panel.date>=tr_s)&(panel.date<=tr_e)].dropna(subset=[LABEL])
        te=panel[(panel.date>=te_s)&(panel.date<=te_e)].dropna(subset=[LABEL])
        # P0 duty: PER-ROW purge -- a training row survives iff its realized
        # label endpoint is strictly before the test interval start
        n0=len(tr)
        keep=tr.date.map(lambda d: ep.get(d) is not None and ep[d] < te_s)
        tr=tr[keep]
        if purge_log is not None:
            surv_ep=tr.date.map(ep)
            purge_log.append({"test_start":te_s,"n_train_pre_purge":int(n0),
                "n_purged":int(n0-len(tr)),
                "max_surviving_label_endpoint":(max(surv_ep) if len(surv_ep) else None)})
        if len(tr)<MIN_TR or len(te)<MIN_TE: out.append(np.nan); continue
        Xtr=tr[feats].fillna(0).values.astype(np.float64)
        ytr=tr[LABEL].clip(-5,5).values.astype(np.float64).copy()
        if shuffle:
            td=tr["date"].values
            for d in np.unique(td):
                i=np.where(td==d)[0]; ytr[i]=rng.permutation(ytr[i])
        Xte=te[feats].fillna(0).values.astype(np.float64)
        mu,sd=Xtr.mean(axis=0),Xtr.std(axis=0)+1e-9
        Xtr=((Xtr-mu)/sd).clip(-5,5); Xte=((Xte-mu)/sd).clip(-5,5)
        si=np.argsort(tr["date"].values)
        _,gsz=np.unique(tr["date"].values[si],return_counts=True)
        dtr=xgb.DMatrix(Xtr[si],label=ytr[si]); dtr.set_group(gsz)
        p={**PARAMS,"seed":seed}
        bst=xgb.train(p,dtr,num_boost_round=100)
        out.append(cs_ic(bst.predict(xgb.DMatrix(Xte)),te[LABEL].values,te["date"].values))
    return out

def legs(panel, feats):
    purge_log=[]
    real=np.nanmean([one_pass(panel,feats,s,False,purge_log if s==SEEDS[0] else None) for s in SEEDS],axis=0)
    shuf=np.nanmean([one_pass(panel,feats,s,True) for s in SEEDS],axis=0)
    rs=real-shuf
    seed_means=[np.nanmean(one_pass(panel,feats,s,False)) for s in SEEDS]
    l1=bool(np.nanmean(rs)>0)
    l2=bool(np.nansum(rs>0)>=6)
    l3=bool(np.nanstd(seed_means)<=0.01)
    recent=rs[5:]  # folds 2024, 2025, 2026
    l4=bool(np.nansum(recent>0)>=2 or not (recent[2]>0 and recent[0]<=0 and recent[1]<=0))
    return {"purge_per_fold":purge_log,
            "real_per_fold":[round(float(x),4) for x in real],
            "shuffle_per_fold":[round(float(x),4) for x in shuf],
            "real_signal_per_fold":[round(float(x),4) for x in rs],
            "mean_real_signal":round(float(np.nanmean(rs)),4),
            "n_folds_pos":int(np.nansum(rs>0)),
            "aa_seed_std":round(float(np.nanstd(seed_means)),5),
            "legs":[l1,l2,l3,l4],
            "verdict":"PASS" if all([l1,l2,l3,l4]) else "KILL"}

def synthetic(mode,seed=7):
    rng=np.random.default_rng(seed)
    dates=pd.bdate_range("2016-01-04","2026-05-07")
    tickers=[f"T{i:03d}" for i in range(60)]
    n=len(dates)*len(tickers)
    df=pd.DataFrame({"date":np.repeat(dates.strftime("%Y-%m-%d"),len(tickers)),
                     "ticker":np.tile(tickers,len(dates))})
    for c in FEATS: df[c]=rng.normal(size=n)
    noise=rng.normal(scale=1.0,size=n)
    if mode=="positive":
        sig=0.35*df["ROC20"].values+0.25*df["RANK60"].values
        df[LABEL]=sig+noise
    else:
        df[LABEL]=noise
    return df

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--control",choices=["positive","null"])
    ap.add_argument("--real",action="store_true")
    ap.add_argument("--confirm-211-merged",action="store_true")
    a=ap.parse_args()
    CORPUS_SHA256 = "870f68ebad5d2d87e2601f62310f34615d2d8d25df9d9cbf563629b13129bf7e"
    if a.real:
        if not a.confirm_211_merged: print("REFUSED: gated on model#211 merge"); sys.exit(2)
        import hashlib
        _cp="/Users/renhao/git/github/RenQuant/data/alpha158_291_fundamental_dataset.parquet"
        assert hashlib.sha256(open(_cp,"rb").read()).hexdigest()==CORPUS_SHA256, "corpus drifted from prereg pin"
        panel=pd.read_parquet(_cp)
        panel["date"]=pd.to_datetime(panel["date"]).dt.strftime("%Y-%m-%d")
        r=legs(panel,FEATS)
    else:
        r=legs(synthetic(a.control),FEATS)
    r["corpus_sha256"]=CORPUS_SHA256 if a.real else None
    r["fold_table"]=CUTS
    import hashlib as _h
    r["features_sha256"]=_h.sha256(json.dumps(FEATS).encode()).hexdigest()
    r["admissible_verdict"]=None   # null until review countersigns (model#213 duty)
    r["gate_arithmetic"]=r.pop("verdict")
    print(json.dumps(r,indent=1))
    if a.control=="positive": sys.exit(0 if r["gate_arithmetic"]=="PASS" else 1)
    if a.control=="null": sys.exit(0 if r["gate_arithmetic"]=="KILL" else 1)
