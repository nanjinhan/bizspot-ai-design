# WEB VERIFICATION REPORT

## 검증 요약

BizSpot AI v9 `/map`은 `frontend/` React/Vite 앱에서 동작한다. 기존 정적 `web/`은 레거시로 보존했고, 동일 기능을 중복 구현하지 않았다.

이번 보정으로 지도는 Kakao SDK를 우선 시도하고, 로드되지 않으면 광주 bounding box 기반 2D fallback map으로 전환된다. `grid_scores.json`은 전체 마커용이 아니라 클릭 분석 lookup 데이터로 사용된다.

## 실제 구현 완료

- `frontend/` Vite React 앱 유지
- `/map` Kakao SDK 우선 로딩
- `FallbackMap` 분리 구현
- fallback map의 x/y 클릭 좌표를 광주 위경도로 변환
- grid-first 클릭 분석
- 선택 업종 row 우선 표시
- 선택 업종 row 부재 시 같은 격자 TOP 5 중 1위 표시
- grid 데이터 부재 시 candidates fallback 유지
- 기본 후보 마커 상위 100개 제한
- 업종 필터 마커 최대 40개 제한
- AI 상담 TOP 3 빨간 번호 마커 유지
- 로컬 Express API와 Vercel serverless API 구조 분리
- API key 부재 또는 호출 실패 시 rule-based fallback 답변
- 분석 패널에 분석 기준, 선택 좌표, 분석 격자, 거리 표시
- 지정 금지 표현과 금지 필드명 정적 검사

## fallback으로 동작

- Kakao SDK가 로드되지 않으면 2D fallback map으로 동작한다.
- AI API key가 없거나 요청이 실패하면 로컬 JSON 기반 rule-based 답변을 표시한다.
- `grid_scores.json`이 없거나 클릭 위치에 활용 가능한 격자가 없으면 `candidates_balanced.json` 기반 후보지 fallback을 사용한다.
- 로컬 5173 포트가 사용 중이라 검증은 5174에서 수행했다. 서버 CORS는 5173과 5174를 모두 허용한다.

## mock 또는 제한적 구현

- `grid_scores.json`은 상가 데이터가 존재하는 commercial grid만 포함한다.
- 500m 격자는 현재 산출물 기준 `lat/lng approximate 500m bin` 방식으로 생성된 자료다.
- Kakao key는 설정되어 있으나 현재 로컬 검증 환경에서는 SDK 지도가 아닌 fallback map이 표시되었다. Kakao Developers 도메인 설정 확인이 필요하다.
- AI는 후보지를 새로 만들지 않고 로컬 JSON의 TOP 3 후보 설명만 수행한다.
- 신규 점포 관측 유지 관련 결과는 추천 점수에 쓰지 않고 한계 인사이트로만 표시한다.

## 테스트 결과

| 항목 | 결과 | 메모 |
|---|---:|---|
| `grid_scores.json` 생성/로드 | 통과 | 3,454 row |
| `grid_scores.json` 사용자 표시 업종 | 통과 | `other` 없음 |
| `grid_scores.json` 좌표 필드 | 통과 | 누락 0 row |
| `candidates_balanced.json` 좌표 필드 | 통과 | 누락 0 row |
| 금지 필드명 검사 | 통과 | 웹 데이터 기준 없음 |
| 지정 금지 표현 검사 | 통과 | `src`, `api`, `public/data` 기준 없음 |
| frontend build | 통과 | `npm run build` |
| server syntax | 통과 | `server.js`, `aiPrompt.js` |
| API health | 통과 | `geminiConfigured=false` fallback 상태 |
| `/map` 로컬 로딩 | 통과 | `http://127.0.0.1:5174/map` |
| fallback map 표시 | 통과 | Kakao SDK 로드 실패 시 표시 |
| fallback map 빈 공간 클릭 | 통과 | grid 기반 분석으로 패널 갱신 |
| grid 기반 분석 우선 | 통과 | `analysisType=grid` |
| 분석 기준 패널 | 통과 | 500m 격자 기반, 좌표, 거리 표시 |
| AI fallback 답변 | 통과 | rule-based 답변 표시 |
| AI TOP 3 빨간 마커 | 통과 | 3개 표시 |
| marker 제한 정책 | 통과 | 전체 100개, 업종 최대 40개 |
| Vercel production deploy | 통과 | Ready |
| Vercel `/` fetch | 통과 | Vercel MCP 기준 200 |
| Vercel `/map` fetch | 통과 | Vercel MCP 기준 200 |
| Vercel `/api/health` fetch | 통과 | share token 포함 200 |
| Kakao SDK 직접 요청 | 통과 | localhost, 127.0.0.1, stable alias 200 |
| Kakao 지도 로컬 렌더링 | 통과 | fallback 미표시, Kakao map container 표시 |
| Kakao 지도 클릭 분석 | 통과 | 500m grid 기반 분석 패널 갱신 |
| 로컬 Gemma API health | 통과 | `geminiConfigured=true` |
| 로컬 Gemma 추천 API | 통과 | `fallback=false` |
| Vercel Gemma API health | 통과 | `geminiConfigured=true` |
| Vercel Gemma 추천 API | 통과 | `fallback=false` |

## 배포 상태

- Production URL: `https://frontend-9p0ye8xve-si-hoon-parks-projects.vercel.app`
- Alias: `https://frontend-livid-pi-38.vercel.app`
- Inspector: `https://vercel.com/si-hoon-parks-projects/frontend/5qXfQ9336myVNyRBikvsmC3GZCrV`
- Share URL: `https://frontend-livid-pi-38.vercel.app/?_vercel_share=ps3gktlxPZhXjN4IuBzFxb30YmBq4cpm`

Vercel MCP fetch로 stable alias의 `/map`, `/api/health`를 검증했다.

## 남은 한계

- Kakao SDK 실지도 검증은 로컬 `http://127.0.0.1:5174/map`에서 통과했다.
- Vercel production 환경변수에 AI key가 설정되어 배포 환경에서도 Gemma 응답이 동작한다.
- 비용 부담 proxy는 실제 월세가 아니므로 비용 해석은 제한적이다.
- 본 웹은 공공데이터 기반 1차 후보지 필터링과 의사결정 지원 도구로 사용해야 한다.

## 완료 조건 평가

- `grid_scores.json` 생성: 완료
- `/map` 클릭 시 grid 기반 분석 우선 동작: 완료
- grid 실패 시 candidates fallback 유지: 완료
- AI 상담 TOP 3 빨간 마커 유지: 완료
- grid 관련 테스트 결과 문서 기록: 완료
- Vercel 재배포 검증: 완료
- Kakao SDK 실제 지도 렌더링 검증: 완료
- Gemma API 실제 응답 검증: 완료
