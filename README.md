# BizSpot AI

BizSpot AI는 모델 검증을 먼저 수행하고, 그 결과를 지도형 웹서비스로 보여주는 광주 소상공인 창업 입지 분석 시스템입니다. 좋은 상권이 곧 창업하기 좋은 상권은 아니라는 문제의식에서 출발해, 수요·경쟁·비용·접근성·업종 궁합의 균형을 데이터로 확인합니다.

## 데이터 목록
- D0 법정동코드
- D1 소상공인시장진흥공단 상가정보
- D2 상가정보 업종코드
- D3 국토교통부 건축HUB 건축물대장정보 서비스
- D4 국토교통부 상업업무용 부동산 매매 실거래가 자료
- D5 개별공시지가
- D6 버스정류장
- D7 광주 도시철도
- D8 유동인구: 미확보, proxy 대체

## 설치 방법
```bash
python -m pip install -r requirements.txt
```

## .env 설정 방법
`.env.example`을 참고해 로컬에 `.env`를 만들고 `DATA_GO_KR_SERVICE_KEY`를 설정한다. API 키는 코드나 Git에 넣지 않는다.

## 실행 방법
```bash
python scripts/run_all.py --mode scan
python scripts/run_all.py --mode preprocess
python scripts/run_all.py --mode features
python scripts/run_all.py --mode model
python scripts/run_all.py --mode web
python scripts/run_all.py --mode report
python scripts/run_all.py --mode all
```

## 산출물 위치
- 전처리: `data/processed/`
- 분석 데이터: `data/analysis/`
- 표/그림/보고서: `outputs/`
- 웹 대시보드: `web/index.html`

## 모델 검증 방식
단일 시점 데이터이므로 창업 성공이나 생존 예측이 아니라 현재 카페 입지 패턴을 설명하는 proxy 모델로 검증한다.

## 웹 실행 방법
정적 파일이므로 `web/index.html`을 브라우저에서 열면 된다. 일부 브라우저의 로컬 JSON 제한이 있으면 `python -m http.server 8000 -d web`으로 실행한다.

## 한계와 주의사항
- 이 점수는 창업 성공을 보장하지 않는다.
- 유동인구 데이터가 없어 수요 가능성은 proxy로 계산했다.
- 비용 부담은 실제 월세가 아니라 공시지가와 상업용 거래 수준 기반 proxy다.
- SHAP/feature importance는 모델 판단 근거이지 인과관계 증명이 아니다.

## 주요 출처
- 행정안전부 법정동코드: https://www.code.go.kr/stdcode/regCodeL.do
- 상가정보 파일/API: https://www.data.go.kr/data/15083033/fileData.do, https://www.data.go.kr/data/15012005/openapi.do
- 업종코드: https://www.data.go.kr/data/15067631/fileData.do
- 건축물대장정보: https://www.data.go.kr/data/15134735/openapi.do
- 상업업무용 실거래가: https://www.data.go.kr/data/15126463/openapi.do
- 버스정류장: https://www.data.go.kr/data/15067528/fileData.do
- 광주 도시철도: https://www.data.go.kr/data/15109340/fileData.do