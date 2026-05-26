import { AlertTriangle, CheckCircle2, Info } from 'lucide-react'
import { industryLabel } from '../utils/industryLabel.js'
import SafeNotice from './SafeNotice.jsx'

function formatCoord(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(5) : '-'
}

function formatDistance(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}km` : '-'
}

function scoreBar(label, value) {
  const width = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className="score-bar" key={label}>
      <label>
        <span>{label}</span>
        <b>{value ?? '데이터 없음'}</b>
      </label>
      <div className="bar-track">
        <span style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}

function displayTopIndustry(item, index) {
  const industry = item.industry || item.recommended_industry
  const label = item.industry_label || industryLabel(industry)
  const score = item.score ?? item.suitability_score
  return (
    <li key={`${industry || label}-${item.rank || index}`}>
      {label} <b>{score}</b>
    </li>
  )
}

export default function AnalysisPanel({ candidate, clickInfo, relatedIndustries }) {
  if (!candidate) {
    return (
      <aside className="analysis-panel empty">
        <Info size={22} />
        <p>지도에서 위치나 후보지를 선택하면 입지 분석을 표시합니다.</p>
      </aside>
    )
  }

  const isGridAnalysis = clickInfo?.analysisType === 'grid' || candidate.source_type === 'grid'
  const selectedIndustry = candidate.recommended_industry || candidate.industry
  const displayName =
    candidate.name ||
    `${candidate.sigungu} ${candidate.dong} ${industryLabel(selectedIndustry)} 격자`
  const topIndustries = isGridAnalysis ? clickInfo?.gridTop5 || [] : relatedIndustries

  return (
    <aside className="analysis-panel">
      <div className="panel-eyebrow">선택 분석 결과</div>
      {isGridAnalysis && <div className="analysis-badge">격자 기반 분석</div>}
      <h2>{displayName}</h2>
      <p className="location-line">
        {candidate.sigungu} {candidate.dong} · {industryLabel(selectedIndustry)}
      </p>

      {clickInfo?.fallbackLabel && (
        <div className="fallback-line">
          {clickInfo.fallbackLabel}
          {Number.isFinite(Number(clickInfo.distanceKm)) ? ` · 거리 ${clickInfo.distanceKm.toFixed(2)}km` : ''}
        </div>
      )}
      {clickInfo?.distant && (
        <div className="distance-warning">
          선택 위치 근처에 충분한 분석 데이터가 없어 가장 가까운 분석 격자를 참고로 표시합니다.
        </div>
      )}

      {clickInfo?.clickedPoint && (
        <section className="analysis-meta">
          <h3>분석 기준</h3>
          <dl>
            <div>
              <dt>기준</dt>
              <dd>{isGridAnalysis ? '500m 격자 기반' : '후보지 fallback 기반'}</dd>
            </div>
            <div>
              <dt>선택 좌표</dt>
              <dd>
                {formatCoord(clickInfo.clickedPoint.lat)}, {formatCoord(clickInfo.clickedPoint.lng)}
              </dd>
            </div>
            <div>
              <dt>분석 격자</dt>
              <dd>{clickInfo.baseGridId || candidate.candidate_id || '-'}</dd>
            </div>
            <div>
              <dt>거리</dt>
              <dd>{formatDistance(clickInfo.distanceKm)}</dd>
            </div>
          </dl>
        </section>
      )}

      <div className="score-pair">
        <div>
          <span>입지 적합도</span>
          <strong>{candidate.suitability_score}</strong>
        </div>
        <div>
          <span>영업 유지 proxy 점수</span>
          <strong>{candidate.retention_proxy_score}</strong>
        </div>
      </div>

      <div className="chip-row">
        <span className="chip">위험도 {candidate.risk_level}</span>
        <span className="chip">동일 업종 {candidate.same_industry_300m ?? '-'}개</span>
        <span className="chip">비용 부담 proxy {candidate.cost_burden_proxy?.toLocaleString?.() ?? '-'}</span>
      </div>

      <section className="score-section">
        {[
          scoreBar('수요 proxy', candidate.demand_proxy_score),
          scoreBar('접근성 proxy', candidate.accessibility_score),
          scoreBar('업종 궁합', candidate.industry_fit_score),
          scoreBar('경쟁 부담 완화', candidate.competition_burden_score),
          scoreBar('비용 부담 완화', candidate.cost_inverted_score),
        ]}
      </section>

      <section className="reason-section">
        <h3>
          <CheckCircle2 size={17} />
          추천 사유
        </h3>
        <ul>
          {(candidate.positive_reasons || []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>

      <section className="reason-section">
        <h3>
          <AlertTriangle size={17} />
          주의 사유
        </h3>
        <ul>
          {(candidate.negative_reasons || []).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>

      <section className="related-section">
        <h3>{isGridAnalysis ? '이 격자 추천 업종 TOP 5' : '주변 추천 업종 TOP 5'}</h3>
        {topIndustries.length ? (
          <ol>{topIndustries.map(displayTopIndustry)}</ol>
        ) : (
          <p>이 위치의 업종 추천 데이터는 제한적입니다.</p>
        )}
      </section>

      <section className="limitation-section">
        <h3>한계 인사이트</h3>
        <p>입지 데이터만으로 신규 창업 유지 여부를 충분히 설명하기 어렵습니다.</p>
      </section>

      <SafeNotice compact />
    </aside>
  )
}
