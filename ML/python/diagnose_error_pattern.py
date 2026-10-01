"""Explain session blocks, snow conditions and signed-error components; no training."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dataset/predict_noise_snow/TestSet_02_error_pattern.xlsx"


def main():
    a = joblib.load(ROOT / "python/models/total_noise_model.joblib")
    d = pd.read_excel(ROOT / "dataset/predict_noise_snow/RoadSurf_Synthetic_TestSet_02_predicted.xlsx",
                      sheet_name=a["source_sheet"])
    np.testing.assert_allclose(d.predicted_total_noise_m,
                              a["model"].predict(d[a["feature_columns"]]), atol=1e-12)
    d["excel_row"] = np.arange(len(d)) + 2
    d["signed_error_mm"] = (d.predicted_total_noise_m - d.target_total_noise_m)*1000
    rows = []
    for run, g in d.groupby("run_id", sort=False):
        e = g.signed_error_mm.to_numpy()
        y = g.target_total_noise_m.to_numpy()*1000
        p = g.predicted_total_noise_m.to_numpy()*1000
        snow = g.target_snow_depth_m.to_numpy()
        kind = "no_snow" if np.max(abs(snow)) < 1e-10 else (
            "constant_snow" if np.ptp(snow) < 1e-10 else "varying_snow")
        mse = np.mean(e**2)
        rows.append({"run_id": run, "scenario": g.scenario.iloc[0], "split": g.split.iloc[0],
                     "excel_start": g.excel_row.iloc[0], "excel_end": g.excel_row.iloc[-1],
                     "snow_kind": kind, "snow_min_mm": snow.min()*1000, "snow_max_mm": snow.max()*1000,
                     "mae_mm": np.mean(abs(e)), "bias_mm": e.mean(),
                     "rmse_mm": np.sqrt(mse), "error_std_mm": e.std(),
                     "bias_share_of_mse_pct": e.mean()**2/mse*100,
                     "p95_mm": np.quantile(abs(e), .95), "max_mm": np.max(abs(e)),
                     "prediction_true_corr": np.corrcoef(y,p)[0,1],
                     "prediction_gain": np.sum((p-p.mean())*(y-y.mean()))/np.sum((y-y.mean())**2),
                     "noise_std_mm": y.std(), "prediction_std_mm": p.std(),
                     "heave_std_mm": g.latent_heave_m.std(ddof=0)*1000,
                     "sensor_std_mm": g.target_sensor_error_m.std(ddof=0)*1000})
        d.loc[g.index, "snow_kind"] = kind
    sessions = pd.DataFrame(rows)
    groups = []
    for (scenario, kind), g in d.groupby(["scenario", "snow_kind"]):
        groups.append({"scenario": scenario, "snow_kind": kind, "rows": len(g),
                       "sessions": g.run_id.nunique(), "mae_mm": g.signed_error_mm.abs().mean(),
                       "bias_mm": g.signed_error_mm.mean()})
    # Identity verification: with zero snow, measured distance - clearance IS true noise.
    z = d.loc[d.snow_kind.eq("no_snow")]
    residual = np.max(abs(z.distance_measured_m - 3.1715 - z.target_total_noise_m))
    assert residual < 1e-12
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        sessions.to_excel(writer, sheet_name="session_decomposition", index=False)
        pd.DataFrame(groups).to_excel(writer, sheet_name="scenario_snow", index=False)
        d.loc[d.run_id.isin(["test2_run_09", "test2_run_17", "test2_run_24", "test2_run_29"])].to_excel(
            writer, sheet_name="key_sessions", index=False)
        pd.DataFrame({"note": [
            "Bias sign: predicted minus ground truth; negative means snow height underestimated.",
            "MSE = bias^2 + population error variance; decomposition is diagnostic, not a deployable correction.",
            "Prediction gain is descriptive regression slope of prediction against true noise, not causal.",
            "Snow kind uses ground truth for diagnosis only. It is not an input feature.",
            "Rows concatenate separate sessions; each contains 600 samples and 60 seconds at 10 Hz.",
            "No model, prediction workbook or chart was changed."]}).to_excel(writer, sheet_name="notes", index=False)
    print(sessions[["run_id", "scenario", "snow_kind", "mae_mm", "bias_mm", "bias_share_of_mse_pct", "prediction_gain"]].round(3).to_string(index=False))
    print("SCENARIO/SNOW\n", pd.DataFrame(groups).round(3).to_string(index=False))
    print("Verified no-snow distance identity residual:", residual)
    print(OUT)


if __name__ == "__main__":
    main()
