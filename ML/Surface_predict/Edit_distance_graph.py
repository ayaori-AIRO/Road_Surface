from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


ML_DIR = Path(__file__).resolve().parent.parent
EXCEL_PATH = (
    ML_DIR / "dataset" / "Surface_edit_data"
    / "RoadSurf_20251126_121531_outlier_detected.xlsx"
)


def plot_distance() -> None:
    """엑셀의 시간별 Distance(m) 데이터를 선 그래프로 표시한다."""
    data = pd.read_excel(
        EXCEL_PATH,
        usecols=["Timestamp", "Distance_edit(m)"],
        engine="openpyxl",
    )

    data["Timestamp"] = pd.to_datetime(data["Timestamp"], errors="coerce")
    data["Distance_edit(m)"] = pd.to_numeric(
        data["Distance_edit(m)"],
        errors="coerce",
    )
    # Distance의 빈 행은 제거하지 않는다. Matplotlib이 NaN 구간에서 선을 끊는다.
    data = data.dropna(subset=["Timestamp"]).sort_values("Timestamp")

    if data["Distance_edit(m)"].notna().sum() == 0:
        raise ValueError("그래프로 표시할 유효한 Timestamp/Distance(m) 데이터가 없습니다.")

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(
        data["Timestamp"],
        data["Distance_edit(m)"],
        color="#1565C0",
        linewidth=1.4,
    )

    ax.set_title("Edited Distance Over Time", fontsize=16, fontweight="bold")
    ax.set_xlabel("Timestamp")
    ax.set_ylabel("Distance_edit (m)")
    ax.grid(True, color="#D9D9D9", linewidth=0.7, alpha=0.7)
    ax.margins(x=0)

    # 주식 차트처럼 시간 눈금 간격을 데이터 범위에 맞춰 자동 조절한다.
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    plot_distance()
