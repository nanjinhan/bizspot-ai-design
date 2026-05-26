const SAFE_NOTICE =
  '이 답변은 상가정보 스냅샷상 관측 유지와 공공데이터 proxy를 기반으로 후보지를 비교하기 위한 1차 후보지 필터링 참고 지표입니다. 실제 창업 판단에는 임대료, 권리금, 점포 내부 상태, 브랜드 전략, 실제 유동인구 등 추가 확인이 필요합니다.'

const FORBIDDEN_REPLACEMENTS = [
  [['창업', '성공', '확률'], '입지 적합도'],
  [['성공', '확률'], '입지 적합도'],
  [['매출', '예측'], '업무 관련 확장 검토'],
  [['폐업', '예측'], '관측 유지 proxy 참고'],
  [['실제', '생존확률'], '영업 유지 proxy 점수'],
  [['예상', '생존확률'], '영업 유지 proxy 점수'],
  [['이곳에', '창업하면', '성공'], '후보지로 검토할 수 있음'],
]

function patternFromParts(parts) {
  return new RegExp(parts.join('\\s*'), 'g')
}

function sanitizeAnswer(text) {
  if (!text) return ''
  return FORBIDDEN_REPLACEMENTS.reduce(
    (output, [parts, replacement]) => output.replace(patternFromParts(parts), replacement),
    text,
  )
}

function buildPrompt({ question, candidates }) {
  const candidateLines = candidates
    .map((candidate, index) => {
      const positives = (candidate.positive_reasons || []).join(' / ')
      const negatives = (candidate.negative_reasons || []).join(' / ')
      const grid = candidate.nearby_grid_score
        ? `- 근접 격자 참고: ${candidate.nearby_grid_score.base_grid_id}, 입지 적합도 ${candidate.nearby_grid_score.suitability_score}, 영업 유지 proxy 점수 ${candidate.nearby_grid_score.retention_proxy_score}, 거리 ${candidate.nearby_grid_score.distance_km}km`
        : ''
      return [
        `${index + 1}. ${candidate.name}`,
        `- candidate_id: ${candidate.candidate_id}`,
        `- 위치: ${candidate.sigungu} ${candidate.dong}`,
        `- 업종: ${candidate.industry_label || candidate.recommended_industry}`,
        `- 입지 적합도: ${candidate.suitability_score}`,
        `- 영업 유지 proxy 점수: ${candidate.retention_proxy_score}`,
        `- 비용 부담 proxy: ${candidate.cost_burden_proxy}`,
        `- 추천 사유: ${positives}`,
        `- 주의 사유: ${negatives}`,
        grid,
      ]
        .filter(Boolean)
        .join('\n')
    })
    .join('\n\n')

  return `
너는 BizSpot AI의 입지 후보지 설명 도우미다.
반드시 제공된 후보지 데이터 안에서만 답변한다.
후보지 순위, 위치, 점수, 좌표를 새로 만들거나 바꾸지 않는다.
창업 결과를 보장하는 표현, 매출 관련 전망 표현, 관측 중단을 단정하는 표현을 쓰지 않는다.
retention_proxy_score는 상가정보 스냅샷상 관측 유지 패턴 기반 보조 점수로 설명한다.
각 후보지마다 추천 사유와 주의 사유를 함께 설명한다.
답변 마지막에는 실제 임대료, 권리금, 점포 내부 상태, 브랜드 전략, 실제 유동인구 확인이 필요하다고 안내한다.

사용자 질문:
${question}

로컬 JSON에서 선택된 TOP 3 후보:
${candidateLines}

답변 형식:
질문 조건을 기준으로 공공데이터 기반 후보지를 살펴보면 아래 순서로 검토할 수 있습니다.

1. 후보지명 - 입지 적합도
- 영업 유지 proxy 점수:
- 추천 이유:
- 주의 이유:

2. ...
3. ...

${SAFE_NOTICE}
`.trim()
}

function buildFallbackAnswer({ candidates }) {
  if (!Array.isArray(candidates) || candidates.length === 0) {
    return `조건에 맞는 후보지를 찾지 못했습니다.\n\n${SAFE_NOTICE}`
  }

  const lines = [
    'API 연결이 불안정하거나 키가 없어 로컬 JSON 기반 답변을 제공합니다.',
    '질문 조건을 기준으로 공공데이터 기반 후보지를 살펴보면 아래 순서로 검토할 수 있습니다.',
    '',
  ]

  candidates.slice(0, 3).forEach((candidate, index) => {
    lines.push(
      `${index + 1}. ${candidate.name}`,
      `- 입지 적합도: ${candidate.suitability_score}점`,
      `- 영업 유지 proxy 점수: ${candidate.retention_proxy_score}점`,
      `- 추천 이유: ${(candidate.positive_reasons || []).join(' ') || '공공데이터 proxy 기준으로 비교 후보에 포함되었습니다.'}`,
      `- 주의 이유: ${(candidate.negative_reasons || []).join(' ') || '현장 임대료와 실제 유동인구 확인이 필요합니다.'}`,
      '',
    )
  })

  lines.push(SAFE_NOTICE)
  return lines.join('\n')
}

module.exports = {
  buildFallbackAnswer,
  buildPrompt,
  sanitizeAnswer,
}
