# GOAL_PROGRESS

## 2026-05-16 Kakao Map Integration v2

### 현재 상태

- `frontend/` React/Vite 앱을 유지했고 기존 `web/`은 수정하지 않았다.
- `frontend/.env`에 `VITE_KAKAO_MAP_KEY`, `VITE_API_BASE_URL` 형식을 준비했고, 사용자가 Kakao JavaScript key를 입력했다.
- `/map`은 Kakao SDK 우선 로드, 실패 시 광주 bounding box 기반 2D fallback map으로 전환된다.
- `grid_scores.json`은 전체 마커 표시용이 아니라 클릭 분석 lookup 데이터로 사용된다.
- 지도 마커는 제한 표시로 보정했다.
  - 전체 업종: `candidates_balanced.json` 상위 100개
  - 선택 업종: 해당 업종 후보와 상위 grid row를 합쳐 최대 40개
  - AI 상담: TOP 3 빨간 번호 마커
- 클릭 분석은 가장 가까운 `base_grid_id`를 찾고, 선택 업종 row가 있으면 그 row를 표시한다.
- 선택 업종 row가 없으면 같은 격자 안의 입지 적합도 TOP 5 중 1위를 분석 결과로 표시한다.
- grid 데이터가 없으면 기존 candidates 기반 가장 가까운 후보지 fallback으로 전환된다.

### 생성/변경 파일

- `frontend/src/components/FallbackMap.jsx`
- `frontend/src/components/KakaoMap.jsx`
- `frontend/src/pages/MapPage.jsx`
- `frontend/src/components/AnalysisPanel.jsx`
- `frontend/src/components/AiConsultPanel.jsx`
- `frontend/src/components/CandidateCard.jsx`
- `frontend/src/utils/geo.js`
- `frontend/src/utils/kakaoLoader.js`
- `frontend/src/utils/recommendation.js`
- `frontend/src/utils/industryLabel.js`
- `frontend/src/utils/safeText.js`
- `frontend/api/_aiPrompt.js`
- `server/aiPrompt.js`
- `frontend/src/styles.css`
- `GOAL_PROGRESS.md`
- `WEB_VERIFICATION_REPORT.md`
- `DATA_CONNECTION_REPORT.md`

### 테스트 결과

| 항목 | 결과 | 메모 |
|---|---:|---|
| `grid_scores.json` 로드 | 통과 | 3,454 row |
| `candidates_balanced.json` 로드 | 통과 | 160 row |
| grid `other` 제외 | 통과 | 0 row |
| 필수 좌표 존재 | 통과 | 누락 0 row |
| 금지 필드명 검사 | 통과 | public data 기준 없음 |
| grid-first 클릭 분석 함수 | 통과 | `analysisType=grid` |
| 기본 후보 마커 제한 | 통과 | 상위 100개 |
| cafe 후보 마커 제한 | 통과 | 후보 20개, grid 보조로 최대 40개 |
| frontend build | 통과 | `npm run build` |
| server syntax | 통과 | `server.js`, `aiPrompt.js` |
| server health | 통과 | `geminiConfigured=false` fallback 상태 |
| fallback map 표시 | 통과 | 로컬 `/map`에서 확인 |
| fallback map 빈 공간 클릭 | 통과 | grid 기반 분석 패널 갱신 |
| 분석 기준 표시 | 통과 | 500m 격자 기반, 선택 좌표, 거리 표시 |
| AI fallback 답변 | 통과 | API key 비활성 상태에서 rule-based 답변 |
| AI TOP 3 빨간 마커 | 통과 | 3개 표시 |

### Vercel 배포 checkpoint

- Vercel CLI가 Windows 한글 hostname을 HTTP header에 넣으며 오류가 나서, npx cache의 Vercel CLI user-agent hostname 부분을 ASCII로 정규화한 뒤 재시도했다.
- `npx vercel pull --yes --environment=production`: 통과
- `npx vercel build --prod`: 통과
- `npx vercel deploy --prebuilt --prod`: 통과
- Production URL: `https://frontend-3kty70x1v-si-hoon-parks-projects.vercel.app`
- Alias: `https://frontend-livid-pi-38.vercel.app`
- Inspector: `https://vercel.com/si-hoon-parks-projects/frontend/B7znqnjzq4S8RXQpeqtCaAAURX8U`
- Share URL: `https://frontend-3kty70x1v-si-hoon-parks-projects.vercel.app/?_vercel_share=gj9FOeS9wG5N8y6Yb5dmd1cgJanWO2Pz`
- Vercel MCP fetch 검증:
  - `/`: 200
  - `/map`: 200
  - `/api/health` with share token: 200, `geminiConfigured=false`
- 일반 HTTP fetch는 Vercel Authentication 보호로 401이 나온다.

### 남은 문제

- 로컬 Kakao SDK는 key가 설정되어 있어도 현재 검증 환경에서는 fallback map으로 전환되었다. Kakao Developers의 JavaScript 도메인에 `http://127.0.0.1:5174`, `http://localhost:5174`, 배포 도메인을 등록한 뒤 재확인이 필요하다.
- 5173 포트는 로컬 `postgres.exe`가 사용 중이라 브라우저 검증은 5174에서 진행했다. 서버 CORS는 5173과 5174를 모두 허용한다.
- Vercel 환경의 Gemini/Gemma API key는 아직 설정되지 않아 배포 환경 AI API는 rule-based fallback으로 동작한다.

## 2026-05-16 Kakao SDK activation checkpoint

### 현재 상태

- Kakao Developers 도메인 등록 및 Kakao Map 사용 설정 이후 SDK 요청이 정상화됐다.
- 직접 SDK 요청 확인 결과:
  - `http://localhost:5174`: 200
  - `http://127.0.0.1:5174`: 200
  - `https://frontend-livid-pi-38.vercel.app`: 200
  - `https://frontend-3kty70x1v-si-hoon-parks-projects.vercel.app`: 200
- 로컬 `/map` 브라우저 검증 결과:
  - fallback map 미표시
  - Kakao map container 표시
  - Kakao 지도 클릭 후 500m grid 기반 분석 패널 갱신 확인
- 최신 frontend build 통과.
- Vercel prebuilt production deploy 통과.

### 최신 배포 정보

- Production URL: `https://frontend-ewofqcaeb-si-hoon-parks-projects.vercel.app`
- Stable alias: `https://frontend-livid-pi-38.vercel.app`
- Inspector: `https://vercel.com/si-hoon-parks-projects/frontend/AHNHwJ9AcgVWDsrndJvaxaXxGuhE`
- Share URL: `https://frontend-livid-pi-38.vercel.app/?_vercel_share=ps3gktlxPZhXjN4IuBzFxb30YmBq4cpm`
- Vercel MCP fetch 검증:
  - `https://frontend-livid-pi-38.vercel.app/map`: 200
  - `https://frontend-livid-pi-38.vercel.app/api/health`: 200, `geminiConfigured=false`

### 남은 주의사항

- Vercel의 고유 deployment URL은 배포마다 바뀐다. Kakao 도메인은 안정적인 alias인 `https://frontend-livid-pi-38.vercel.app` 중심으로 사용하는 것이 좋다.
- 배포 환경 AI API는 아직 `GEMINI_API_KEY`가 없어 fallback 답변을 사용한다.

## 2026-05-17 Gemma API checkpoint

### 현재 상태

- root `.env`의 `GEMINI_API_KEY`는 설정되어 있고, `GEMMA_MODEL=gemma-4-31b-it`를 사용한다.
- Google Generative Language API 모델 목록에서 `models/gemma-4-31b-it`와 `generateContent` 지원을 확인했다.
- 로컬 Express `/api/health`:
  - `geminiConfigured=true`
  - `model=gemma-4-31b-it`
- 로컬 Express `/api/ai/recommend`:
  - `fallback=false`
  - Gemma 응답 정상 반환
- Gemma 응답의 `thought: true` 파트가 최종 답변에 섞이지 않도록 서버 응답 파서를 수정했다.
- Vercel production 환경변수에 `GEMINI_API_KEY`, `GEMMA_MODEL`를 추가했다.
- Vercel production 재배포 완료.
- 배포 API `/api/health`:
  - `geminiConfigured=true`
  - `model=gemma-4-31b-it`
- 배포 API `/api/ai/recommend`:
  - `fallback=false`
  - Gemma 응답 정상 반환

### 변경 파일

- `server/server.js`
- `frontend/api/ai/recommend.js`
- `frontend/src/components/AiConsultPanel.jsx`
- `GOAL_PROGRESS.md`

### 배포 정보

- Production URL: `https://frontend-9p0ye8xve-si-hoon-parks-projects.vercel.app`
- Stable alias: `https://frontend-livid-pi-38.vercel.app`
- Inspector: `https://vercel.com/si-hoon-parks-projects/frontend/5qXfQ9336myVNyRBikvsmC3GZCrV`

### 주의사항

- production frontend는 localhost API를 사용하지 않고 same-origin `/api/ai/recommend`를 사용하도록 보정했다.
- Gemma API는 응답 시간이 수십 초 걸릴 수 있다. UI에서는 로딩 상태를 유지한다.
