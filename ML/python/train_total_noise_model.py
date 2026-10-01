"""피쳐 10개로 여러 모델을 학습하고 검증 MAE가 가장 낮은 모델을 저장한다.

실행: python ML/python/train_total_noise_model.py
필요 패키지: pandas openpyxl numpy scikit-learn joblib

target_total_noise_m은 정답 y로만 사용하며 입력 X에는 포함하지 않는다.
"""

from __future__ import annotations

import argparse
import json
from time import perf_counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline


ML_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = (
    ML_DIR / "dataset" / "GPT_ML_data" / "RoadSurf_Synthetic_Labeled_v1_resaved.xlsx"
)
DEFAULT_MODEL = ML_DIR / "python" / "models" / "total_noise_model.joblib"
REFERENCE_DISTANCE_M = 3.1715
TARGET_COLUMN = "target_total_noise_m"
FEATURE_COLUMNS = [
    "distance_measured_m",
    "speed_kmh",
    "accel_x_g",
    "accel_y_g",
    "accel_z_g",
    "gyro_x_dps",
    "gyro_y_dps",
    "gyro_z_dps",
    "temperature_c",
    "humidity_pct",
]
LIMITATION = (
    "Metrics evaluate ground truth noise prediction on synthetic data. "
    "Performance on real measurements has not been evaluated."
)


def load_training_data(path: Path) -> tuple[pd.DataFrame, str, int]:
    """입력 피쳐, 정답, split을 읽는다. 첫 시트는 설명이므로 자동 탐색한다."""
    required = set(FEATURE_COLUMNS + [TARGET_COLUMN, "split"])
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        candidates = [
            sheet
            for sheet in workbook.sheet_names
            if required.issubset(pd.read_excel(workbook, sheet_name=sheet, nrows=0).columns)
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Expected exactly one sheet containing the required features, target and split; "
                f"found {candidates}"
            )
        sheet = candidates[0]
        data = pd.read_excel(
            workbook, sheet_name=sheet, usecols=FEATURE_COLUMNS + [TARGET_COLUMN, "split"]
        )

    numeric_columns = FEATURE_COLUMNS + [TARGET_COLUMN]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data[numeric_columns] = data[numeric_columns].replace([np.inf, -np.inf], np.nan)
    # 정답이 없는 행만 제외한다. 입력 결측치는 학습셋 중앙값으로 처리한다.
    invalid_target_rows = int(data[TARGET_COLUMN].isna().sum())
    data = data.dropna(subset=[TARGET_COLUMN]).copy()
    data["split"] = data["split"].astype("string").str.strip().str.lower()
    allowed = {"train", "validation", "test", "ood_test"}
    if not data["split"].isin(allowed).all():
        raise ValueError("Missing or unsupported split labels in source data")
    for split in sorted(allowed):
        if int(data["split"].eq(split).sum()) < 2:
            raise ValueError(f"At least two valid rows required for split={split}")
    return data, sheet, invalid_target_rows


def build_candidates() -> dict[str, Pipeline]:
    """고정된 후보들을 비교하며 전처리는 학습 데이터에서만 학습한다."""
    estimators = {
        "DummyMedian": (DummyRegressor(strategy="median"), False),
        "LinearRegression": (LinearRegression(), True),
        "Ridge": (Ridge(alpha=1.0), True),
        "KNeighbors": (KNeighborsRegressor(n_neighbors=15, weights="distance", n_jobs=-1), True),
        "SVR_RBF": (SVR(C=0.1, epsilon=0.001, gamma="scale"), True),
        "RandomForest": (RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                              random_state=42, n_jobs=-1), False),
        "ExtraTrees": (ExtraTreesRegressor(n_estimators=300, min_samples_leaf=2,
                                          random_state=42, n_jobs=-1), False),
        "HistGradientBoosting": (HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
            l2_regularization=1.0, early_stopping=False, random_state=42), False),
    }
    candidates = {}
    for name, (regressor, scale) in estimators.items():
        steps = [("imputer", SimpleImputer(strategy="median"))]
        if scale:
            steps.append(("scaler", StandardScaler()))
        steps.append(("regressor", regressor))
        candidates[name] = Pipeline(steps)
    return candidates


def evaluate(model: Pipeline, x: pd.DataFrame, y: pd.Series) -> dict:
    prediction = model.predict(x)
    return {
        "rows": len(y),
        "mae_m": float(mean_absolute_error(y, prediction)),
        "rmse_m": float(np.sqrt(mean_squared_error(y, prediction))),
        "r2": float(r2_score(y, prediction)),
    }


def train(dataset_path: Path, model_path: Path) -> dict:
    data, sheet, dropped_rows = load_training_data(dataset_path)
    x = data.loc[:, FEATURE_COLUMNS]
    # Ground truth 노이즈는 정답으로만 사용한다. 부호와 단위를 그대로 유지한다.
    y = data[TARGET_COLUMN]
    train_mask = data["split"].eq("train")
    train_x = x.loc[train_mask]
    empty_columns = train_x.columns[train_x.isna().all()].tolist()
    if empty_columns:
        raise ValueError(f"Training features entirely missing: {empty_columns}")
    if train_x["distance_measured_m"].nunique() < 2:
        raise ValueError("Training distances must have at least two distinct values")

    candidates = build_candidates()
    comparison = []
    valid_mask = data["split"].eq("validation")
    for name, candidate in candidates.items():
        start = perf_counter()
        candidate.fit(train_x, y.loc[train_mask])
        fit_seconds = perf_counter() - start
        validation = evaluate(candidate, x.loc[valid_mask], y.loc[valid_mask])
        comparison.append({"model": name, "fit_seconds": fit_seconds,
                           "parameters": candidate.named_steps["regressor"].get_params(),
                           "validation": validation})
        print(f"{name}: validation MAE={validation['mae_m'] * 1000:.3f} mm", flush=True)

    # 검증 MAE로만 선정한다. 테스트/OOD 평가 전에 선택을 확정한다.
    winner = min(comparison, key=lambda row: row["validation"]["mae_m"])["model"]
    model = candidates[winner]
    for row in comparison:
        row["selected"] = row["model"] == winner
        for split in ("train", "test", "ood_test"):
            mask = data["split"].eq(split)
            row[split] = evaluate(candidates[row["model"]], x.loc[mask], y.loc[mask])
    selected = next(row for row in comparison if row["selected"])
    metrics = {split: selected[split] for split in ("validation", "test", "ood_test")}

    metadata = {
        "model_type": winner,
        "selection_criterion": "lowest validation MAE; fixed candidates; no test/OOD selection",
        "model_comparison": comparison,
        "model_parameters": model.named_steps["regressor"].get_params(),
        "feature_columns": FEATURE_COLUMNS,
        "target_name": TARGET_COLUMN,
        "target_column": TARGET_COLUMN,
        "reference_distance_m": REFERENCE_DISTANCE_M,
        "target_unit": "m",
        "source_file": str(dataset_path.resolve()),
        "source_sheet": sheet,
        "valid_rows": len(data),
        "dropped_invalid_target_rows": dropped_rows,
        "training_rows": int(train_mask.sum()),
        "training_split": "train",
        "validation_metrics": metrics,
        "sklearn_version": sklearn.__version__,
        "limitation": LIMITATION,
    }
    # 검증/테스트 데이터로 재학습하지 않는다. 평가한 모델 자체를 저장한다.
    artifact = {"model": model, **metadata}
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    comparison_path = model_path.with_suffix(".comparison.csv")
    table = []
    for row in comparison:
        entry = {"model": row["model"], "selected": row["selected"],
                 "fit_seconds": row["fit_seconds"]}
        for split in ("train", "validation", "test", "ood_test"):
            for metric in ("mae_m", "rmse_m", "r2"):
                entry[f"{split}_{metric}"] = row[split][metric]
        table.append(entry)
    pd.DataFrame(table).sort_values("validation_mae_m").to_csv(
        comparison_path, index=False, encoding="utf-8-sig")
    print(f"Selected: {winner}; comparison: {comparison_path}")
    report_path = model_path.with_suffix(".metrics.json")
    report_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    # 이후 추론 코드에서 사용하는 방법 (이번에는 엑셀 출력하지 않음):
    # artifact = joblib.load(model_path)
    # predicted_noise = artifact["model"].predict(df[artifact["feature_columns"]])
    # corrected_distance = df["distance_measured_m"] - predicted_noise
    print(f"Valid rows: {len(data):,}; training rows: {int(train_mask.sum()):,}")
    print(f"Dropped invalid targets: {dropped_rows}")
    for split, result in metrics.items():
        print(
            f"{split}: MAE={result['mae_m']:.8g} m, "
            f"RMSE={result['rmse_m']:.8g} m, R2={result['r2']:.8g}"
        )
    print(f"Model: {model_path.resolve()}")
    print(f"Metrics: {report_path.resolve()}")
    print(f"NOTE: {LIMITATION}")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()
    train(args.data, args.model)


if __name__ == "__main__":
    main()
