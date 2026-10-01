from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ML_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = (
    ML_DIR / "dataset" / "Surface_edit_data"
    / "RoadSurf_20251126_121531_outlier_detected.xlsx"
)
MODEL_DIR = ML_DIR / "Surface_predict" / "models"
MODEL_PATH = MODEL_DIR / "noise_predict_model.joblib"

FEATURE_COLUMNS = [
    "Speed(km/h)",
    "AccelX(g)",
    "AccelY(g)",
    "AccelZ(g)",
    "GyroX(deg/s)",
    "GyroY(deg/s)",
    "GyroZ(deg/s)",
    "Temperature(°C)",
    "Humidity(%)",
]
TARGET_COLUMN = "Noise(m)"

# 엑셀 헤더를 제외한 첫 4,201개 데이터 행만 사용한다.
MAX_DATA_ROWS = 4201
TRAIN_RATIO = 0.8
RANDOM_STATE = 42


def load_training_data() -> tuple[pd.DataFrame, pd.Series]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"학습 데이터셋을 찾을 수 없습니다: {DATASET_PATH}"
        )

    data = pd.read_excel(
        DATASET_PATH,
        engine="openpyxl",
    ).iloc[:MAX_DATA_ROWS].copy()

    # Normalize the legacy temperature header saved with mojibake.
    data = data.rename(columns={"Temperature(\uc9f8C)": "Temperature(\u00b0C)"})
    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing_columns = [name for name in required_columns if name not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing training columns: {missing_columns}")
    data = data[required_columns].copy()

    for column in FEATURE_COLUMNS + [TARGET_COLUMN]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    # 이상치 행은 Noise(m)가 비어 있으므로 학습 대상에서 제외된다.
    data = data.dropna(subset=[TARGET_COLUMN]).reset_index(drop=True)

    if len(data) < 10:
        raise ValueError(
            "유효한 학습 데이터가 10개 미만이어서 모델을 만들 수 없습니다."
        )

    return data[FEATURE_COLUMNS], data[TARGET_COLUMN]


def build_model() -> TransformedTargetRegressor:
    feature_model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=300,
                    min_samples_leaf=2,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    # Noise(m)의 크기가 작으므로 타깃을 표준화해 학습한다.
    return TransformedTargetRegressor(
        regressor=feature_model,
        transformer=StandardScaler(),
    )


def main() -> None:
    features, target = load_training_data()

    # 시계열 순서를 유지해 앞 80%로 학습하고 뒤 20%로 검증한다.
    split_index = int(len(features) * TRAIN_RATIO)
    train_x = features.iloc[:split_index]
    valid_x = features.iloc[split_index:]
    train_y = target.iloc[:split_index]
    valid_y = target.iloc[split_index:]

    evaluation_model = build_model()
    evaluation_model.fit(train_x, train_y)
    prediction = evaluation_model.predict(valid_x)

    mae = float(mean_absolute_error(valid_y, prediction))
    rmse = float(
        np.sqrt(mean_squared_error(valid_y, prediction))
    )
    r2 = float(r2_score(valid_y, prediction))

    # 검증이 끝난 뒤 사용 가능한 전체 데이터로 최종 모델을 다시 학습한다.
    final_model = build_model()
    final_model.fit(features, target)

    artifact = {
        "model": final_model,
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "actual_distance_m": 3.17,
        "max_source_rows": MAX_DATA_ROWS,
        "valid_training_rows": len(features),
        "validation_method": "chronological_last_20_percent",
        "validation_metrics": {
            "mae_m": mae,
            "rmse_m": rmse,
            "r2": r2,
        },
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)

    print(f"사용한 원본 범위: 첫 {MAX_DATA_ROWS:,}개 데이터 행")
    print(f"유효 데이터: {len(features):,}개")
    print(f"학습/검증: {len(train_x):,}개 / {len(valid_x):,}개")
    print(f"검증 MAE: {mae:.6f}m")
    print(f"검증 RMSE: {rmse:.6f}m")
    print(f"검증 R²: {r2:.6f}")
    print(f"모델 저장: {MODEL_PATH}")


if __name__ == "__main__":
    main()
