"""Diagnose the saved model on TestSet 02 without retraining or changing it."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dataset/predict_noise_snow/TestSet_02_error_analysis.xlsx"


def summary(g):
    e = g.signed_error_mm
    return pd.Series({
        "rows": len(g), "mae_mm": e.abs().mean(),
        "bias_mm": e.mean(), "rmse_mm": np.sqrt((e**2).mean()),
        "p95_mm": e.abs().quantile(.95), "max_mm": e.abs().max(),
        "over_10mm_pct": (e.abs() > 10).mean()*100,
        "zero_noise_baseline_mae_mm": g.target_total_noise_m.abs().mean()*1000,
        "true_noise_std_mm": g.target_total_noise_m.std()*1000,
        "pred_noise_std_mm": g.predicted_total_noise_m.std()*1000,
        "heave_std_mm": g.latent_heave_m.std()*1000,
        "sensor_error_std_mm": g.target_sensor_error_m.std()*1000,
        "error_heave_corr": e.corr(g.latent_heave_m),
    })


def main():
    a = joblib.load(ROOT / "python/models/total_noise_model.joblib")
    source = Path(a["source_file"])
    if not source.exists():
        source = ROOT / "dataset/GPT_ML_data/RoadSurf_Synthetic_Labeled_v1_resaved.xlsx"
    train = pd.read_excel(source, sheet_name=a["source_sheet"])
    train = train.loc[train.split.eq("train")].copy()
    d = pd.read_excel(ROOT / "dataset/predict_noise_snow/RoadSurf_Synthetic_TestSet_02_predicted.xlsx",
                      sheet_name=a["source_sheet"])
    np.testing.assert_allclose(d.predicted_total_noise_m,
                               a["model"].predict(d[a["feature_columns"]]), atol=1e-12)
    d["excel_row"] = np.arange(len(d)) + 2
    d["signed_error_mm"] = (d.predicted_total_noise_m - d.target_total_noise_m)*1000
    d["absolute_error_mm"] = d.signed_error_mm.abs()
    sessions = d.groupby(["run_id", "split", "scenario"], sort=False).apply(summary).reset_index()
    scenarios = d.groupby("scenario").apply(summary).reset_index()
    splits = d.groupby("split").apply(summary).reset_index()
    feature_rows = []
    for f in a["feature_columns"]:
        low, high = train[f].min(), train[f].max()
        outside = (d[f] < low) | (d[f] > high)
        feature_rows.append({"feature": f, "train_min": low, "train_max": high,
                             "test_min": d[f].min(), "test_max": d[f].max(),
                             "train_unique": train[f].nunique(), "test_unique": d[f].nunique(),
                             "outside_train_range_pct": outside.mean()*100,
                             "outside_mae_mm": d.loc[outside, "absolute_error_mm"].mean(),
                             "inside_mae_mm": d.loc[~outside, "absolute_error_mm"].mean()})
    features = pd.DataFrame(feature_rows)
    importance = pd.DataFrame({"feature": a["feature_columns"],
        "impurity_importance": a["model"].named_steps["regressor"].feature_importances_})
    # Diagnostic perturbation only: cross-feature relationships can be broken.
    rng = np.random.default_rng(42)
    baseline = d.absolute_error_mm.mean()
    permutation = []
    for f in a["feature_columns"]:
        changes = []
        for _ in range(3):
            x = d[a["feature_columns"]].copy()
            x[f] = rng.permutation(x[f].to_numpy())
            mae = np.abs(a["model"].predict(x)-d.target_total_noise_m).mean()*1000
            changes.append(mae-baseline)
        permutation.append({"feature": f, "shuffle_mae_increase_mm": np.mean(changes)})
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        pd.DataFrame([summary(d)]).to_excel(writer, sheet_name="overall", index=False)
        sessions.sort_values("mae_mm", ascending=False).to_excel(writer, sheet_name="sessions", index=False)
        scenarios.to_excel(writer, sheet_name="scenarios", index=False)
        splits.to_excel(writer, sheet_name="splits", index=False)
        features.to_excel(writer, sheet_name="feature_ranges", index=False)
        importance.merge(pd.DataFrame(permutation)).to_excel(writer, sheet_name="feature_dependence", index=False)
        d.nlargest(100, "absolute_error_mm").to_excel(writer, sheet_name="worst_100_rows", index=False)
        pd.DataFrame({"note": [f"Training comparison source: {source}",
            "Ground truth / latent columns used only for diagnosis, not prediction.",
            "Bias = predicted minus target; positive means snow height overestimated.",
            "Permutation is global across runs, 3 repeats; not a causal effect.",
            "Impurity importance can favor correlated run-specific predictors.",
            "No retraining or selection on this test set was performed."]}).to_excel(writer, sheet_name="notes", index=False)
    cols = ["mae_mm", "bias_mm", "p95_mm", "zero_noise_baseline_mae_mm", "error_heave_corr"]
    print("SCENARIOS\n", scenarios[["scenario"]+cols].round(3).to_string(index=False))
    print("WORST SESSIONS\n", sessions.sort_values("mae_mm", ascending=False).head(8).round(3).to_string(index=False))
    print("FEATURES\n", features.round(3).to_string(index=False))
    print("DEPENDENCE\n", importance.merge(pd.DataFrame(permutation)).round(4).to_string(index=False))
    print("OUTPUT", OUT)


if __name__ == "__main__":
    main()
