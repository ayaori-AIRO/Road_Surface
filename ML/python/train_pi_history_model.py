"""Retrain the selected 1s history model without loading PC joblib artifacts."""
import argparse
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
from threadpoolctl import threadpool_limits

import train_total_noise_model as training
from compare_accel_history import make_features, check_causality, score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=training.DEFAULT_DATASET)
    parser.add_argument("--model", type=Path, default=Path(__file__).parent / "models/total_noise_model_accel_history_complete_pi.joblib")
    args = parser.parse_args()
    versions = {"numpy": np.__version__, "scipy": scipy.__version__,
                "scikit-learn": sklearn.__version__, "pandas": pd.__version__,
                "joblib": joblib.__version__}
    expected = {"numpy": "1.26.4", "scipy": "1.13.1", "scikit-learn": "1.6.1",
                "pandas": "2.2.3", "joblib": "1.5.3"}
    if versions != expected:
        parser.error(f"Install requirements-pi-training.txt first. Actual versions: {versions}")
    _, sheet, dropped = training.load_training_data(args.data)
    if dropped:
        raise ValueError("Invalid targets; preserve all rows when computing history")
    data = pd.read_excel(args.data, sheet_name=sheet)
    data["split"] = data["split"].astype("string").str.strip().str.lower()
    if not np.isfinite(data[training.TARGET_COLUMN].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite targets")
    check_causality(data)
    x = make_features(data, 1)
    ready = data.groupby("run_id", sort=False).cumcount() >= 10
    train_mask = data.split.eq("train") & ready
    history_columns = [c for c in x if c not in training.FEATURE_COLUMNS]
    if x.loc[train_mask, history_columns].isna().any().any():
        raise ValueError("Incomplete training history")
    model = training.build_candidates()["HistGradientBoosting"]
    with threadpool_limits(limits=1):
        model.fit(x.loc[train_mask], data.loc[train_mask, training.TARGET_COLUMN])
        metrics = {}
        for split in ("train", "validation", "test", "ood_test"):
            mask = data.split.eq(split) & ready
            metrics[split] = score(data.loc[mask, training.TARGET_COLUMN], model.predict(x.loc[mask]))
        metadata = {"model_type": "HistGradientBoosting_1s", "history_seconds": 1,
                    "feature_columns": list(x.columns), "base_feature_columns": training.FEATURE_COLUMNS,
                    "source_sheet": sheet, "source_file": str(args.data.resolve()),
                    "target_column": training.TARGET_COLUMN, "sklearn_version": sklearn.__version__,
                    "package_versions": versions, "python_version": platform.python_version(),
                    "training_rows": int(train_mask.sum()), "metrics": metrics,
                    "selection": "Retrain previously selected HistGradientBoosting_1s; no new model selection",
                    "history_recipe": "make_features in compare_accel_history.py; 10 Hz; reset per run",
                    "warmup_policy": "Require 11 samples before inference", "limitation": training.LIMITATION}
        args.model.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": model, **metadata}, args.model)
        loaded = joblib.load(args.model)
        sample = x.loc[ready].iloc[:20]
        np.testing.assert_allclose(loaded["model"].predict(sample), model.predict(sample), rtol=0, atol=0)
    args.model.with_suffix(".metrics.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print("Saved and reload verified:", args.model.resolve())


if __name__ == "__main__":
    main()
