# BizSpot AI Plan Report

## 1. 현재 발견한 데이터 파일 목록

- D0 법정동코드: `법정동코드 조회자료 (2)~(6).zip`
- D1 상가정보: `소상공인시장진흥공단_상가(상권)정보_20260331.zip`, 중복본 `(1).zip`
- D2 업종코드: `소상공인시장진흥공단_상가(상권)정보 업종코드_20230228 (1).csv`
- D3 건축물대장정보: 로컬 원본 없음, OpenAPI 사용 가능
- D4 상업업무용 실거래가: 로컬 원본 없음, OpenAPI 사용 가능
- D5 개별공시지가: `AL_D151_29_20260210.zip` CSV, `AL_D150_29_20260210.zip` SHP
- D6 교통: `광주광역시_정류소_20241231.csv`, `국토교통부_전국_버스정류장_위치정보_20251031.csv`
- D7 도시철도: `광주교통공사_문화노선도 현황_20221202.csv`
- D8 유동인구: 없음

## 2. D0~D8 자동 매핑 추정

| ID | 데이터 | 사용 방식 |
|---|---|---|
| D0 | 법정동코드 XLSX ZIP | 광주 5개 자치구 법정동 기준 테이블 |
| D1 | 상가정보 ZIP 내부 광주 CSV | 단일 시점 proxy 입지 검증의 핵심 데이터 |
| D2 | 업종코드 CSV | 생활밀착 업종/카페 플래그 생성 |
| D3 | 건축물대장 OpenAPI | 선택 수집, 실패 시 제외하고 리포트 기록 |
| D4 | 상업업무용 실거래가 OpenAPI | 비용 부담 proxy, 실패 시 공시지가로 대체 |
| D5 | 개별공시지가 CSV/SHP | 법정동/자치구 비용 proxy |
| D6 | 버스정류장 CSV | 광주 파일에 좌표가 없으면 전국 좌표 데이터로 대체 |
| D7 | 도시철도역 CSV | 역 접근성 변수 |
| D8 | 없음 | 상가 밀도, 교통, 공시지가, 건물 용도 proxy로 대체 |

## 3. 인코딩, 압축, 용량, 컬럼 확인 계획

- CSV 인코딩은 `utf-8-sig`, `utf-8`, `cp949`, `euc-kr`, `latin1` 순서로 시도한다.
- 상가 ZIP은 전국 전체를 풀지 않고 내부 `광주_202603.csv`만 읽는다.
- 공시지가 CSV는 `cp949`로 확인되었고, `법정동코드`, `공시지가` 컬럼을 우선 사용한다.
- 광주 정류소 파일은 좌표가 없어 보이므로 전국 버스정류장 좌표 파일을 fallback으로 쓴다.

## 4. 데이터별 전처리 방법

- D0: XLSX를 읽어 광주 5개 자치구, 현존 법정동만 남긴다.
- D1: 광주 상가만 유지하고 좌표 결측/이상치/중복을 제거한다.
- D2: 업종명을 rule-based로 카페, 음식점, 편의점, 생활서비스 등으로 매핑한다.
- D3: API 키가 있으면 제한된 범위에서 캐시 수집하고, 실패하면 건축물 변수 없이 진행한다.
- D4: 2020~2026년 월별/구별 실거래 API를 호출해 법정동 또는 자치구 단위 비용 proxy로 집계한다.
- D5: 광주 법정동코드 기준으로 공시지가를 집계한다.
- D6: 좌표가 있는 전국 버스정류장에서 광주만 필터링한다.
- D7: 역 위도/경도를 표준화한다.
- D8: optional로 두고 실패 처리하지 않는다.

## 5. 광주 5개 자치구 필터링 기준

- 시군구코드 앞 5자리: `29110`, `29140`, `29155`, `29170`, `29200`
- 또는 시도명 `광주광역시`
- 또는 좌표 bounding box: 위도 34.9~35.4, 경도 126.5~127.2

## 6. 피처 생성 계획

- 500m 격자 단위 후보지를 만들고, 격자 내 상가/카페/생활밀착 업종 카운트를 계산한다.
- 좌표는 EPSG:4326 원본을 보존하고, 거리 계산은 근사 meter 좌표로 변환한다.
- 버스/지하철 최근접 거리와 반경 내 개수를 계산한다.
- 공시지가와 실거래가는 법정동/자치구 단위로 결합한다.
- target leakage를 피하기 위해 카페 수는 target으로 쓰고, feature에는 총 상가 수, 타 업종 다양성, 교통, 비용 proxy를 사용한다.

## 7. 모델 검증 목표

- 단일 시점 데이터이므로 생존예측이 아니라 `has_target_industry` proxy 입지 패턴 설명 모델로 검증한다.
- Logistic Regression, Random Forest, XGBoost를 비교하고 LightGBM은 설치되어 있을 때만 사용한다.
- AUROC, F1, Precision, Recall, Accuracy를 기록한다.
- SHAP이 실패하면 permutation importance 또는 model feature importance로 대체한다.

## 8. 실제 생존 라벨 가능/불가능 분기

- 현재 로컬 상가정보는 2026년 3월 단일 스냅샷으로 판단된다.
- 따라서 A안 생존/폐업 라벨은 사용하지 않는다.
- B안 격자 기반 업종 입지 proxy 모델과 후보지 점수 검증으로 진행한다.

## 9. D8 유동인구 데이터 부재 대체 전략

유동인구 데이터가 확보되지 않았기 때문에 본 프로젝트는 실제 유동인구를 직접 사용하지 않고, 전체 상가 밀도·대중교통 접근성·공시지가·건물 용도 등을 수요 가능성의 대리변수로 사용한다.

## 10. 웹 구현 범위

- 정적 HTML/CSS/JS 기반 대시보드
- 후보지 TOP 50, 자치구 요약, 모델 성능, feature importance 표시
- 지도 CDN이 실패해도 카드형/격자형 대시보드가 보이도록 구성

## 11. 산출물 목록

- `config/data_manifest.yaml`
- `outputs/reports/data_file_scan.md`
- `data/processed/*.csv`
- `data/analysis/feature_dataset.csv`, `modeling_dataset.csv`, `candidates_scored.csv`
- `outputs/tables/model_metrics.csv`, `feature_importance.csv`, `top_candidates.csv`, `district_summary.csv`
- `outputs/reports/data_quality_report.md`, `model_validation_report.md`, `experiment_summary.md`
- `web/index.html`, `web/styles.css`, `web/app.js`, `web/data/*.json`

## 12. 예상 리스크와 대응

- API 오류 또는 키 제한: 캐시/로컬 파일 기반으로 fallback
- 공간 라이브러리 부재: pandas와 scikit-learn 기반 meter 근사 계산 사용
- 광주 정류소 좌표 부재: 전국 버스정류장 위치정보 사용
- 단일 시점 데이터: 생존예측 표현 금지, proxy 모델로 명확히 표시
- 실거래가/공시지가 해석 과장 위험: 비용 부담 proxy로만 표현

## 13. 실행 순서와 명령어

```bash
python scripts/run_all.py --mode scan
python scripts/run_all.py --mode preprocess
python scripts/run_all.py --mode features
python scripts/run_all.py --mode model
python scripts/run_all.py --mode web
python scripts/run_all.py --mode report
python scripts/run_all.py --mode all
```

## 14. 검증 체크리스트

- [ ] 광주 상가정보 행 수와 좌표 품질이 확인되었는가?
- [ ] D8 없음이 실패가 아니라 proxy 전략으로 반영되었는가?
- [ ] target leakage 없이 proxy target을 만들었는가?
- [ ] 모델 성능이 과장 없이 해석되었는가?
- [ ] 웹에서 창업 성공 보장이 아니라 1차 필터링 지표라고 안내하는가?

## 15. STOP AND VALIDATE 보강 계획

현재 단계에서는 추가 기능 구현을 중단하고, 이미 생성된 결과의 검증 가능성과 해석 안전성을 보강한다. 검증의 초점은 높은 AUROC가 실제 예측력을 뜻하는지, 또는 target 정의와 공간적 분할 방식 때문에 과대평가되었을 가능성이 있는지를 확인하는 것이다.

### 현재 결과 요약

| 항목 | 현재 값 |
|---|---:|
| 광주 상가 데이터 수 | 75,325 |
| 공시지가 데이터 수 | 385,848 |
| 버스정류장 데이터 수 | 8,655 |
| 도시철도역 데이터 수 | 20 |
| 후보지 격자 수 | 984 |
| Logistic Regression AUROC / F1 | 0.9651 / 0.8932 |
| Random Forest AUROC / F1 | 0.9793 / 0.9151 |
| XGBoost AUROC / F1 | 0.9758 / 0.9309 |
| Spearman 상관계수 | 0.8548 |
| 상위 20% 후보지 평균 카페 수 | 10.431 |
| 하위 20% 후보지 평균 카페 수 | 0.000 |

### 타깃 정의 검증

- target column 이름은 `has_target_industry`이다.
- target은 500m 격자 안에 현재 카페로 분류된 점포가 1개 이상 있으면 1, 없으면 0으로 생성했다.
- 이 target은 실제 생존, 폐업, 매출, 수익성 데이터가 아니다.
- 이 target은 현재 광주 카페 밀집/입지 패턴을 기반으로 만든 proxy label이다.
- 본 결과는 실제 창업 성공이나 매출을 직접 예측한 것이 아니라, 현재 광주 카페 입지 패턴을 공공데이터 proxy 변수로 설명할 수 있는지를 검증한 결과이다.

### 데이터 누수 및 과대평가 위험

| 점검 항목 | 위험도 | 현재 상태 | 개선 방안 |
|---|---|---|---|
| target 생성에 사용된 변수가 feature에 그대로 들어갔는가? | 중간 | 모델 feature에는 `target_industry_count`를 직접 넣지 않았다. 다만 전체 상가 수와 업종 다양성은 같은 상가 원천에서 계산되어 target과 강하게 연결될 수 있다. | `target_industry_count`, 동일 업종 밀도, 카페 포함 다양성 변수를 제거한 leakage-free feature set으로 재학습한다. |
| 현재 카페 수, 카페 밀도, 동일 업종 수가 target과 feature 양쪽에 동시에 사용되었는가? | 중간~높음 | 모델 feature에는 직접 사용하지 않았지만, 후보지 점수 산식의 `competition_score`는 현재 카페 수 기반이다. | 모델 검증용 feature와 웹 점수 산식을 분리하고, 검증 실험에서는 카페 수 기반 점수 변수를 제외한다. |
| train/test split이 random split이라 공간적으로 가까운 격자가 train과 test에 동시에 들어갔는가? | 높음 | 현재 결과는 random split 기반이다. 인접 격자의 상권 구조가 비슷해 성능이 과대평가될 수 있다. | 자치구 holdout 또는 공간 블록 holdout으로 재검증한다. |
| 같은 행정동/격자 주변 데이터가 중복되어 성능이 과대평가될 가능성이 있는가? | 높음 | 500m 격자는 주변 생활권이 겹치며, 같은 행정동 내 격자가 train/test에 섞일 수 있다. | 행정동 또는 자치구 단위 GroupKFold를 추가한다. |
| 후보지 생성 기준이 target과 직접 연결되어 있는가? | 중간 | 후보지는 상가가 존재하는 격자 중심으로 생성되어 완전한 비상권/무상가 격자는 빠졌다. | 광주 전체 영역의 빈 격자까지 포함한 후보지 풀로 민감도 분석을 수행한다. |

### 추가 검증 실험

1. Random split 결과와 Spatial holdout 결과를 비교한다.
2. Leakage-free feature set으로 재학습한다.
3. 단순 규칙 모델, Logistic Regression, Random Forest, XGBoost를 같은 split에서 비교한다.
4. 경쟁 변수, 교통 변수, 공시지가 변수, 건물 변수를 제거하는 ablation study를 수행한다.
5. 후보지 점수와 현재 카페 수의 Spearman 상관, 상위 20% vs 하위 20% 평균 카페 수 차이를 다시 확인한다.

### 현재 결과의 안전한 해석

공공데이터만으로도 광주 카페 입지 패턴을 상당 부분 설명할 가능성은 확인했다. 그러나 이는 실제 창업 성공, 매출, 폐업률을 직접 예측한 결과가 아니다. 따라서 본 프로젝트의 모델은 창업 성공 예측기가 아니라 입지 후보지를 1차로 필터링하는 의사결정 지원 도구로 사용해야 한다.

`PLAN ONLY 완료: 위 계획을 검토한 뒤 IMPLEMENT MODE로 진행할지 결정하세요.`
