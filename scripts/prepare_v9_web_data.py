from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FEATURE_PATH = PROJECT_ROOT / "data" / "v8" / "analysis" / "feature_store_level.csv"
V8_WEB = PROJECT_ROOT / "outputs" / "v8" / "web_ready_data"
FRONTEND_DATA = PROJECT_ROOT / "frontend" / "public" / "data"

LATEST_SNAPSHOT = 20251231
GRID_RADIUS_M = 500
GWANGJU_BOUNDS = {
    "min_lat": 35.02,
    "max_lat": 35.32,
    "min_lng": 126.65,
    "max_lng": 127.02,
}

ALLOWED_INDUSTRIES = [
    "cafe",
    "dessert_bakery",
    "restaurant_general",
    "bunsik",
    "chicken",
    "convenience_store",
    "beauty_hair",
    "laundry",
]

INDUSTRY_LABELS = {
    "cafe": "카페",
    "dessert_bakery": "디저트/베이커리",
    "restaurant_general": "일반 음식점",
    "bunsik": "분식",
    "chicken": "치킨",
    "convenience_store": "편의점",
    "beauty_hair": "미용실",
    "laundry": "세탁소",
}

FEATURE_COLUMNS = [
    "snapshot_uid",
    "snapshot_date",
    "store_id",
    "industry_group",
    "sigungu_code",
    "sigungu_name",
    "dong_name",
    "lon",
    "lat",
    "x_m",
    "y_m",
    "survived_12m",
    "total_store_300m",
    "total_store_500m",
    "industry_entropy_500m",
    "same_industry_300m_excl_self",
    "same_industry_500m_excl_self",
    "nearest_bus_m",
    "bus_count_300m",
    "nearest_subway_m",
    "subway_count_500m",
    "cost_burden_proxy",
    "store_age_proxy_months",
]

LAT_COLUMN_CANDIDATES = ("lat", "latitude", "위도")
LNG_COLUMN_CANDIDATES = ("lng", "lon", "longitude", "경도")

FORBIDDEN_FIELDS = [
    "success_probability",
    "survival_probability",
    "failure_probability",
    "closure_probability",
    "sales_prediction",
    "revenue_prediction",
]

FORBIDDEN_TEXT_PARTS = [
    ("창업", "성공", "확률"),
    ("성공", "확률"),
    ("매출", "예측"),
    ("폐업", "예측"),
    ("실제", "생존확률"),
    ("예상", "생존확률"),
    ("이곳에", "창업하면", "성공"),
]


def minmax(series: pd.Series, invert: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    lo = values.quantile(0.02)
    hi = values.quantile(0.98)
    clipped = values.clip(lo, hi)
    if pd.isna(lo) or pd.isna(hi) or math.isclose(float(lo), float(hi)):
        out = pd.Series(50.0, index=series.index)
    else:
        out = (clipped - lo) / (hi - lo) * 100
    if invert:
        out = 100 - out
    return out.fillna(50).clip(0, 100)


def forbidden_texts() -> list[str]:
    return [" ".join(parts) for parts in FORBIDDEN_TEXT_PARTS]


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def round_or_none(value: Any, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def in_gwangju_bounds(df: pd.DataFrame) -> pd.Series:
    return (
        df["lat"].between(GWANGJU_BOUNDS["min_lat"], GWANGJU_BOUNDS["max_lat"])
        & df["lon"].between(GWANGJU_BOUNDS["min_lng"], GWANGJU_BOUNDS["max_lng"])
    )


def detect_coordinate_columns(columns: pd.Index) -> tuple[str, str]:
    column_lookup = {str(col).strip().lower(): str(col) for col in columns}
    lat_col = next((column_lookup[name.lower()] for name in LAT_COLUMN_CANDIDATES if name.lower() in column_lookup), "")
    lng_col = next((column_lookup[name.lower()] for name in LNG_COLUMN_CANDIDATES if name.lower() in column_lookup), "")
    if not lat_col or not lng_col:
        raise ValueError(
            "feature_store_level.csv must include coordinate columns among "
            f"{LAT_COLUMN_CANDIDATES} and {LNG_COLUMN_CANDIDATES}"
        )
    return lat_col, lng_col


def load_feature_data() -> pd.DataFrame:
    source_columns = pd.read_csv(FEATURE_PATH, nrows=0).columns
    lat_col, lng_col = detect_coordinate_columns(source_columns)
    optional_columns = {"lat", "lon", "lng", "latitude", "longitude", "위도", "경도", "x_m", "y_m"}
    required_columns = [col for col in FEATURE_COLUMNS if col not in optional_columns]
    missing = [col for col in required_columns if col not in source_columns]
    if missing:
        raise ValueError(f"feature_store_level.csv missing columns: {missing}")
    usecols = list(dict.fromkeys(required_columns + [lat_col, lng_col]))
    df = pd.read_csv(FEATURE_PATH, usecols=usecols, low_memory=False)
    df = df.rename(columns={lat_col: "lat", lng_col: "lon"})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df[df["industry_group"].isin(ALLOWED_INDUSTRIES)].copy()
    df = df[df["lat"].notna() & df["lon"].notna()].copy()
    df = df[in_gwangju_bounds(df)].copy()
    return df


def build_scores(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    scored["snapshot_date"] = pd.to_numeric(scored["snapshot_date"], errors="coerce").astype("Int64")

    historical = scored[scored["survived_12m"].notna()].copy()
    industry_retention = historical.groupby("industry_group")["survived_12m"].mean()
    district_retention = historical.groupby("sigungu_name")["survived_12m"].mean()

    latest = scored[scored["snapshot_date"] == LATEST_SNAPSHOT].copy()
    if latest.empty:
        raise ValueError(f"No rows found for latest snapshot {LATEST_SNAPSHOT}")

    latest["demand_proxy_score"] = (
        minmax(latest["total_store_300m"]) * 0.55
        + minmax(latest["total_store_500m"]) * 0.20
        + minmax(latest["industry_entropy_500m"]) * 0.25
    )
    latest["accessibility_score"] = (
        minmax(latest["nearest_bus_m"], invert=True) * 0.40
        + minmax(latest["bus_count_300m"]) * 0.30
        + minmax(latest["nearest_subway_m"], invert=True) * 0.20
        + minmax(latest["subway_count_500m"]) * 0.10
    )
    latest["competition_burden_score"] = (
        minmax(latest["same_industry_300m_excl_self"], invert=True) * 0.70
        + minmax(latest["same_industry_500m_excl_self"], invert=True) * 0.30
    )
    latest["cost_inverted_score"] = minmax(latest["cost_burden_proxy"], invert=True)

    latest["industry_retention_rate"] = latest["industry_group"].map(industry_retention).fillna(historical["survived_12m"].mean())
    latest["district_retention_rate"] = latest["sigungu_name"].map(district_retention).fillna(historical["survived_12m"].mean())
    latest["industry_fit_score"] = minmax(latest["industry_retention_rate"])

    # This score intentionally differs from suitability_score. It reflects observed-retention proxy patterns only.
    latest["retention_proxy_score"] = (
        minmax(latest["industry_retention_rate"]) * 0.45
        + minmax(latest["district_retention_rate"]) * 0.25
        + minmax(latest["store_age_proxy_months"]) * 0.15
        + minmax(latest["industry_entropy_500m"]) * 0.15
    )
    latest["suitability_score"] = (
        latest["demand_proxy_score"] * 0.30
        + latest["accessibility_score"] * 0.20
        + latest["industry_fit_score"] * 0.20
        + latest["competition_burden_score"] * 0.15
        + latest["cost_inverted_score"] * 0.15
    )
    latest["risk_level"] = np.select(
        [latest["suitability_score"] >= 75, latest["suitability_score"] >= 60],
        ["낮음", "보통"],
        default="주의",
    )
    return latest


def add_grid_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    gridded = df.copy()
    try:
        from pyproj import Transformer  # type: ignore

        transformer = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
        inverse = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
        x_values, y_values = transformer.transform(gridded["lon"].to_numpy(), gridded["lat"].to_numpy())
        gridded["grid_x"] = np.floor(np.array(x_values) / GRID_RADIUS_M).astype(int)
        gridded["grid_y"] = np.floor(np.array(y_values) / GRID_RADIUS_M).astype(int)
        center_x = (gridded["grid_x"] + 0.5) * GRID_RADIUS_M
        center_y = (gridded["grid_y"] + 0.5) * GRID_RADIUS_M
        center_lng, center_lat = inverse.transform(center_x.to_numpy(), center_y.to_numpy())
        gridded["grid_center_lat"] = center_lat
        gridded["grid_center_lng"] = center_lng
        method = "pyproj EPSG:4326 to EPSG:5179 500m bin"
    except Exception:
        lat_meter = 111_320.0
        reference_lat = (GWANGJU_BOUNDS["min_lat"] + GWANGJU_BOUNDS["max_lat"]) / 2
        lng_meter = 111_320.0 * math.cos(math.radians(reference_lat))
        gridded["grid_x"] = np.floor((gridded["lon"] - GWANGJU_BOUNDS["min_lng"]) * lng_meter / GRID_RADIUS_M).astype(int)
        gridded["grid_y"] = np.floor((gridded["lat"] - GWANGJU_BOUNDS["min_lat"]) * lat_meter / GRID_RADIUS_M).astype(int)
        gridded["grid_center_lng"] = GWANGJU_BOUNDS["min_lng"] + ((gridded["grid_x"] + 0.5) * GRID_RADIUS_M / lng_meter)
        gridded["grid_center_lat"] = GWANGJU_BOUNDS["min_lat"] + ((gridded["grid_y"] + 0.5) * GRID_RADIUS_M / lat_meter)
        method = "lat/lng approximate 500m bin"

    grid_keys = gridded[["grid_x", "grid_y"]].drop_duplicates().sort_values(["grid_y", "grid_x"])
    base_ids = {
        (int(row.grid_x), int(row.grid_y)): f"GJ-grid-{idx:04d}"
        for idx, row in enumerate(grid_keys.itertuples(index=False), start=1)
    }
    gridded["base_grid_id"] = [
        base_ids[(int(grid_x), int(grid_y))]
        for grid_x, grid_y in zip(gridded["grid_x"], gridded["grid_y"], strict=False)
    ]
    return gridded, {
        "grid_size_m": GRID_RADIUS_M,
        "coordinate_method": method,
        "base_grid_count": len(base_ids),
    }


def mode_text(series: pd.Series) -> str:
    cleaned = series.dropna().astype(str).str.strip()
    if cleaned.empty:
        return ""
    return cleaned.value_counts().index[0]


def risk_from_score(score: float) -> str:
    if score >= 75:
        return "낮음"
    if score >= 60:
        return "보통"
    return "주의"


def build_reason_lists(row: pd.Series, competition_q75: float, competition_q60: float, cost_q75: float) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    negatives: list[str] = []
    same_industry = float(row.get("same_industry_300m_excl_self", 0) or 0)

    if row["demand_proxy_score"] >= 70:
        positives.append("주변 상가 규모와 업종 다양성 proxy가 높아 수요 신호가 확인됩니다.")
    elif row["demand_proxy_score"] < 45:
        negatives.append("상권 규모 proxy가 낮아 실제 수요 확인이 필요합니다.")

    if same_industry >= competition_q60:
        positives.append("동일 업종 밀집도가 있어 관련 수요가 존재한다는 신호로 볼 수 있습니다.")
    if same_industry >= competition_q75:
        negatives.append("다만 동일 업종 밀집도가 높아 경쟁 부담도 함께 확인해야 합니다.")
    elif row["competition_burden_score"] >= 65:
        positives.append("동일 업종 과밀 부담 proxy가 상대적으로 낮은 편입니다.")

    if row["accessibility_score"] >= 70:
        positives.append("버스 또는 도시철도 접근성 proxy가 양호합니다.")
    elif row["accessibility_score"] < 45:
        negatives.append("대중교통 접근성 proxy가 낮아 접근성 검토가 필요합니다.")

    if pd.notna(row.get("cost_burden_proxy")) and float(row["cost_burden_proxy"]) >= cost_q75:
        negatives.append("비용 부담 proxy가 높은 편입니다. 실제 임대료와 권리금 확인이 필요합니다.")
    elif row["cost_inverted_score"] >= 65:
        positives.append("비용 부담 proxy가 상대적으로 낮은 편입니다.")

    if not positives:
        positives.append("공공데이터 proxy를 종합했을 때 비교 후보지로 검토할 수 있습니다.")
    if not negatives:
        negatives.append("현장 임대료, 권리금, 유동인구, 점포 상태는 별도 확인이 필요합니다.")
    return positives[:4], negatives[:4]


def row_to_candidate(row: pd.Series, rank: int, competition_q75: float, competition_q60: float, cost_q75: float) -> dict[str, Any]:
    industry = clean_text(row["industry_group"])
    sigungu = clean_text(row["sigungu_name"])
    dong = clean_text(row["dong_name"])
    label = INDUSTRY_LABELS.get(industry, industry)
    positive_reasons, negative_reasons = build_reason_lists(row, competition_q75, competition_q60, cost_q75)
    return {
        "candidate_id": f"GJ-{int(row['sigungu_code'])}-{industry}-{rank:03d}",
        "name": f"{sigungu} {dong} {label} 후보지",
        "sigungu": sigungu,
        "dong": dong,
        "lat": round(float(row["lat"]), 6),
        "lng": round(float(row["lon"]), 6),
        "recommended_industry": industry,
        "industry_label": label,
        "suitability_score": round_or_none(row["suitability_score"]),
        "retention_proxy_score": round_or_none(row["retention_proxy_score"]),
        "risk_level": clean_text(row["risk_level"]),
        "demand_proxy_score": round_or_none(row["demand_proxy_score"]),
        "competition_burden_score": round_or_none(row["competition_burden_score"]),
        "accessibility_score": round_or_none(row["accessibility_score"]),
        "cost_burden_proxy": round_or_none(row["cost_burden_proxy"]),
        "cost_inverted_score": round_or_none(row["cost_inverted_score"]),
        "industry_fit_score": round_or_none(row["industry_fit_score"]),
        "same_industry_300m": round_or_none(row["same_industry_300m_excl_self"], 1),
        "total_store_300m": round_or_none(row["total_store_300m"], 1),
        "positive_reasons": positive_reasons,
        "negative_reasons": negative_reasons,
    }


def build_candidates(scored: pd.DataFrame) -> list[dict[str, Any]]:
    scored = scored.copy()

    competition_q75 = float(scored["same_industry_300m_excl_self"].quantile(0.75))
    competition_q60 = float(scored["same_industry_300m_excl_self"].quantile(0.60))
    cost_q75 = float(scored["cost_burden_proxy"].quantile(0.75))

    per_industry_rows: dict[str, list[pd.Series]] = {}
    for industry in ALLOWED_INDUSTRIES:
        group = scored[scored["industry_group"] == industry].copy()
        group = group.sort_values(["suitability_score", "retention_proxy_score"], ascending=False)
        group = group.drop_duplicates(["grid_x", "grid_y"])
        per_industry_rows[industry] = [row for _, row in group.head(20).iterrows()]

    candidates: list[dict[str, Any]] = []
    rank = 1
    for idx in range(20):
        for industry in ALLOWED_INDUSTRIES:
            rows = per_industry_rows.get(industry, [])
            if idx >= len(rows):
                continue
            candidates.append(row_to_candidate(rows[idx], rank, competition_q75, competition_q60, cost_q75))
            rank += 1
    return candidates


def build_grid_scores(scored: pd.DataFrame) -> list[dict[str, Any]]:
    competition_q75 = float(scored["same_industry_300m_excl_self"].quantile(0.75))
    competition_q60 = float(scored["same_industry_300m_excl_self"].quantile(0.60))
    cost_q75 = float(scored["cost_burden_proxy"].quantile(0.75))
    score_columns = [
        "suitability_score",
        "retention_proxy_score",
        "demand_proxy_score",
        "competition_burden_score",
        "accessibility_score",
        "cost_burden_proxy",
        "cost_inverted_score",
        "industry_fit_score",
        "same_industry_300m_excl_self",
        "total_store_300m",
        "industry_entropy_500m",
        "store_age_proxy_months",
    ]

    rows: list[dict[str, Any]] = []
    grouped = scored.groupby(["base_grid_id", "industry_group"], dropna=False)
    for (base_grid_id, industry), group in grouped:
        if industry not in ALLOWED_INDUSTRIES:
            continue
        values: dict[str, Any] = {
            column: pd.to_numeric(group[column], errors="coerce").mean()
            for column in score_columns
        }
        synthetic = pd.Series(values)
        positive_reasons, negative_reasons = build_reason_lists(
            synthetic,
            competition_q75,
            competition_q60,
            cost_q75,
        )
        suitability = float(values["suitability_score"]) if pd.notna(values["suitability_score"]) else 50.0
        center_lat = float(group["grid_center_lat"].iloc[0])
        center_lng = float(group["grid_center_lng"].iloc[0])
        sigungu = mode_text(group["sigungu_name"])
        dong = mode_text(group["dong_name"])
        label = INDUSTRY_LABELS.get(str(industry), str(industry))
        rows.append(
            {
                "grid_id": f"{base_grid_id}-{industry}",
                "base_grid_id": str(base_grid_id),
                "center_lat": round(center_lat, 6),
                "center_lng": round(center_lng, 6),
                "lat": round(center_lat, 6),
                "lng": round(center_lng, 6),
                "sigungu": sigungu,
                "dong": dong,
                "radius_m": GRID_RADIUS_M,
                "industry": str(industry),
                "recommended_industry": str(industry),
                "industry_label": label,
                "suitability_score": round_or_none(values["suitability_score"]),
                "retention_proxy_score": round_or_none(values["retention_proxy_score"]),
                "risk_level": risk_from_score(suitability),
                "demand_proxy_score": round_or_none(values["demand_proxy_score"]),
                "competition_burden_score": round_or_none(values["competition_burden_score"]),
                "accessibility_score": round_or_none(values["accessibility_score"]),
                "cost_burden_proxy": round_or_none(values["cost_burden_proxy"]),
                "cost_inverted_score": round_or_none(values["cost_inverted_score"]),
                "industry_fit_score": round_or_none(values["industry_fit_score"]),
                "same_industry_300m": round_or_none(values["same_industry_300m_excl_self"], 1),
                "total_store_300m": round_or_none(values["total_store_300m"], 1),
                "store_count_in_grid": int(len(group)),
                "positive_reasons": positive_reasons,
                "negative_reasons": negative_reasons,
                "analysis_basis": "500m 상권 격자 기반",
                "source_type": "grid",
            }
        )
    return sorted(
        rows,
        key=lambda item: (item["base_grid_id"], -(item["suitability_score"] or 0)),
    )


def group_candidates_by_industry(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {industry: [] for industry in ALLOWED_INDUSTRIES}
    for candidate in candidates:
        grouped[candidate["recommended_industry"]].append(candidate)
    return grouped


def build_industry_recommendations(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_place: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = f"{candidate['sigungu']} {candidate['dong']}"
        by_place.setdefault(key, []).append(candidate)

    rows: list[dict[str, Any]] = []
    for place, items in by_place.items():
        top = sorted(items, key=lambda item: item["suitability_score"] or 0, reverse=True)[:5]
        if not top:
            continue
        rows.append(
            {
                "candidate_id": f"REC-{len(rows) + 1:03d}",
                "place": place,
                "sigungu": top[0]["sigungu"],
                "dong": top[0]["dong"],
                "lat": top[0]["lat"],
                "lng": top[0]["lng"],
                "industry_top5": [
                    {
                        "rank": idx,
                        "industry": item["recommended_industry"],
                        "industry_label": item["industry_label"],
                        "score": item["suitability_score"],
                        "retention_proxy_score": item["retention_proxy_score"],
                        "reason": "공공데이터 기반 입지 적합도와 상가정보 스냅샷상 관측 유지 proxy를 함께 참고했습니다.",
                    }
                    for idx, item in enumerate(top, start=1)
                ],
            }
        )
    return rows[:100]


def build_assistant_context(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    context: dict[str, dict[str, list[dict[str, Any]]]] = {}
    ordered = sorted(candidates, key=lambda item: item["suitability_score"] or 0, reverse=True)
    for candidate in ordered:
        region = candidate["sigungu"]
        industry = candidate["recommended_industry"]
        context.setdefault(region, {}).setdefault(industry, [])
        if len(context[region][industry]) < 3:
            context[region][industry].append(candidate)
    return {
        "top3_by_region_industry": context,
        "safe_answer_guideline": "AI는 로컬 JSON에서 선택된 후보지를 설명만 하며, 실제 창업 성과나 재무 결과를 보장하거나 예측하지 않는다.",
    }


def copy_json(name: str) -> None:
    source = V8_WEB / name
    if source.exists():
        if name == "validation_summary.json":
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["safe_note"] = "실제 창업 성과나 재무 결과를 보장하거나 예측한 결과가 아닙니다."
            write_json(name, payload)
            return
        shutil.copyfile(source, FRONTEND_DATA / name)


def write_json(name: str, payload: Any) -> None:
    path = FRONTEND_DATA / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_outputs(candidates: list[dict[str, Any]], grid_scores: list[dict[str, Any]], grid_meta: dict[str, Any]) -> dict[str, Any]:
    industries = sorted({candidate["recommended_industry"] for candidate in candidates})
    grid_industries = sorted({row["industry"] for row in grid_scores})
    missing_required = [
        candidate["candidate_id"]
        for candidate in candidates
        if not all(candidate.get(key) is not None for key in ["lat", "lng", "suitability_score", "retention_proxy_score", "recommended_industry"])
    ]
    missing_grid_required = [
        row["grid_id"]
        for row in grid_scores
        if not all(row.get(key) is not None for key in ["center_lat", "center_lng", "suitability_score", "retention_proxy_score", "industry"])
    ]
    grid_out_of_bounds = [
        row["grid_id"]
        for row in grid_scores
        if not (
            GWANGJU_BOUNDS["min_lat"] <= float(row["center_lat"]) <= GWANGJU_BOUNDS["max_lat"]
            and GWANGJU_BOUNDS["min_lng"] <= float(row["center_lng"]) <= GWANGJU_BOUNDS["max_lng"]
        )
    ]
    equal_scores = sum(
        1
        for candidate in candidates
        if candidate.get("suitability_score") == candidate.get("retention_proxy_score")
    )
    grid_equal_scores = sum(
        1
        for row in grid_scores
        if row.get("suitability_score") == row.get("retention_proxy_score")
    )
    forbidden_hits: list[str] = []
    forbidden_text_hits: list[str] = []
    for path in FRONTEND_DATA.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for field in FORBIDDEN_FIELDS:
            if field in text:
                forbidden_hits.append(f"{path.name}:{field}")
        for phrase in forbidden_texts():
            if phrase in text:
                forbidden_text_hits.append(f"{path.name}:{phrase}")
    return {
        "candidate_count": len(candidates),
        "industries": industries,
        "contains_other": "other" in industries,
        "missing_required_count": len(missing_required),
        "same_suitability_and_retention_count": equal_scores,
        "grid_row_count": len(grid_scores),
        "grid_base_count": grid_meta["base_grid_count"],
        "grid_size_m": grid_meta["grid_size_m"],
        "grid_coordinate_method": grid_meta["coordinate_method"],
        "grid_industries": grid_industries,
        "grid_contains_other": "other" in grid_industries,
        "grid_missing_required_count": len(missing_grid_required),
        "grid_out_of_bounds_count": len(grid_out_of_bounds),
        "grid_same_suitability_and_retention_count": grid_equal_scores,
        "forbidden_field_hits": forbidden_hits,
        "forbidden_text_hits": forbidden_text_hits,
        "new_store_survived_12m_used_for_scoring": False,
        "note": "new_store_survived_12m is intentionally excluded from recommendation scoring and used only as a limitation insight.",
    }


def main() -> None:
    FRONTEND_DATA.mkdir(parents=True, exist_ok=True)
    scored = build_scores(load_feature_data())
    scored, grid_meta = add_grid_columns(scored)
    candidates = build_candidates(scored)
    grid_scores = build_grid_scores(scored)
    by_industry = group_candidates_by_industry(candidates)
    industry_recommendations = build_industry_recommendations(candidates)
    assistant_context = build_assistant_context(candidates)

    write_json("candidates_balanced.json", candidates)
    write_json("grid_scores.json", grid_scores)
    write_json("candidates_by_industry.json", by_industry)
    write_json("industry_recommendations_filtered.json", industry_recommendations)
    write_json("assistant_recommendation_context_filtered.json", assistant_context)
    for name in ["district_summary.json", "model_metrics.json", "validation_summary.json", "explanation_rules.json"]:
        copy_json(name)

    validation = validate_outputs(candidates, grid_scores, grid_meta)
    write_json("v9_data_quality.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
