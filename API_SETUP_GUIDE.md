# API SETUP GUIDE

## Frontend 환경변수

`frontend/.env`에 아래 값을 둔다.

```env
VITE_KAKAO_MAP_KEY=YOUR_KAKAO_JAVASCRIPT_KEY
VITE_API_BASE_URL=http://localhost:8787
```

Vite에서 브라우저로 노출되는 환경변수는 반드시 `VITE_` prefix가 필요하다. Kakao 지도에는 Kakao Developers의 **JavaScript 키**를 사용한다.

Kakao SDK가 로드되지 않으면 `/map`은 자동으로 2D fallback map을 사용한다.

## Kakao Developers 도메인 설정

Kakao JavaScript key를 넣어도 지도가 뜨지 않으면 Kakao Developers 콘솔에서 JavaScript 도메인을 확인한다.

로컬 검증용 권장 등록값:

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:5174`
- `http://127.0.0.1:5174`

배포 검증용 권장 등록값:

- `https://frontend-livid-pi-38.vercel.app`
- 현재 고유 deployment URL을 직접 열어야 한다면 해당 URL도 추가한다.

도메인 등록 전에는 fallback map이 표시될 수 있으며, 이 경우에도 grid 기반 클릭 분석은 동작한다.

## Local AI Server 환경변수

로컬 Express 서버는 `server/.env` 또는 repo root `.env`에서 아래 값을 읽는다.

```env
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_API_KEY
GEMMA_MODEL=gemma-4-31b-it
PORT=8787
```

API key가 없거나 모델 호출이 실패해도 서버는 로컬 JSON 기반 fallback 답변을 반환한다.

## Vercel 배포 환경변수

배포 환경은 `frontend/api` serverless functions를 사용한다. Vercel 프로젝트 환경변수에 아래 값을 넣으면 배포 환경에서도 모델 호출을 사용할 수 있다.

```env
GEMINI_API_KEY=YOUR_GOOGLE_AI_STUDIO_API_KEY
GEMMA_MODEL=gemma-4-31b-it
```

현재 배포 환경의 `/api/health`는 `geminiConfigured=true`로 확인되었고, AI 상담은 Gemma API 응답을 사용한다.

## 실행 순서

데이터 생성:

```powershell
python scripts\prepare_v9_web_data.py
```

서버 실행:

```powershell
cd server
npm run dev
```

프론트엔드 실행:

```powershell
cd frontend
npx vite --host 127.0.0.1 --port 5174
```

기본 개발 포트는 5173이지만, 현재 로컬에서는 5173을 다른 프로세스가 사용 중이라 검증은 5174에서 진행했다. 서버 CORS는 5173과 5174를 모두 허용한다.

## Vercel 배포 URL

- Production URL: `https://frontend-9p0ye8xve-si-hoon-parks-projects.vercel.app`
- Stable alias: `https://frontend-livid-pi-38.vercel.app`
- Inspector: `https://vercel.com/si-hoon-parks-projects/frontend/5qXfQ9336myVNyRBikvsmC3GZCrV`
- Share URL: `https://frontend-livid-pi-38.vercel.app/?_vercel_share=ps3gktlxPZhXjN4IuBzFxb30YmBq4cpm`

고유 deployment URL은 배포마다 바뀌므로 Kakao 도메인 등록과 시연은 stable alias를 기준으로 진행하는 것이 좋다.

## 안전 동작

- AI는 로컬 JSON에서 선택된 TOP 3 후보만 설명한다.
- AI는 후보지, 좌표, 점수, 순위를 새로 만들지 않는다.
- 웹 데이터 필드명은 `retention_proxy_score`, `suitability_score`, `cost_burden_proxy`처럼 안전한 이름만 사용한다.
- `new_store_survived_12m`는 추천 점수에 사용하지 않고 한계 인사이트로만 표시한다.
