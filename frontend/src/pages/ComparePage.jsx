import { useEffect, useState } from 'react'
import { GitCompare } from 'lucide-react'
import { ScrollProgress, usePageReveal } from '../components/ScrollReveal.jsx'

async function loadJson(path) {
  const res = await fetch(path)
  return res.json()
}

const DISTRICT_DESC = {
  광산구: '광주 서쪽 신도시 중심 — 수완·첨단지구 상권 발달, 임대 부담 낮음',
  북구: '광주 최대 인구 구 — 용봉·일곡·신용·오치 상권 다양, 카페 후보 최다',
  서구: '구도심 + 상무지구 — 접근성 우수, 유동인구 높지만 임대 부담도 높음',
  남구: '봉선·주월 주거 밀집 — 안정적 배후 수요, 음식점·카페 적합',
  동구: '원도심·충장로 상권 — 역사적 상권이나 경쟁 밀도·임대 부담 최고',
}

function ScoreBar({ value, max }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="compare-bar-track">
      <div className="compare-bar-fill" style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function ComparePage() {
  const [data, setData] = useState([])
  usePageReveal()

  useEffect(() => {
    loadJson('/data/district_summary.json').then(setData)
  }, [])

  const maxScore = Math.max(...data.map((d) => d.avg_suitability_score || 0))
  const maxCost = Math.max(...data.map((d) => d.avg_cost_burden_proxy || 0))
  const maxComp = Math.max(...data.map((d) => d.avg_same_industry_300m || 0))
  const sorted = [...data].sort((a, b) => b.avg_suitability_score - a.avg_suitability_score)

  return (
    <div className="info-page">
      <ScrollProgress />

      <div className="info-hero reveal">
        <GitCompare size={32} color="#8272f9" />
        <h1>자치구 비교</h1>
        <p>광주광역시 5개 자치구의 평균 입지 점수를 비교합니다</p>
      </div>

      <section className="info-section">
        <div className="compare-cards">
          {sorted.map((d, i) => (
            <div key={d.sigungu_name} className={`compare-card reveal reveal-delay-${(i % 3) + 1} ${i === 0 ? 'compare-card--top' : ''}`}>
              {i === 0 && <span className="compare-badge">최고 적합도</span>}
              <div className="compare-rank">#{i + 1}</div>
              <h2 className="compare-name">{d.sigungu_name}</h2>
              <p className="compare-desc">{DISTRICT_DESC[d.sigungu_name] || ''}</p>

              <div className="compare-stat">
                <div className="compare-stat-header">
                  <span>평균 입지 적합도</span>
                  <strong>{d.avg_suitability_score?.toFixed(1)}</strong>
                </div>
                <ScoreBar value={d.avg_suitability_score} max={maxScore} />
              </div>

              <div className="compare-stat">
                <div className="compare-stat-header">
                  <span>예상 임대 부담</span>
                  <strong>{Math.round(d.avg_cost_burden_proxy / 10000)}만</strong>
                </div>
                <ScoreBar value={d.avg_cost_burden_proxy} max={maxCost} />
              </div>

              <div className="compare-stat">
                <div className="compare-stat-header">
                  <span>주변 동일업종 수 (300m)</span>
                  <strong>{Math.round(d.avg_same_industry_300m)}개</strong>
                </div>
                <ScoreBar value={d.avg_same_industry_300m} max={maxComp} />
              </div>

              <div className="compare-count">분석 후보지 {d.candidate_rows?.toLocaleString()}곳</div>
            </div>
          ))}
        </div>

        <div className="compare-note reveal">
          * 평균 입지 적합도는 Score = 수요 35% + 경쟁역산 25% + 업종궁합 20% + 접근성 10% + 비용역산 10% 가중합으로 산출됩니다.
          지도에서 특정 동·후보지를 직접 선택하면 더 정밀한 분석을 볼 수 있습니다.
        </div>
      </section>
    </div>
  )
}
