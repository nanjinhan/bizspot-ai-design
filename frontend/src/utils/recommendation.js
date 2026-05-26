import { distanceKm, getPointLatLng } from './geo.js'
import { industryLabel } from './industryLabel.js'
import { SAFE_NOTICE_LONG } from './safeText.js'

const REGION_ALIASES = ['동구', '서구', '남구', '북구', '광산구']
const INDUSTRY_KEYWORDS = [
  ['cafe', ['카페', '커피', 'coffee']],
  ['dessert_bakery', ['디저트', '베이커리', '빵', '제과']],
  ['restaurant_general', ['음식점', '식당', '한식', '외식']],
  ['bunsik', ['분식', '김밥', '떡볶이']],
  ['chicken', ['치킨', '닭']],
  ['convenience_store', ['편의점']],
  ['beauty_hair', ['미용실', '헤어', '뷰티']],
  ['laundry', ['세탁소', '세탁']],
]

export function sortByScore(candidates = []) {
  return [...candidates].sort((a, b) => {
    const scoreDiff = (Number(b.suitability_score) || 0) - (Number(a.suitability_score) || 0)
    if (scoreDiff !== 0) return scoreDiff
    return (Number(b.retention_proxy_score) || 0) - (Number(a.retention_proxy_score) || 0)
  })
}

export function filterCandidates(candidates, district, industry) {
  return candidates.filter((candidate) => {
    const districtOk = district === '전체' || candidate.sigungu === district
    const industryOk = industry === 'all' || candidate.recommended_industry === industry
    return districtOk && industryOk && getPointLatLng(candidate)
  })
}

export function nearestCandidate(candidates, point) {
  const rows = candidates.filter((candidate) => getPointLatLng(candidate))
  if (!rows.length) return null
  return rows
    .map((candidate) => ({
      candidate,
      distanceKm: distanceKm(point, candidate),
    }))
    .sort((a, b) => a.distanceKm - b.distanceKm)[0]
}

export function pointForAnalysisRow(row) {
  return getPointLatLng(row)
}

export function nearestGridBase(gridScores, point) {
  if (!gridScores.length) return null
  const baseMap = new Map()
  gridScores.forEach((row) => {
    const pointInRow = getPointLatLng(row)
    if (!row.base_grid_id || !pointInRow || baseMap.has(row.base_grid_id)) return
    baseMap.set(row.base_grid_id, {
      base_grid_id: row.base_grid_id,
      center_lat: pointInRow.lat,
      center_lng: pointInRow.lng,
      lat: pointInRow.lat,
      lng: pointInRow.lng,
    })
  })

  return [...baseMap.values()]
    .map((grid) => ({
      grid,
      distanceKm: distanceKm(point, grid),
    }))
    .sort((a, b) => a.distanceKm - b.distanceKm)[0]
}

export function selectGridForClick(gridScores, point, selectedIndustry) {
  const nearest = nearestGridBase(gridScores, point)
  if (!nearest) return null

  const rowsInGrid = sortByScore(
    gridScores.filter((row) => row.base_grid_id === nearest.grid.base_grid_id),
  )
  if (!rowsInGrid.length) return null

  const industryRow =
    selectedIndustry && selectedIndustry !== 'all'
      ? rowsInGrid.find(
          (row) => row.industry === selectedIndustry || row.recommended_industry === selectedIndustry,
        )
      : null
  const selectedRow = industryRow || rowsInGrid[0]

  return {
    candidate: selectedRow,
    distanceKm: nearest.distanceKm,
    fallbackLabel: industryRow ? '선택 업종 격자 분석' : '같은 격자 업종 TOP 5 기준',
    distant: nearest.distanceKm > 1,
    analysisType: 'grid',
    baseGridId: nearest.grid.base_grid_id,
    gridTop5: rowsInGrid.slice(0, 5),
    clickedPoint: point,
  }
}

export function selectCandidateForClick(candidates, point, selectedIndustry) {
  const validCandidates = candidates.filter((candidate) => getPointLatLng(candidate))
  const nearestAny = nearestCandidate(validCandidates, point)
  const inferredDistrict = nearestAny?.candidate?.sigungu
  const sameIndustry = validCandidates.filter((item) => item.recommended_industry === selectedIndustry)
  const sameDistrict = inferredDistrict
    ? validCandidates.filter((item) => item.sigungu === inferredDistrict)
    : []
  const sameIndustrySameDistrict = sameIndustry.filter((item) => item.sigungu === inferredDistrict)

  const attempts = [
    { label: '선택 업종 + 1km 이내 후보', list: sameIndustry, requireWithinKm: 1 },
    { label: '선택 업종 + 같은 자치구 후보', list: sameIndustrySameDistrict },
    { label: '모든 업종 + 1km 이내 후보', list: validCandidates, requireWithinKm: 1 },
    { label: '모든 업종 + 같은 자치구 후보', list: sameDistrict },
  ]

  for (const attempt of attempts) {
    const nearest = nearestCandidate(attempt.list, point)
    if (!nearest) continue
    if (attempt.requireWithinKm && nearest.distanceKm > attempt.requireWithinKm) continue
    return {
      ...nearest,
      fallbackLabel: attempt.label,
      distant: nearest.distanceKm > 1,
    }
  }

  const best = sortByScore(validCandidates)[0]
  return {
    candidate: best,
    distanceKm: best ? distanceKm(point, best) : 0,
    fallbackLabel: '광주 전체 상위 후보',
    distant: true,
  }
}

export function selectAnalysisForClick({ gridScores, candidates, point, selectedIndustry }) {
  const gridResult = selectGridForClick(gridScores, point, selectedIndustry)
  if (gridResult) return gridResult

  const candidateResult = selectCandidateForClick(
    candidates,
    point,
    selectedIndustry === 'all' ? 'cafe' : selectedIndustry,
  )
  return candidateResult
    ? {
        ...candidateResult,
        analysisType: 'candidate',
        clickedPoint: point,
      }
    : null
}

export function parseQuestion(question) {
  const normalized = String(question || '').toLowerCase()
  const region = REGION_ALIASES.find((item) => normalized.includes(item)) || '전체'
  const industryEntry = INDUSTRY_KEYWORDS.find(([, keywords]) =>
    keywords.some((keyword) => normalized.includes(keyword.toLowerCase())),
  )
  return {
    region,
    industry: industryEntry?.[0] || 'all',
  }
}

export function selectTop3ForQuestion(candidates, question) {
  const parsed = parseQuestion(question)
  const both = sortByScore(filterCandidates(candidates, parsed.region, parsed.industry))
  const regionOnly = sortByScore(filterCandidates(candidates, parsed.region, 'all'))
  const industryOnly = sortByScore(filterCandidates(candidates, '전체', parsed.industry))
  const all = sortByScore(candidates)
  const merged = uniqueByCandidateId([...both, ...regionOnly, ...industryOnly, ...all])

  return {
    parsed,
    recommendations: merged.slice(0, 3),
  }
}

export function nearestGridForCandidate(gridScores, candidate) {
  if (!gridScores.length || !candidate) return null
  const sameIndustry = gridScores.filter((row) => row.industry === candidate.recommended_industry)
  const nearest = nearestCandidate(sameIndustry.length ? sameIndustry : gridScores, candidate)
  return nearest?.candidate
    ? {
        base_grid_id: nearest.candidate.base_grid_id,
        suitability_score: nearest.candidate.suitability_score,
        retention_proxy_score: nearest.candidate.retention_proxy_score,
        distance_km: Number(nearest.distanceKm.toFixed(2)),
      }
    : null
}

export function attachGridContext(recommendations, gridScores) {
  return recommendations.map((candidate) => ({
    ...candidate,
    nearby_grid_score: nearestGridForCandidate(gridScores, candidate),
  }))
}

export function uniqueByCandidateId(items) {
  const seen = new Set()
  return items.filter((item) => {
    const key = item?.candidate_id || item?.grid_id
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function buildFallbackAnswer(question, recommendations) {
  if (!recommendations.length) {
    return `질문 조건에 맞는 후보지를 찾지 못했습니다.\n\n${SAFE_NOTICE_LONG}`
  }
  const lines = [
    'API 연결이 불안정해 로컬 공공데이터 기반 답변을 제공합니다.',
    '질문 조건을 기준으로 먼저 검토할 후보지는 아래와 같습니다.',
    '',
  ]
  recommendations.forEach((candidate, index) => {
    lines.push(
      `${index + 1}. ${candidate.sigungu} ${candidate.dong} ${industryLabel(candidate.recommended_industry)} 후보지`,
      `- 입지 적합도: ${candidate.suitability_score}점`,
      `- 영업 유지 proxy 점수: ${candidate.retention_proxy_score}점`,
      `- 추천 사유: ${(candidate.positive_reasons || []).join(' ')}`,
      `- 주의 사유: ${(candidate.negative_reasons || []).join(' ')}`,
      '',
    )
  })
  lines.push(SAFE_NOTICE_LONG)
  return lines.join('\n')
}
