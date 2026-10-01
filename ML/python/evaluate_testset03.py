"""Evaluate frozen models on TestSet 03; no fitting or model selection."""
import hashlib
import joblib
import numpy as np
import pandas as pd
import compare_accel_history as history

ROOT = history.ROOT
SOURCE = ROOT / "dataset/GPT_ML_data/RoadSurf_Synthetic_TestSet_03.xlsx"
OUTDIR = ROOT / "dataset/predict_noise_snow"


def main():
    paths = {
        "baseline": ROOT / "python/models/total_noise_model.joblib",
        "history_imputed": ROOT / "python/models/total_noise_model_accel_history.joblib",
        "history_complete": ROOT / "python/models/total_noise_model_accel_history_complete.joblib",
    }
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    artifacts = {name: joblib.load(path) for name, path in paths.items()}
    with pd.ExcelFile(SOURCE) as book:
        sheet = next(s for s in book.sheet_names if "target_total_noise_m" in
                     pd.read_excel(book, sheet_name=s, nrows=0).columns)
        data = pd.read_excel(book, sheet_name=sheet)
    if not np.isfinite(data[["target_total_noise_m", "target_snow_depth_m"]]).all().all():
        raise ValueError("Invalid targets")
    elapsed_samples = data.groupby("run_id", sort=False).cumcount()
    predictions = {}
    rows, sessions, scenarios, overlaps = [], [], [], []
    min_ready = max(a.get("history_seconds", 0) for a in artifacts.values())*10
    masks = {"common_ready": elapsed_samples >= min_ready,
             "common_after_5s": elapsed_samples >= max(50, min_ready)}
    for name, artifact in artifacts.items():
        seconds = artifact.get("history_seconds", 0)
        x = history.make_features(data, seconds)
        ready = elapsed_samples >= (seconds*10 if name == "history_complete" else 0)
        predicted = np.full(len(data), np.nan)
        predicted[ready] = artifact["model"].predict(x.loc[ready, artifact["feature_columns"]])
        predictions[name] = predicted
        for period, mask in masks.items():
            rows.append({"model": name, "period": period,
                         **history.score(data.loc[mask, "target_total_noise_m"], predicted[mask])})
        for run, g in data.loc[masks["common_after_5s"]].groupby("run_id", sort=False):
            sessions.append({"model": name, "run_id": run, "scenario": g.scenario.iloc[0],
                             **history.score(g.target_total_noise_m, predicted[g.index])})
        for scenario, g in data.loc[masks["common_after_5s"]].groupby("scenario"):
            scenarios.append({"model": name, "scenario": scenario,
                              **history.score(g.target_total_noise_m, predicted[g.index])})
        if name != "baseline":
            history.TEST_PATH = SOURCE
            history.OUTPUT = OUTDIR / f"RoadSurf_Synthetic_TestSet_03_predicted_{name}.xlsx"
            history.write_predictions(data, sheet, predicted)
            saved = pd.read_excel(history.OUTPUT, sheet_name=sheet)
            np.testing.assert_allclose(saved.predicted_total_noise_m, predicted, atol=1e-12)
            np.testing.assert_allclose(saved.predicted_snow_height_m,
                                       3.1715-(data.distance_measured_m-predicted), atol=1e-12)
            for pred, target, error in [("predicted_total_noise_m", "target_total_noise_m", "total_noise_absolute_error_m"),
                                       ("predicted_snow_height_m", "target_snow_depth_m", "snow_height_absolute_error_m")]:
                np.testing.assert_allclose(saved[error], abs(saved[pred]-saved[target]), atol=1e-12)
            assert saved.loc[~ready, saved.columns[-4:]].isna().all().all()

    # Exact-row checks establish that this is not merely a renamed prior workbook.
    columns = history.BASE_FEATURES+["target_total_noise_m", "target_snow_depth_m"]
    new_hash = pd.util.hash_pandas_object(data[columns], index=False)
    for file in ("RoadSurf_Synthetic_Labeled_v1_resaved.xlsx", "RoadSurf_Synthetic_TestSet_02.xlsx"):
        old = pd.read_excel(ROOT / "dataset/GPT_ML_data" / file, sheet_name=sheet)
        old_hash = pd.util.hash_pandas_object(old[columns], index=False)
        overlaps.append({"source": file, "exact_matching_rows": int(new_hash.isin(old_hash).sum())})
    session_df = pd.DataFrame(sessions)
    paired = session_df.pivot(index="run_id", columns="model", values="mae_mm")
    paired["complete_minus_imputed_mm"] = paired.history_complete-paired.history_imputed
    # Paired session bootstrap, not a row bootstrap: nearby rows are dependent.
    delta = paired.complete_minus_imputed_mm.to_numpy()
    rng = np.random.default_rng(42)
    means = rng.choice(delta, size=(10000,len(delta)), replace=True).mean(axis=1)
    interval = np.quantile(means, [.025,.975])
    report = OUTDIR / "TestSet_03_frozen_model_comparison.xlsx"
    with pd.ExcelWriter(report, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="metrics", index=False)
        session_df.to_excel(writer, sheet_name="sessions", index=False)
        paired.reset_index().to_excel(writer, sheet_name="paired_sessions", index=False)
        pd.DataFrame(scenarios).to_excel(writer, sheet_name="scenarios", index=False)
        pd.DataFrame(overlaps).to_excel(writer, sheet_name="overlap_checks", index=False)
        pd.DataFrame({"note": [
            "Frozen models; no fitting or selection on TestSet 03.",
            "Both models compared on identical rows, with session warm-up excluded.",
            "Model difference includes retraining after warm-up exclusion; this is not a multi-seed study.",
            "Session bootstrap interval assumes sessions are independent; same synthetic generator limits scope.",
            f"Paired session mean MAE delta complete-imputed (mm): {delta.mean()}",
            f"Paired bootstrap 95% interval (mm): {interval.tolist()}",
        ]}).to_excel(writer, sheet_name="notes", index=False)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest()==hashes[name] for name,path in paths.items())
    print(pd.DataFrame(rows).round(4).to_string(index=False))
    print("Improved sessions:",int((delta<0).sum()),"/",len(delta))
    print("Mean paired delta and bootstrap interval (mm):",delta.mean(),interval)
    print("Overlaps:",overlaps)
    print(pd.DataFrame(scenarios)[["model","scenario","mae_mm"]].round(3).to_string(index=False))
    print("Report:",report)
    print("Verified output values and unchanged model hashes.")


if __name__ == "__main__":
    main()
