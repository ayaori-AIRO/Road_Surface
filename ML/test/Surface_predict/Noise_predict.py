from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ML_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = (
    ML_DIR / "dataset" / "Surface_edit_data"
    / "RoadSurf_20251126_121531_outlier_detected.xlsx"
)
MODEL_PATH = ML_DIR / "Surface_predict" / "models" / "noise_predict_model.joblib"
OUTPUT_DIR = ML_DIR / "dataset" / "Surface_predict_result"
OUTPUT_PATH = OUTPUT_DIR / f"{INPUT_PATH.stem}_noise_predicted.xlsx"
PREDICTION_COLUMN = "Predicted_noise(m)"


def main() -> None:
    for path in (INPUT_PATH, MODEL_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    artifact = joblib.load(MODEL_PATH)
    model = artifact["model"]
    feature_columns = artifact["feature_columns"]

    data = pd.read_excel(INPUT_PATH, engine="openpyxl")
    model_data = data.rename(columns={"Temperature(\uc9f8C)": "Temperature(\u00b0C)"})
    missing_columns = [column for column in feature_columns if column not in model_data.columns]
    if missing_columns:
        raise ValueError(f"예측에 필요한 피쳐가 없습니다: {missing_columns}")
    if data.empty:
        raise ValueError("예측할 데이터 행이 없습니다.")

    # 원본 열은 유지하고 모델 입력만 숫자로 변환한다.
    # 결측값은 저장된 모델 내부의 학습된 중앙값 대체기로 처리한다.
    features = model_data[feature_columns].apply(pd.to_numeric, errors="coerce")
    features = features.replace([np.inf, -np.inf], np.nan)

    # 학습 때의 행 제한이나 Noise(m) 유무와 무관하게 전체 행을 예측한다.
    data[PREDICTION_COLUMN] = model.predict(features)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data.to_excel(OUTPUT_PATH, index=False, engine="openpyxl")

    print(f"노이즈 예측 완료: {len(data):,}개 행")
    print(f"추가한 열: {PREDICTION_COLUMN}")
    print(f"결과 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
