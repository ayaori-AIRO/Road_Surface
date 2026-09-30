from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd


ML_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = (
    ML_DIR / "dataset" / "Surface_Original_data"
    / "RoadSurf_20251126_121531.xlsx"
)
OUTPUT_DIR = ML_DIR / "dataset" / "Surface_edit_data"
OUTPUT_PATH = OUTPUT_DIR / "RoadSurf_20251126_121531_outlier_detected.xlsx"

DISTANCE_COLUMN = "Distance(m)"
OUTLIER_COLUMN = "Distance_outlier"
EDITED_DISTANCE_COLUMN = "Distance_edit(m)"
NOISE_COLUMN = "Noise(m)"
ACTUAL_DISTANCE = 3.17

# 현재 판정 기준
WINDOW_SIZE = 11
MAD_MULTIPLIER = 3.0
MAD_SCALE_FACTOR = 1.4826
MIN_DISTANCE_THRESHOLD = 0.10


def calculate_threshold(values: np.ndarray) -> tuple[float, float]:
    """정상 이력의 중앙값과 Hampel 임계값을 계산한다."""
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    threshold = max(
        MAD_MULTIPLIER * MAD_SCALE_FACTOR * mad,
        MIN_DISTANCE_THRESHOLD,
    )
    return median, threshold


def detect_distance_outliers(distance: pd.Series) -> pd.Series:
    """과거 정상값 11개의 중앙값과 MAD로 Distance 이상치를 판별한다."""
    numeric_distance = pd.to_numeric(distance, errors="coerce")
    values = numeric_distance.to_numpy(dtype=float)
    outlier = np.zeros(len(values), dtype=bool)

    if len(values) < WINDOW_SIZE:
        raise ValueError(
            f"Distance 데이터가 최소 {WINDOW_SIZE}개 필요합니다."
        )

    # 시작 시 최초 11개로 임시 정상 기준을 만든다.
    initial_values = values[:WINDOW_SIZE]
    finite_initial_values = initial_values[
        np.isfinite(initial_values)
    ]

    if len(finite_initial_values) < 5:
        raise ValueError(
            "최초 11개 중 유효한 Distance가 5개 미만이어서 "
            "초기 정상 기준을 만들 수 없습니다."
        )

    initial_median, initial_threshold = calculate_threshold(
        finite_initial_values
    )

    normal_history: deque[float] = deque(maxlen=WINDOW_SIZE)

    for index, value in enumerate(initial_values):
        is_invalid = not np.isfinite(value)
        is_outlier = (
            is_invalid
            or abs(value - initial_median) > initial_threshold
        )
        outlier[index] = is_outlier

        if not is_outlier:
            normal_history.append(float(value))

    # 초기 이상치를 제외한 정상값이 11개가 될 때까지 새 정상값을 추가한다.
    # 정상 이력이 완성된 뒤에는 반드시 과거 정상값 11개만 사용한다.
    for index in range(WINDOW_SIZE, len(values)):
        value = values[index]

        if not np.isfinite(value):
            outlier[index] = True
            continue

        history_array = np.asarray(normal_history, dtype=float)
        median, threshold = calculate_threshold(history_array)
        is_outlier = abs(value - median) > threshold
        outlier[index] = is_outlier

        # 이상치는 이후 판정 기준에 포함하지 않는다.
        if not is_outlier:
            normal_history.append(float(value))

    return pd.Series(outlier, index=distance.index, dtype=bool)


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"입력 데이터셋을 찾을 수 없습니다: {INPUT_PATH}"
        )

    data = pd.read_excel(INPUT_PATH, engine="openpyxl")

    if DISTANCE_COLUMN not in data.columns:
        raise KeyError(
            f"'{DISTANCE_COLUMN}' 피처를 찾을 수 없습니다. "
            f"현재 피처: {list(data.columns)}"
        )

    data[OUTLIER_COLUMN] = detect_distance_outliers(
        data[DISTANCE_COLUMN]
    )
    data[EDITED_DISTANCE_COLUMN] = data[DISTANCE_COLUMN].where(
        ~data[OUTLIER_COLUMN]
    )
    data[NOISE_COLUMN] = (
        data[EDITED_DISTANCE_COLUMN] - ACTUAL_DISTANCE
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data.to_excel(OUTPUT_PATH, index=False, engine="openpyxl")

    outlier_count = int(data[OUTLIER_COLUMN].sum())
    total_count = len(data)
    outlier_ratio = (
        outlier_count / total_count * 100 if total_count else 0.0
    )

    print(f"검사 완료: {total_count:,}개")
    print(
        f"Distance 이상치: {outlier_count:,}개 "
        f"({outlier_ratio:.2f}%)"
    )
    print(f"결과 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
