from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "v8" / "reports"
TABLES = ROOT / "outputs" / "v8" / "tables"
WEB = ROOT / "outputs" / "v8" / "web_ready_data"
PROCESSED = ROOT / "data" / "v8" / "processed"
ANALYSIS = ROOT / "data" / "v8" / "analysis"
OUT = REPORTS / "BizSpot_AI_v8_FULL_RESULT_DATA_REPORT.md"


def fmt(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def md(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int | None = None) -> str:
    if df is None or df.empty:
        return "_데이터 없음_"
    work = df.copy()
    if cols:
        work = work[[col for col in cols if col in work.columns]]
    if max_rows is not None:
        work = work.head(max_rows)
    columns = list(work.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for _, row in work.iterrows():
        values = []
        for col in columns:
            value = fmt(row[col]).replace("\n", "<br>").replace("|", "/")
            values.append(value)
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def read_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def file_size(path: Path) -> str:
    if not path.exists():
        return ""
    size = float(path.stat().st_size)
    units = ["B", "KB", "MB", "GB"]
    unit_idx = 0
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_json(name: str):
    return json.loads((WEB / name).read_text(encoding="utf-8"))


def build_output_inventory(scan: pd.DataFrame) -> pd.DataFrame:
    output_files: list[dict[str, object]] = []
    groups = [
        (
            "report_md",
            REPORTS,
            [
                "data_file_scan.md",
                "data_mapping_report.md",
                "matching_quality_report.md",
                "label_definition_report.md",
                "feature_design_report.md",
                "model_validation_report.md",
                "hypothesis_validation_report.md",
                "web_data_contract.md",
                "risk_checklist.md",
                "experiment_summary.md",
                "web_json_field_validation.md",
                "BizSpot_AI_v8_FULL_RESULT_DATA_REPORT.md",
            ],
        ),
        (
            "processed_csv",
            PROCESSED,
            [
                "store_panel_gwangju.csv",
                "matched_store_panel.csv",
                "snapshot_transition_matches.csv",
                *[f"store_snapshot_{date}_gwangju.csv" for date in scan["snapshot_date"].astype(str)],
            ],
        ),
        (
            "analysis_csv",
            ANALYSIS,
            [
                "feature_store_level.csv",
                "survival_6m_dataset.csv",
                "survival_12m_dataset.csv",
                "new_store_survival_12m_dataset.csv",
            ],
        ),
        (
            "table_csv",
            TABLES,
            [
                "data_file_scan.csv",
                "snapshot_quality.csv",
                "matching_quality_by_transition.csv",
                "label_summary.csv",
                "model_metrics.csv",
                "feature_importance.csv",
                "competition_threshold.csv",
                "cost_burden_quantiles.csv",
                "ablation_study.csv",
                "radius_sensitivity.csv",
                "industry_performance.csv",
                "top_candidates.csv",
                "top_industry_recommendations.csv",
                "district_summary.csv",
            ],
        ),
        (
            "web_json",
            WEB,
            [
                "candidates.json",
                "industry_recommendations.json",
                "assistant_recommendation_context.json",
                "district_summary.json",
                "model_metrics.json",
                "validation_summary.json",
                "explanation_rules.json",
            ],
        ),
    ]
    for category, base, names in groups:
        for name in names:
            path = base / name
            output_files.append(
                {
                    "category": category,
                    "file": rel(path),
                    "exists": path.exists(),
                    "size": file_size(path),
                }
            )
    return pd.DataFrame(output_files)


def main() -> None:
    scan = read_table("data_file_scan.csv")
    match = read_table("matching_quality_by_transition.csv")
    labels = read_table("label_summary.csv")
    metrics = read_table("model_metrics.csv")
    competition = read_table("competition_threshold.csv")
    cost = read_table("cost_burden_quantiles.csv")
    ablation = read_table("ablation_study.csv")
    radius = read_table("radius_sensitivity.csv")
    industry_perf = read_table("industry_performance.csv")
    importance = read_table("feature_importance.csv")
    district = pd.read_csv(TABLES / "district_summary.csv")

    metrics["target_report_name"] = metrics["target"].map(
        {
            "survived_6m": "6개월 영업 유지 proxy",
            "survived_12m": "12개월 영업 유지 proxy",
            "new_store_survived_12m": "신규 점포 12개월 관측 유지 proxy",
        }
    ).fillna(metrics["target"])

    main_time = metrics[
        (metrics["split"] == "time_split")
        & (metrics["model"].isin(["logistic_regression", "random_forest", "xgboost"]))
    ][
        [
            "target_report_name",
            "model",
            "rows",
            "positive_rate",
            "auroc",
            "pr_auc",
            "f1",
            "precision",
            "recall",
            "accuracy",
            "brier_score",
        ]
    ]

    spatial = metrics[
        (metrics["target"] == "survived_12m")
        & (metrics["split"].astype(str).str.contains("spatial_holdout"))
        & (metrics["model"].isin(["logistic_regression", "random_forest", "xgboost"]))
    ].copy()
    spatial_best = spatial.sort_values(["split", "pr_auc"], ascending=[True, False]).groupby("split").head(1)[
        ["split", "model", "rows", "positive_rate", "auroc", "pr_auc", "f1", "precision", "recall", "accuracy", "brier_score"]
    ]

    group = metrics[
        (metrics["target"] == "survived_12m")
        & (metrics["split"].astype(str).str.contains("groupkfold"))
        & (metrics["model"].isin(["logistic_regression", "random_forest", "xgboost"]))
    ].copy()
    group_best = group.sort_values(["split", "pr_auc"], ascending=[True, False]).groupby("split").head(1)[
        ["split", "model", "rows", "positive_rate", "auroc", "pr_auc", "f1", "precision", "recall", "accuracy", "brier_score"]
    ]

    special_2024 = match[match["special_2024_transition"] == True].copy()  # noqa: E712
    candidates = pd.DataFrame(load_json("candidates.json"))
    recommendations = load_json("industry_recommendations.json")

    recommendation_rows: list[dict[str, object]] = []
    for item in recommendations:
        top5 = item.get("industry_top5", [])
        recommendation_rows.append(
            {
                "candidate_id": item.get("candidate_id"),
                "industry_top5": ", ".join(
                    f"{entry.get('rank')}.{entry.get('industry')}({entry.get('score')})" for entry in top5
                ),
            }
        )
    industry_recs = pd.DataFrame(recommendation_rows)

    forbidden_fields = [
        "success_probability",
        "survival_probability",
        "failure_probability",
        "closure_probability",
        "sales_prediction",
        "revenue_prediction",
    ]
    violations: list[str] = []
    for path in WEB.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        for term in forbidden_fields:
            if term in text:
                violations.append(f"{path.name}:{term}")

    panel_rows = int(scan["row_count_estimate"].sum())
    output_inventory = build_output_inventory(scan)
    candidate_cols = [
        "candidate_id",
        "sigungu",
        "dong",
        "recommended_industry",
        "suitability_score",
        "retention_proxy_score",
        "risk_level",
        "demand_proxy_score",
        "competition_burden_score",
        "accessibility_score",
        "cost_burden_proxy",
        "industry_fit_score",
    ]

    summary = pd.DataFrame(
        [
            {"항목": "입력 스냅샷 수", "값": len(scan), "해석": "2022-06부터 2025-12까지 반기별 8개 광주 상가정보 스냅샷"},
            {"항목": "상가 패널 행 수", "값": f"{panel_rows:,}", "해석": "8개 스냅샷의 광주 상가 레코드 합계"},
            {
                "항목": "6개월 영업 유지 proxy 유효 행",
                "값": f"{int(labels.loc[labels.internal_column == 'survived_6m', 'valid_rows'].iloc[0]):,}",
                "해석": "t 시점 점포가 t+6개월 스냅샷에도 관측되는지",
            },
            {
                "항목": "6개월 영업 유지 proxy 비율",
                "값": f"{float(labels.loc[labels.internal_column == 'survived_6m', 'positive_rate'].iloc[0]):.4f}",
                "해석": "실제 생존율/폐업률이 아니라 스냅샷 관측 유지 비율",
            },
            {
                "항목": "12개월 영업 유지 proxy 유효 행",
                "값": f"{int(labels.loc[labels.internal_column == 'survived_12m', 'valid_rows'].iloc[0]):,}",
                "해석": "t 시점 점포가 t+12개월 스냅샷에도 관측되는지",
            },
            {
                "항목": "12개월 영업 유지 proxy 비율",
                "값": f"{float(labels.loc[labels.internal_column == 'survived_12m', 'positive_rate'].iloc[0]):.4f}",
                "해석": "메인 실험 타깃",
            },
            {
                "항목": "신규 점포 12개월 관측 유지 proxy 유효 행",
                "값": f"{int(labels.loc[labels.internal_column == 'new_store_survived_12m', 'valid_rows'].iloc[0]):,}",
                "해석": "t에는 있고 t-6에는 없던 점포의 t+12 관측 유지",
            },
            {"항목": "웹 후보지 JSON 수", "값": len(candidates), "해석": "candidates.json에 저장된 공공데이터 기반 후보지 점수"},
            {"항목": "웹 업종 추천 JSON 수", "값": len(industry_recs), "해석": "industry_recommendations.json에 저장된 격자별 업종 추천"},
            {"항목": "금지 웹 필드명 검출", "값": "없음" if not violations else ", ".join(violations), "해석": "성공확률/폐업확률/매출예측 계열 필드명 금지"},
        ]
    )

    lines: list[str] = [
        "# BizSpot AI v8 전체 결과 통합 데이터 보고서",
        "",
        "생성일: 2026-05-14",
        "",
        "본 문서는 v8 보정 지시를 반영한 전처리, 점포 매칭, 영업 유지 proxy 라벨, 모델 검증, 가설 검증, 웹 데이터 계약, 산출물 경로를 한 번에 확인하기 위한 통합 Markdown 보고서이다.",
        "",
        "> 본 결과는 실제 창업 성공이나 매출을 직접 예측한 것이 아니라, 상가정보 스냅샷상 관측 유지와 공공데이터 proxy 변수로 광주 상권의 관측 유지 패턴을 설명할 수 있는지 검증한 결과이다.",
        "",
        "## 1. 한눈에 보는 결론",
        "",
        md(summary),
        "",
        "## 2. 안전한 해석",
        "",
        "- 공공데이터와 상가정보 스냅샷만으로 광주 상권의 관측 유지 패턴을 일부 설명할 가능성을 확인했다.",
        "- 그러나 이 결과는 실제 창업 성공, 실제 매출, 실제 폐업률을 직접 예측한 것이 아니다.",
        "- `survived_6m`, `survived_12m`는 내부 컬럼명으로만 사용하며, 보고서/웹에서는 각각 “6개월 영업 유지 proxy”, “12개월 영업 유지 proxy”, “상가정보 스냅샷상 관측 유지”라고 표현한다.",
        "- 웹에서는 이 모델을 “창업 성공 예측기”가 아니라 “입지 후보지를 1차로 필터링하는 의사결정 지원 도구”로 사용한다.",
        "- 실제 창업 판단에는 임대료, 권리금, 점포 내부 상태, 브랜드 전략, 실제 유동인구, 현장 경쟁 강도 등 추가 데이터가 필요하다.",
        "",
        "## 3. 입력 데이터 스캔 결과",
        "",
        "8개 반기 ZIP에서 광주 CSV를 모두 찾았다. 2022년 파일은 중첩 ZIP 구조였고, ZIP entry명은 cp437 기반 복원 후보를 적용해 탐색했다.",
        "",
        md(scan[["snapshot_date", "gwangju_entry", "nested_zip_entry", "encoding", "column_count", "row_count_estimate", "entry_size_bytes"]]),
        "",
        "## 4. 점포 매칭 품질",
        "",
        "매칭은 1차 `상가업소번호` 직접 매칭, 2차 자치구/업종그룹/좌표 300m blocking 기반 fuzzy matching 순서로 수행했다. 전체 pairwise fuzzy matching은 수행하지 않았다.",
        "",
        md(
            match[
                [
                    "from_snapshot",
                    "to_snapshot",
                    "from_rows",
                    "to_rows",
                    "direct_id_matches",
                    "blocked_fuzzy_matches",
                    "total_matches",
                    "match_rate_from",
                    "direct_id_match_rate_from",
                    "blocked_fuzzy_match_rate_from",
                    "unmatched_from",
                    "candidate_pairs_after_blocking",
                    "review_pairs_70_84",
                    "accepted_pairs_85_plus",
                    "special_2024_transition",
                ]
            ]
        ),
        "",
        "### 4.1 2024년 전후 특이 구간",
        "",
        "2024년 업종코드/업소번호 개편 가능성을 고려해 아래 두 구간은 별도 해석 대상이다.",
        "",
        md(
            special_2024[
                [
                    "from_snapshot",
                    "to_snapshot",
                    "direct_id_matches",
                    "blocked_fuzzy_matches",
                    "match_rate_from",
                    "direct_id_match_rate_from",
                    "blocked_fuzzy_match_rate_from",
                    "candidate_pairs_after_blocking",
                    "review_pairs_70_84",
                    "accepted_pairs_85_plus",
                ]
            ]
        ),
        "",
        "## 5. 타깃 라벨 정의",
        "",
        "라벨은 실제 생존/폐업/매출 데이터가 아니라, 상가정보 스냅샷에서 동일 점포가 이후 기준일에도 관측되는지를 이용해 만든 proxy label이다. t+6, t+12 스냅샷은 label 생성에만 사용했고 feature에는 포함하지 않았다.",
        "",
        md(labels),
        "",
        "### 5.1 타깃으로 말할 수 있는 것과 없는 것",
        "",
        "| 구분 | 내용 |",
        "| --- | --- |",
        "| 말할 수 있는 결론 | 공공데이터 proxy와 과거 상가정보 스냅샷이 점포의 “상가정보 스냅샷상 관측 유지” 패턴을 어느 정도 설명하는지 |",
        "| 제한해야 하는 결론 | 창업 성공 확률, 매출액, 순이익, 실제 폐업 확률, 브랜드별 성공 가능성 |",
        "| 웹 표현 | 입지 적합도, 카페 입지 패턴 적합도, 현재 상권 패턴 기반 추천, 공공데이터 기반 후보지 점수, 입지 안정성 proxy 점수 |",
        "| 금지 표현 | 창업 성공 확률, 매출 예측, 폐업 예측, 이곳에 창업하면 성공 |",
        "",
        "## 6. Feature 설계와 누수 방지",
        "",
        "모든 feature는 시점 t 또는 t 이전 정보만 사용했다. t+6, t+12의 상가 수, 경쟁도, 업종 정보, 비용 정보는 feature에 넣지 않았다. 공시지가/실거래가는 시점별 정밀 매칭이 아니라 static cost proxy 성격으로 해석을 제한했다.",
        "",
        "| feature 그룹 | 예시 컬럼 | 해석 | 누수 방지 방식 |",
        "| --- | --- | --- | --- |",
        "| 상권 규모 proxy | `total_store_100m`, `total_store_300m`, `total_store_500m`, `total_store_1000m` | 주변 상가 밀집도 | 시점 t 스냅샷만 사용 |",
        "| 동일 업종 경쟁 proxy | `same_industry_*m_excl_self` | 같은 업종 주변 점포 수 | 자기 자신 제외, t 스냅샷만 사용 |",
        "| 업종 다양성 proxy | `industry_hhi_500m`, `industry_entropy_500m` | 주변 업종 혼합도 | t 스냅샷만 사용 |",
        "| 교통 접근성 proxy | `nearest_bus_m`, `bus_count_300m`, `nearest_subway_m` | 버스/도시철도 접근성 | 정적 공공데이터로 사용 |",
        "| 비용 부담 proxy | `land_price_mean_dong`, `transaction_price_*`, `cost_burden_proxy` | 공시지가/실거래가 기반 비용 부담 proxy | static cost proxy로 해석 제한 |",
        "| 점포 자체 변수 | `store_name_length`, `store_age_proxy_months` | 점포명/관측 시작 시점 기반 보조 변수 | 미래 시점 정보 제외 |",
        "",
        "## 7. 모델 검증 결과",
        "",
        "최종 대표 성능은 random split이 아니라 time split, spatial holdout, matched_store_id GroupKFold를 우선한다. 계산 시간을 통제하기 위해 모델 학습/검증은 타깃별 최대 30,000행 균형 샘플로 수행했다. 전체 라벨 데이터셋은 CSV로 보존했다.",
        "",
        "### 7.1 Time Split 결과",
        "",
        md(main_time),
        "",
        "### 7.2 Spatial Holdout 결과: 12개월 영업 유지 proxy, 각 자치구 holdout별 best model",
        "",
        md(spatial_best),
        "",
        "### 7.3 matched_store_id GroupKFold 결과: 12개월 영업 유지 proxy, fold별 best model",
        "",
        md(group_best),
        "",
        "### 7.4 전체 모델 메트릭",
        "",
        md(metrics[["target_report_name", "target", "split", "model", "rows", "positive_rate", "auroc", "pr_auc", "f1", "precision", "recall", "accuracy", "brier_score"]]),
        "",
        "### 7.5 Feature Importance",
        "",
        md(importance),
        "",
        "## 8. H2 경쟁 임계점 검증",
        "",
        "H2는 모델 feature importance가 아니라 동일 업종 경쟁도 구간별 6개월/12개월 영업 유지 proxy 비율로 검증했다.",
        "",
        md(competition),
        "",
        "## 9. H3 비용 부담 가설 검증",
        "",
        "H3는 비용 부담 proxy 분위수별 영업 유지 proxy 비율과 비용 변수 제거 ablation으로 검증했다. 비용 변수는 실제 임대료가 아니며 static cost proxy로 해석한다.",
        "",
        "### 9.1 비용 부담 proxy 분위수별 유지율",
        "",
        md(cost),
        "",
        "### 9.2 Ablation Study",
        "",
        md(ablation),
        "",
        "## 10. 반경 민감도 분석",
        "",
        "100m, 300m, 500m, 1000m feature set을 비교했다.",
        "",
        md(radius),
        "",
        "## 11. 업종별 성능/패턴 요약",
        "",
        md(industry_perf),
        "",
        "## 12. 자치구 요약",
        "",
        md(district),
        "",
        "## 13. 웹 데이터 계약",
        "",
        "웹용 JSON에는 성공확률, 폐업확률, 매출예측 의미의 필드명을 쓰지 않았다.",
        "",
        "| 구분 | 필드/표현 |",
        "| --- | --- |",
        "| 허용 필드명 | `retention_proxy_score`, `suitability_score`, `cost_burden_proxy`, `demand_proxy_score`, `competition_burden_score`, `accessibility_score`, `industry_fit_score`, `risk_level`, `positive_reasons`, `negative_reasons` |",
        "| 금지 필드명 | `success_probability`, `survival_probability`, `failure_probability`, `closure_probability`, `sales_prediction`, `revenue_prediction` |",
        "| 웹 권장 문구 | “이 점수는 창업 성공을 보장하지 않습니다.” |",
        "| 웹 권장 문구 | “상가정보 스냅샷상 관측 유지와 공공데이터 proxy를 기반으로 후보지를 비교하기 위한 1차 필터링 지표입니다.” |",
        "| 웹 권장 문구 | “실제 창업 판단에는 임대료, 권리금, 점포 내부 상태, 브랜드 전략, 실제 유동인구 등 추가 확인이 필요합니다.” |",
        "| 금지 표현 | 창업 성공 확률, 매출 예측, 폐업 예측, 이곳에 창업하면 성공 |",
        "",
        "### 13.1 웹 JSON 검증",
        "",
        md(
            pd.DataFrame(
                [
                    {"검증 항목": "금지 필드명 JSON 내 포함 여부", "결과": "통과" if not violations else "위반", "상세": "없음" if not violations else ", ".join(violations)},
                    {"검증 항목": "candidates.json 후보 수", "결과": len(candidates), "상세": "공공데이터 기반 후보지 점수"},
                    {"검증 항목": "industry_recommendations.json 추천 수", "결과": len(industry_recs), "상세": "격자별 top5 업종 추천"},
                ]
            )
        ),
        "",
        "## 14. 웹 후보지 데이터: candidates.json 전체 150건",
        "",
        md(candidates, cols=candidate_cols),
        "",
        "## 15. 웹 업종 추천 데이터: industry_recommendations.json 전체 100건 요약",
        "",
        md(industry_recs),
        "",
        "## 16. 산출물 전체 목록",
        "",
        md(output_inventory),
        "",
        "## 17. 최종 리스크 체크리스트",
        "",
        "| 리스크 | 현재 상태 | 대응 |",
        "| --- | --- | --- |",
        "| 실제 매출/폐업 데이터 부재 | 남아 있음 | 매출/폐업 표현 금지, 영업 유지 proxy로만 해석 |",
        "| 2024년 업종코드/업소번호 개편 가능성 | 별도 매칭률 보고 완료 | 2023-12→2024-06, 2024-06→2024-12 구간 별도 표기 |",
        "| 공간적으로 가까운 점포 간 유사성 | spatial holdout 수행 | random split 대표 성능 사용 금지 |",
        "| 동일 점포 반복 관측으로 인한 과대평가 | matched_store_id GroupKFold 수행 | GroupKFold 결과를 대표 검증 중 하나로 유지 |",
        "| 비용 변수의 시점 정합성 | static cost proxy로 제한 | 인과적 비용 효과라고 표현하지 않음 |",
        "| fuzzy matching 오매칭 가능성 | 85점 이상만 메인 라벨 사용, 70~84점 review로 분리 | review pair CSV 별도 보존 |",
        "",
        "## 18. 보고서에 바로 쓸 수 있는 최종 문장",
        "",
        "본 실험은 2022년 6월부터 2025년 12월까지의 광주광역시 상가정보 반기별 스냅샷을 이용해 점포의 “상가정보 스냅샷상 관측 유지”를 proxy label로 정의하고, 공공데이터 기반 입지·경쟁·교통·비용 부담 proxy 변수가 이 관측 유지 패턴을 어느 정도 설명하는지 검증했다. 12개월 영업 유지 proxy 기준 time split에서는 XGBoost가 AUROC 0.6460, PR-AUC 0.6277을 보였고, spatial holdout 및 matched_store_id GroupKFold에서는 AUROC가 대략 0.57~0.60 수준으로 나타났다. 따라서 본 결과는 실제 창업 성공이나 매출을 직접 예측한 것이 아니라, 공공데이터 기반으로 후보지를 1차 필터링하기 위한 의사결정 지원 지표로 해석해야 한다.",
        "",
        "## 19. 마지막 요약",
        "",
        "1. 현재 모델 결과를 신뢰해도 되는 정도: “창업 성공 예측”으로는 신뢰하면 안 되고, “공공데이터 기반 입지/관측 유지 proxy 1차 필터링”으로는 참고 가능하다.",
        "2. 가장 큰 리스크 3개: 실제 매출/폐업 데이터 부재, 2024년 데이터 체계 변경 가능성, 공간/동일 점포 반복 관측으로 인한 성능 과대평가 가능성.",
        "3. 추가 검증으로 반드시 해야 할 것 3개: 실제 매출·폐업·임대료 데이터 결합, 2024년 전후 매칭 샘플 수작업 검수, spatial holdout/GroupKFold를 확장한 외부 검증.",
        "4. 웹에서 써도 되는 표현: 창업 적합도, 입지 적합도, 카페 입지 패턴 적합도, 현재 상권 패턴 기반 추천, 공공데이터 기반 후보지 점수, 입지 안정성 proxy 점수.",
        "5. 웹에서 쓰면 안 되는 표현: 창업 성공 확률, 매출 예측, 폐업 예측, 이곳에 창업하면 성공, 예상 생존확률.",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)
    print(f"size_bytes={OUT.stat().st_size}")
    print("violations=" + ("none" if not violations else ", ".join(violations)))


if __name__ == "__main__":
    main()
