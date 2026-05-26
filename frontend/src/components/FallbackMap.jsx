import { getPointLatLng, pointFromFallbackClick, projectToFallbackMap } from '../utils/geo.js'

function markerColor(score) {
  if (score >= 75) return '#168a5b'
  if (score >= 60) return '#d97706'
  return '#dc2626'
}

function markerKey(row) {
  return row.grid_id || row.candidate_id || `${row.lat}-${row.lng}-${row.industry || row.recommended_industry}`
}

export default function FallbackMap({
  markerRows,
  selectedCandidate,
  clickedPoint,
  aiRecommendations,
  reason,
  onMapClick,
  onCandidateSelect,
  onGridSelect,
}) {
  function handlePanelClick(event) {
    if (event.target.closest('button')) return
    onMapClick(pointFromFallbackClick(event, event.currentTarget))
  }

  function handleMarkerClick(row) {
    if (row.source_type === 'grid') onGridSelect(row)
    else onCandidateSelect(row)
  }

  return (
    <div
      className="fallback-map"
      data-testid="fallback-map"
      role="application"
      aria-label="광주 bounding box 기반 fallback 지도"
      onClick={handlePanelClick}
    >
      <div className="fallback-map-label">
        <strong>Kakao 지도 대신 fallback 지도로 표시 중</strong>
        <span>
          {reason || 'Kakao SDK가 로드되지 않았습니다.'} 현재 접속 도메인을 Kakao Developers에 등록하고 dev server를 재시작하세요.
        </span>
      </div>

      {markerRows.map((row) => {
        const point = getPointLatLng(row)
        if (!point) return null
        const projected = projectToFallbackMap(point)
        const active =
          selectedCandidate &&
          (selectedCandidate.candidate_id === row.candidate_id || selectedCandidate.grid_id === row.grid_id)
        return (
          <button
            key={markerKey(row)}
            className={active ? 'fallback-marker active' : 'fallback-marker'}
            type="button"
            style={{
              left: `${projected.x}%`,
              top: `${projected.y}%`,
              background: markerColor(row.suitability_score),
            }}
            title={row.name || row.grid_id}
            aria-label={row.name || row.grid_id || '분석 마커'}
            onClick={() => handleMarkerClick(row)}
          />
        )
      })}

      {clickedPoint && (
        <span
          className="clicked-marker"
          data-testid="clicked-marker"
          style={{
            left: `${projectToFallbackMap(clickedPoint).x}%`,
            top: `${projectToFallbackMap(clickedPoint).y}%`,
          }}
        />
      )}

      {aiRecommendations.map((candidate, index) => {
        const point = getPointLatLng(candidate)
        if (!point) return null
        const projected = projectToFallbackMap(point)
        return (
          <button
            key={`ai-${candidate.candidate_id || index}`}
            className="fallback-ai-marker"
            type="button"
            style={{ left: `${projected.x}%`, top: `${projected.y}%` }}
            title={candidate.name}
            aria-label={`AI 추천 ${index + 1}: ${candidate.name}`}
            onClick={() => onCandidateSelect(candidate)}
          >
            {index + 1}
          </button>
        )
      })}
    </div>
  )
}
