# DATA CONNECTION REPORT

## 데이터 연결 요약

v9 웹 데이터는 v8 실험 산출물을 기반으로 만든다. 후보지 추천 목록은 `data/v8/analysis/feature_store_level.csv`의 최신 스냅샷 `20251231`을 기준으로 만들었고, 웹 표시는 `frontend/public/data/candidates_balanced.json`과 `frontend/public/data/grid_scores.json`을 사용한다.

이번 Kakao Map Integration v2에서는 두 데이터의 역할을 분리했다.

- `candidates_balanced.json`: 지도 기본 마커, 좌측 후보 목록, AI TOP 3 상담 후보
- `grid_scores.json`: 지도 클릭 위치를 분석하기 위한 500m 상권 격자 lookup 데이터

## 후보지 방식

기존 후보지 방식은 미리 계산된 후보지 row를 표시하고, 사용자가 후보지나 마커를 선택하면 해당 row의 점수와 사유를 보여준다.

- 장점: AI 상담 TOP 3와 후보 카드 설명에 바로 연결된다.
- 한계: 사용자가 빈 위치를 클릭했을 때 “그 위치 주변” 분석처럼 보이기 어렵다.
- 현재 용도: 기본 마커, 후보 카드, grid 데이터 부재 시 fallback

## grid_scores 방식

`grid_scores.json`은 광주 상권 데이터를 500m 격자로 요약한 lookup 데이터다. 실시간 공간 계산이나 실시간 모델 학습을 하지 않고, 미리 계산된 격자 점수를 조회한다.

클릭 분석 순서는 다음과 같다.

1. 사용자가 지도 또는 fallback pseudo-map을 클릭한다.
2. 클릭 좌표에서 가장 가까운 `base_grid_id`를 찾는다.
3. 해당 격자에 선택 업종 row가 있으면 그 row를 분석 결과로 표시한다.
4. 선택 업종 row가 없으면 같은 격자의 입지 적합도 TOP 5 중 1위를 분석 결과로 표시한다.
5. 같은 격자 데이터가 없거나 `grid_scores.json`이 비어 있으면 `candidates_balanced.json`에서 가장 가까운 후보지로 fallback한다.
6. 클릭 위치와 분석 중심점 거리가 1km 이상이면 가장 가까운 분석 격자 참고 안내를 표시한다.

## 지도 마커 표시 정책

`grid_scores.json`은 업종별 row 수가 많으므로 전체를 지도 마커로 표시하지 않는다.

- 기본 표시: balanced candidate 상위 100개
- 업종 필터 표시: 선택 업종 후보와 상위 grid row를 합쳐 최대 40개
- AI 상담 표시: TOP 3 빨간 번호 마커
- grid 전체 row: 클릭 분석 lookup으로만 사용

이 정책은 지도 가독성과 렌더링 성능을 유지하기 위한 것이다.

## fallback map 좌표 생성

Kakao SDK가 로드되지 않으면 `FallbackMap`이 광주 bounding box 기반 2D pseudo-map을 보여준다.

- 화면의 x/y 클릭 비율을 광주 위경도 범위로 변환한다.
- 변환된 좌표를 Kakao 지도 클릭과 같은 `handleMapClick` 로직에 전달한다.
- 따라서 Kakao key가 없어도 grid-first 클릭 분석, 후보 fallback, AI TOP 3 마커가 동작한다.

## grid_scores 생성 방법

- 입력 파일: `data/v8/analysis/feature_store_level.csv`
- 기준 시점: `20251231`
- 격자 크기: 500m
- 출력 파일: `frontend/public/data/grid_scores.json`
- 생성 결과: 3,454 row
- 사용자 표시 업종: cafe, dessert_bakery, restaurant_general, bunsik, chicken, convenience_store, beauty_hair, laundry
- 제외: `other`, 좌표 누락 row, 광주 범위 밖 row

좌표 변환은 현재 로컬 환경에서 `lat/lng approximate 500m bin` 방식으로 기록되어 있다. 이는 시연과 1차 후보지 필터링 목적에는 충분하지만, 행정구역 경계를 완전히 채우는 정밀 격자 생성 방식은 아니다.

## “광주 전체 상권 격자” 표현의 한계

`grid_scores.json`은 광주 행정구역 전체의 모든 빈 격자를 생성한 자료가 아니다. 상가 데이터가 존재하는 commercial grid만 포함한다.

따라서 산지, 하천, 주거지 일부, 상가 데이터가 적은 빈 구역을 클릭하면 해당 위치 자체의 독립 점수가 아니라 가장 가까운 상권 격자 또는 후보지 fallback 결과가 표시된다.

이 fallback을 유지하는 이유는 다음과 같다.

- 빈 구역 클릭에서도 `/map` 핵심 흐름이 멈추지 않는다.
- 사용자는 클릭 위치 주변에서 참고 가능한 가장 가까운 분석 단위를 볼 수 있다.
- `grid_scores.json` 생성 실패 또는 누락 상황에서도 후보지 분석 기능을 유지할 수 있다.
