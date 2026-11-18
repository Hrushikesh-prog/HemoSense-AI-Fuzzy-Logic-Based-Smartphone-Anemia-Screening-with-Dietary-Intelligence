"""Main experiment: patient-level 5-fold CV of ANFIS vs baselines, ablations,
cross-region generalisation, and export of the deployed model (models/anfis.json).

Protocol (no information from a test fold is used anywhere):
  * one sample per participant; outer StratifiedKFold(5, seed 42) on region x anemic
  * inside each training fold: top-3 features by single-feature AUC; model fit;
    inner 5-fold out-of-fold scores -> Platt calibration + two thresholds:
      tau_sens85  = highest threshold reaching >= 85 % sensitivity (screening target)
      tau_youden  = threshold maximising sensitivity + specificity (used by the app)
  * pooled out-of-fold probabilities -> AUC (bootstrap 95 % CI), sens/spec (Wilson CI),
    Brier, ECE, DeLong test vs ANFIS.

Needs:  research/results/features.csv  (extract_features)
        research/results/live_sim_features.csv (live_path_sim)
Run:    python -m research.run_experiment
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from hemosense.anfis import ANFIS  # noqa: E402
from hemosense.features import FEATURES  # noqa: E402
from hemosense.labels import app_grade  # noqa: E402
from hemosense.mamdani import Mamdani  # noqa: E402
from hemosense.metrics import (auc_with_ci, brier, delong_test, ece, prop_ci,  # noqa: E402
                               screen_metrics, threshold_for_sensitivity)

RESULTS = os.path.join(ROOT, "research", "results")
FIG = os.path.join(RESULTS, "figures")
SEED = 42
APP_TAU = 0.5  # decision rule used by the app: calibrated probability >= 0.5 (chosen with the user)

VARIANTS = {  # name -> column prefix
    "expert_palpebral": "mask_raw",
    "expert_palpebral_fuzzycorr": "mask_fuzzy",
    "expert_union": "union",
    "live_pipeline": "live_sim",
    "haar_auto": "auto_raw",
    "haar_auto_fuzzycorr": "auto_fuzzy",
}


# ---------------------------------------------------------------- models
def single_auc(x, y):
    a = roc_auc_score(y, x)
    return max(a, 1 - a)


def select_univariate(X: pd.DataFrame, y, k: int = 3, cands=FEATURES) -> list[str]:
    """First protocol: top-k by single-feature AUC. Picks redundant redness features."""
    return sorted(cands, key=lambda f: -single_auc(X[f].values, y))[:k]


def select_greedy(X: pd.DataFrame, y, k: int = 3, cands=FEATURES) -> list[str]:
    """Redundancy-aware forward selection: add the feature that most improves the
    inner 5-fold AUC of a logistic model on the TRAINING data only."""
    from sklearn.model_selection import cross_val_predict
    chosen: list[str] = []
    while len(chosen) < k:
        best = None
        for c in cands:
            if c in chosen:
                continue
            cols = chosen + [c]
            s = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
                                  X[cols].values, y, method="decision_function",
                                  cv=StratifiedKFold(5, shuffle=True, random_state=SEED + 2))
            a = roc_auc_score(y, s)
            if best is None or a > best[0]:
                best = (a, c)
        chosen.append(best[1])
    return chosen


select_features = select_greedy


class AnfisModel:
    name = "ANFIS"

    def __init__(self, k: int = 3, n_terms: int = 3, cands=FEATURES, selector: str = "greedy",
                 train: bool = True):
        self.k, self.n_terms, self.cands, self.selector, self.train = k, n_terms, cands, selector, train

    def fit(self, X: pd.DataFrame, y):
        sel = select_greedy if self.selector == "greedy" else select_univariate
        self.feats = sel(X, y, self.k, self.cands)
        Xa = X[self.feats].values
        if not self.train:  # ablation: least-squares consequents only, no gradient training
            self.m = ANFIS(self.feats, n_terms=self.n_terms, seed=SEED).fit(Xa, y, epochs=1)
            return self
        tr, va = train_test_split(np.arange(len(y)), test_size=0.2, stratify=y, random_state=SEED)
        probe = ANFIS(self.feats, n_terms=self.n_terms, seed=SEED).fit(Xa[tr], y[tr], Xa[va], y[va])
        self.m = ANFIS(self.feats, n_terms=self.n_terms, seed=SEED).fit(Xa, y, epochs=max(probe.best_epoch, 20))
        return self

    def score(self, X):
        return self.m.logit(X[self.feats].values)


class MamdaniModel:
    name = "Mamdani"

    def fit(self, X, y):
        self.m = Mamdani().fit(X[list(Mamdani.features)].values, y)
        return self

    def score(self, X):
        return self.m.risk(X[list(Mamdani.features)].values)


class LogRegModel:
    name = "LogReg"

    def fit(self, X, y):
        self.m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(X[list(FEATURES)].values, y)
        return self

    def score(self, X):
        return self.m.decision_function(X[list(FEATURES)].values)


class RFModel:
    name = "RandomForest"

    def fit(self, X, y):
        self.m = RandomForestClassifier(n_estimators=300, min_samples_leaf=3, random_state=SEED, n_jobs=-1)
        self.m.fit(X[list(FEATURES)].values, y)
        return self

    def score(self, X):
        return self.m.predict_proba(X[list(FEATURES)].values)[:, 1]


class MajorityModel:
    name = "Majority"

    def fit(self, X, y):
        self.p = float(np.mean(y))
        return self

    def score(self, X):
        return np.full(len(X), self.p)


MODELS = {"ANFIS": AnfisModel, "Mamdani": MamdaniModel, "LogReg": LogRegModel,
          "RandomForest": RFModel, "Majority": MajorityModel}


# ---------------------------------------------------------------- calibration / thresholds
def youden(y, p) -> float:
    fpr, tpr, thr = roc_curve(y, p)
    return float(thr[np.argmax(tpr - fpr)])


def calibrate(factory, X: pd.DataFrame, y) -> dict:
    """Inner 5-fold OOF scores on the training data -> Platt (a, b) and thresholds."""
    oof = np.zeros(len(y))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED + 1).split(X, y):
        oof[te] = factory().fit(X.iloc[tr], y[tr]).score(X.iloc[te])
    if np.std(oof) < 1e-12:
        return {"a": 0.0, "b": float(np.log(y.mean() / (1 - y.mean()))), "tau_sens85": 0.5, "tau_youden": 0.5}
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(oof.reshape(-1, 1), y)
    a, b = float(lr.coef_[0, 0]), float(lr.intercept_[0])
    p = 1 / (1 + np.exp(-(a * oof + b)))
    return {"a": a, "b": b, "tau_sens85": threshold_for_sensitivity(y, p, 0.85), "tau_youden": youden(y, p)}


def cross_validate(df: pd.DataFrame, prefix: str, factory, target: str = "anemic", folds=None) -> pd.DataFrame:
    X = df[[f"{prefix}__{f}" for f in FEATURES]].copy()
    X.columns = list(FEATURES)
    y = df[target].values.astype(int)
    out = pd.DataFrame({"pid": df.pid.values, "y": y, "p": np.nan, "tau_sens85": np.nan,
                        "tau_youden": np.nan, "fold": -1})
    out["feats"] = ""
    for k, (tr, te) in enumerate(folds):
        cal = calibrate(factory, X.iloc[tr], y[tr])
        m = factory().fit(X.iloc[tr], y[tr])
        s = m.score(X.iloc[te])
        out.loc[te, "p"] = 1 / (1 + np.exp(-(cal["a"] * s + cal["b"])))
        out.loc[te, "tau_sens85"] = cal["tau_sens85"]
        out.loc[te, "tau_youden"] = cal["tau_youden"]
        out.loc[te, "fold"] = k
        out.loc[te, "feats"] = ",".join(getattr(m, "feats", []))
    return out


def summarise(o: pd.DataFrame) -> dict:
    y, p = o.y.values, o.p.values
    r = {"n": int(len(y)), "n_pos": int(y.sum()), **auc_with_ci(y, p), "brier": brier(y, p), "ece": ece(y, p)}
    o = o.assign(tau_050=APP_TAU)
    for t in ("tau_sens85", "tau_youden", "tau_050"):
        m = screen_metrics(y, p, o[t].values)
        c = m["confusion"]
        m["sensitivity_ci95"] = prop_ci(c["tp"], c["tp"] + c["fn"])
        m["specificity_ci95"] = prop_ci(c["tn"], c["tn"] + c["fp"])
        r[t] = m
    return r


def make_folds(df: pd.DataFrame, seed: int = SEED):
    strata = (df.region + "_" + df.anemic.astype(str)).values
    return list(StratifiedKFold(5, shuffle=True, random_state=seed).split(df, strata))


# ---------------------------------------------------------------- main
def main() -> None:
    t0 = time.time()
    os.makedirs(FIG, exist_ok=True)
    feats = pd.read_csv(os.path.join(RESULTS, "features.csv"))
    live = pd.read_csv(os.path.join(RESULTS, "live_sim_features.csv"))
    keep = ["pid"] + [c for c in live.columns if c.startswith(("live_sim__", "union__"))] + ["status"]
    df = feats.merge(live[keep], on="pid", how="left")
    df = df[df.status == "ok"].reset_index(drop=True)  # live-path failures are reported separately
    print(f"{len(df)} participants with every variant ({int(df.anemic.sum())} anemic)")
    folds = make_folds(df)
    pd.DataFrame([(df.pid[i], k) for k, (_, te) in enumerate(folds) for i in te],
                 columns=["pid", "fold"]).to_csv(os.path.join(RESULTS, "folds.csv"), index=False)

    report: dict = {"n_participants": int(len(df)), "n_anemic": int(df.anemic.sum()),
                    "n_mod_sev": int(df.mod_sev.sum()),
                    "by_region": {r: {"n": int(len(g)), "anemic": int(g.anemic.sum()), "mod_sev": int(g.mod_sev.sum())}
                                  for r, g in df.groupby("region")},
                    "main": {}, "ablations": {}, "cross_region": {}, "delong_vs_anfis": {}}

    # 1) main comparison on the two headline settings
    preds = {}
    for vname in ("expert_palpebral", "live_pipeline"):
        report["main"][vname] = {}
        for mname, M in MODELS.items():
            o = cross_validate(df, VARIANTS[vname], M, folds=folds)
            preds[(vname, mname)] = o
            o.to_csv(os.path.join(RESULTS, f"oof_{vname}_{mname}.csv"), index=False)
            report["main"][vname][mname] = summarise(o)
            if mname == "ANFIS":
                report["main"][vname][mname]["selected_features_per_fold"] = o.groupby("fold").feats.first().tolist()
            print(f"  {vname:18s} {mname:12s} AUC {report['main'][vname][mname]['auc']:.3f}", flush=True)
        report["delong_vs_anfis"][vname] = {
            m: delong_test(preds[(vname, 'ANFIS')].y.values, preds[(vname, 'ANFIS')].p.values, preds[(vname, m)].p.values)
            for m in MODELS if m not in ("ANFIS", "Majority")}
        # per-region breakdown of ANFIS
        o = preds[(vname, "ANFIS")].merge(df[["pid", "region"]], on="pid")
        report["main"][vname]["ANFIS"]["by_region"] = {
            r: {**auc_with_ci(g.y.values, g.p.values),
                **{k: v for k, v in screen_metrics(g.y.values, g.p.values, APP_TAU).items()
                   if k in ("sensitivity", "specificity")}}
            for r, g in o.groupby("region")}

    # 2) ablations (ANFIS AUC)
    ab = report["ablations"]
    ab["pipeline_variant"] = {v: summarise(cross_validate(df, p, AnfisModel, folds=folds))["auc"]
                              for v, p in VARIANTS.items()}
    ab["n_inputs_live"] = {k: summarise(cross_validate(df, "live_sim", lambda k=k: AnfisModel(k=k), folds=folds))["auc"]
                           for k in (2, 3, 4)}
    ab["feature_selection_live"] = {
        "univariate_top3 (first protocol)": summarise(cross_validate(
            df, "live_sim", lambda: AnfisModel(selector="univariate"), folds=folds))["auc"],
        "greedy_forward (final protocol)": report["main"]["live_pipeline"]["ANFIS"]["auc"]}
    ab["gradient_training_live"] = {
        "lse_init_only": summarise(cross_validate(df, "live_sim", lambda: AnfisModel(train=False), folds=folds))["auc"],
        "lse_plus_adam (final)": report["main"]["live_pipeline"]["ANFIS"]["auc"]}
    ab["n_terms_live"] = {t: summarise(cross_validate(df, "live_sim", lambda t=t: AnfisModel(n_terms=t), folds=folds))["auc"]
                          for t in (2, 3)}
    reps = {}
    for mname in ("ANFIS", "LogReg", "RandomForest", "Mamdani"):
        aucs = [summarise(cross_validate(df, "live_sim", MODELS[mname], folds=make_folds(df, s)))["auc"]
                for s in range(5)]
        reps[mname] = {"mean": float(np.mean(aucs)), "sd": float(np.std(aucs)), "aucs": aucs}
    ab["repeated_cv_live_5x5"] = reps
    print("  ablations done", flush=True)

    # 3) cross-region generalisation (train on one country, test on the other)
    for vname in ("expert_palpebral", "live_pipeline"):
        pre = VARIANTS[vname]
        X = df[[f"{pre}__{f}" for f in FEATURES]].copy()
        X.columns = list(FEATURES)
        res = {}
        for src, dst in (("India", "Italy"), ("Italy", "India")):
            tr, te = (df.region == src).values, (df.region == dst).values
            y = df.anemic.values
            for mname in ("ANFIS", "LogReg", "Mamdani"):
                cal = calibrate(MODELS[mname], X[tr].reset_index(drop=True), y[tr])
                m = MODELS[mname]().fit(X[tr].reset_index(drop=True), y[tr])
                p = 1 / (1 + np.exp(-(cal["a"] * m.score(X[te]) + cal["b"])))
                sm = screen_metrics(y[te], p, APP_TAU)
                res[f"{src}->{dst}:{mname}"] = {**auc_with_ci(y[te], p), "sensitivity": sm["sensitivity"],
                                                "specificity": sm["specificity"]}
        report["cross_region"][vname] = res

    # 4) severity: ANFIS for moderate-or-severe, combined 3-grade output (live pipeline)
    o_a = preds[("live_pipeline", "ANFIS")]
    o_s = cross_validate(df, "live_sim", AnfisModel, target="mod_sev", folds=folds)
    report["severity_live"] = {"mod_sev_model": summarise(o_s)}
    truth = df.who_grade.map(app_grade).values
    pred = np.where(o_a.p.values < APP_TAU, "Normal",
                    np.where(o_s.p.values >= APP_TAU, "Moderate-to-Severe", "Mild"))
    labels = ["Normal", "Mild", "Moderate-to-Severe"]
    cm = pd.crosstab(pd.Categorical(truth, labels), pd.Categorical(pred, labels), dropna=False)
    report["severity_live"]["three_grade_confusion_rows_true_cols_pred"] = cm.values.tolist()
    report["severity_live"]["three_grade_accuracy"] = float((truth == pred).mean())
    report["severity_live"]["moderate_severe_flagged_as_anemic"] = float(
        (pred[truth == "Moderate-to-Severe"] != "Normal").mean())

    # 5) deployed model: ANFIS on live-pipeline features, all participants
    export_model(df, report)
    with open(os.path.join(RESULTS, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=float)
    make_figures(df, preds, report)
    print(f"done in {time.time() - t0:.0f}s -> research/results/metrics.json")


def export_model(df: pd.DataFrame, report: dict) -> None:
    X = df[[f"live_sim__{f}" for f in FEATURES]].copy()
    X.columns = list(FEATURES)
    out = {"version": "1.0.0", "trained_on": "Eyes-defy-anemia (India + Italy), live-pipeline features",
           "n_train": int(len(df)), "created": time.strftime("%Y-%m-%d"), "models": {}}
    for target in ("anemic", "mod_sev"):
        y = df[target].values.astype(int)
        cal = calibrate(AnfisModel, X, y)
        m = AnfisModel().fit(X, y)
        m.m.platt_a, m.m.platt_b = cal["a"], cal["b"]
        m.m.tau = APP_TAU
        out["models"][target] = m.m.to_dict(decision_rule="p >= 0.5", tau_youden=cal["tau_youden"],
                                            tau_sens85=cal["tau_sens85"],
                                            n_active_rules=int(m.m.active.sum()), n_params=m.m.n_params)
    out["cv_live_pipeline"] = {k: report["main"]["live_pipeline"]["ANFIS"][k] for k in ("auc", "auc_ci95")}
    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    with open(os.path.join(ROOT, "models", "anfis.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    report["deployed_model"] = {t: {k: out["models"][t][k] for k in ("features", "n_active_rules", "n_params",
                                                                     "tau_youden", "tau_sens85")}
                                for t in out["models"]}


def make_figures(df: pd.DataFrame, preds: dict, report: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for vname in ("expert_palpebral", "live_pipeline"):
        fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=200)
        for mname in ("ANFIS", "Mamdani", "LogReg", "RandomForest"):
            o = preds[(vname, mname)]
            fpr, tpr, _ = roc_curve(o.y, o.p)
            ax.plot(fpr, tpr, lw=1.6 if mname == "ANFIS" else 1.0,
                    label=f"{mname} (AUC {report['main'][vname][mname]['auc']:.2f})")
        ax.plot([0, 1], [0, 1], "k:", lw=0.8)
        ax.set_xlabel("1 - specificity"); ax.set_ylabel("Sensitivity")
        ax.set_title(f"ROC, 5-fold CV ({vname.replace('_', ' ')})", fontsize=9)
        ax.legend(fontsize=7, loc="lower right"); fig.tight_layout()
        fig.savefig(os.path.join(FIG, f"roc_{vname}.png")); plt.close(fig)

    with open(os.path.join(ROOT, "models", "anfis.json"), encoding="utf-8") as f:
        mdl = ANFIS.from_dict(json.load(f)["models"]["anemic"])
    fig, axes = plt.subplots(1, len(mdl.features), figsize=(3.2 * len(mdl.features), 2.6), dpi=200)
    for k, (ax, feat) in enumerate(zip(np.atleast_1d(axes), mdl.features)):
        xs = np.linspace(-3, 3, 300)
        raw = xs * mdl.std_[k] + mdl.mean_[k]
        for j, term in enumerate(("Low", "Medium", "High")):
            ax.plot(raw, np.exp(-0.5 * ((xs - mdl.centres[k, j]) / mdl.widths[k, j]) ** 2), label=term)
        ax.set_title(f"{feat}", fontsize=9); ax.set_ylim(0, 1.05)
    np.atleast_1d(axes)[0].legend(fontsize=7)
    fig.suptitle("Learned ANFIS membership functions (deployed model)", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "anfis_membership.png")); plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(11, 2.8), dpi=200)
    for ax, f in zip(axes, FEATURES):
        col = f"live_sim__{f}"
        ax.boxplot([df.loc[df.anemic == 0, col], df.loc[df.anemic == 1, col]], tick_labels=["Not anemic", "Anemic"])
        ax.set_title(f"{f} (AUC {single_auc(df[col].values, df.anemic.values):.2f})", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "features_by_class.png")); plt.close(fig)

    o = preds[("live_pipeline", "ANFIS")]
    bins = np.linspace(0, 1, 6)
    idx = np.clip(np.digitize(o.p, bins) - 1, 0, 4)
    fig, ax = plt.subplots(figsize=(3.6, 3.6), dpi=200)
    xs = [o.p[idx == b].mean() for b in range(5) if (idx == b).any()]
    ys = [o.y[idx == b].mean() for b in range(5) if (idx == b).any()]
    ax.plot([0, 1], [0, 1], "k:", lw=0.8); ax.plot(xs, ys, "o-")
    ax.set_xlabel("Predicted probability"); ax.set_ylabel("Observed anemia rate")
    ax.set_title("Calibration, ANFIS (live pipeline)", fontsize=9); fig.tight_layout()
    fig.savefig(os.path.join(FIG, "calibration_anfis_live.png")); plt.close(fig)


if __name__ == "__main__":
    main()
