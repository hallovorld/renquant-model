"""Prove the WF driver's fit path IS the served recipe: refit full-sample with
the driver's exact code path and compare predictions to the SERVED artifact's
booster on the same rows. READ-ONLY."""
import importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd, xgboost as xgb

RQ = Path("/Users/renhao/git/github/RenQuant"); DATA = RQ/"data"
SERVED = RQ/"backtesting/renquant_104/artifacts/shadow/panel-clf.top-decile.fwd60.json"
spec = importlib.util.spec_from_file_location("_r", "/Users/renhao/git/github/renquant-model/scripts/train_topdecile_clf_shadow.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
from renquant_model_gbdt.panel_data import load_panel, build_normalization
from renquant_model_gbdt.panel_trainer import panel_training_matrix

train, feat_cols, label = load_panel(DATA, label=r.LABEL)
train = train.dropna(subset=[r.LABEL])
y = r.top_decile_label(train)
mu, sd, kind, lo, hi = build_normalization(train, feat_cols, DATA)
X = panel_training_matrix(train, feat_cols, mu, sd, kind)
order = np.argsort(train["date"].values, kind="stable")
b = xgb.train(dict(r.CLF_PARAMS, seed=42),
              xgb.DMatrix(X.values[order].astype(np.float64), label=y.values[order]),
              num_boost_round=r.N_ROUNDS)

a = json.loads(SERVED.read_text())
sb = xgb.Booster(); sb.load_model(bytearray(a["booster_raw_json"].encode()))
assert list(a["feature_cols"]) == list(feat_cols), "feature_cols differ"
np.testing.assert_allclose(np.asarray(a["feature_means"],float), mu, rtol=0, atol=1e-12)
np.testing.assert_allclose(np.asarray(a["feature_stds"],float), sd, rtol=0, atol=1e-12)
assert list(a["feature_norm_kind"]) == list(kind), "norm kind differs"

samp = X.values[:20000].astype(np.float64)
d = xgb.DMatrix(samp)
p_new, p_served = b.predict(d), sb.predict(d)
md = float(np.max(np.abs(p_new - p_served)))
print(json.dumps({
  "served_effective_train_cutoff_date": a["effective_train_cutoff_date"],
  "refit_effective_train_cutoff_date": r.effective_train_cutoff(train),
  "feature_cols_identical": True, "normalization_identical": True,
  "max_abs_pred_diff_20k_rows": md,
  "bitwise_booster_json_identical": bytes(b.save_raw(raw_format="json")).decode() == a["booster_raw_json"],
}, indent=2))
assert md < 1e-9, f"driver fit path does NOT reproduce the served recipe (max diff {md})"
print("[OK] driver fit path reproduces the SERVED artifact exactly")
