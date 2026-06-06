import { BarChart2, CheckCircle2, XCircle } from 'lucide-react'

const WEIGHTS = [
  { pct: '35%', label: '수요 가능성', desc: '유동인구·배후·상권 활성도', color: '#8272f9' },
  { pct: '25%', label: '경쟁 역산', desc: '동일 업종 과밀 보정', color: '#6254e8' },
  { pct: '20%', label: '업종 궁합', desc: '지역 업종 구조와 적합성', color: '#a294fa' },
  { pct: '10%', label: '접근성', desc: '버스·지하철 거리', color: '#bdb5fc' },
  { pct: '10%', label: '비용 역산', desc: '공시지가·거래 수준', color: '#d4cffd' },
]

const VARIABLES = [
  { cat: '경쟁', var: 'comp_density_300m / 500m', method: '후보지 반경 내 동일 소분류 업종 수', interp: '높으면 수요 신호이면서 경쟁 위험' },
  { cat: '상권 규모', var: 'total_store_500m', method: '반경 내 전체 상가 수', interp: '상권 활성도 측정' },
  { cat: '업종 다양성', var: 'hhi_500m', method: '반경 내 업종별 비율로 HHI 계산', interp: '업종 쏠림·다양성 판단' },
  { cat: '교통 접근성', var: 'nearest_bus_m', method: '최근접 정류장 거리', interp: '방문 편의성' },
  { cat: '도시철도', var: 'nearest_subway_m', method: '최근접 광주도시철도역 거리', interp: '직장인·학생 이동 수요' },
  { cat: '비용 부담', var: 'cost_burden_proxy', method: '공시지가 등급 + 상업용 거래 수준', interp: '임대료 아니라 비용 부담 추정치' },
  { cat: '건물 특성', var: 'building_age, gross_floor_area', method: '현재연도 - 사용승인연도, 면적', interp: '건물 노후도·규모' },
]

const CAN = [
  '공공데이터만으로도 후보지의 경쟁도·접근성·비용 부담을 정량화할 수 있다.',
  '좋은 상권과 창업하기 좋은 상권은 다를 수 있다.',
  '추천·주의 사유를 데이터로 설명할 수 있다.',
]

const CANNOT = [
  '이 시스템이 실제 창업 성공을 보장한다.',
  '실제 매출을 정확히 예측했다.',
  '상업업무용 매매 실거래가가 곧 임대료다.',
  '전국 모든 지역에 같은 모델을 바로 적용할 수 있다.',
]

export default function AnalysisPage() {
  return (
    <div className="info-page">
      <div className="info-hero">
        <BarChart2 size={32} color="#8272f9" />
        <h1>분석 방법</h1>
        <p>BizSpot AI가 입지 점수를 산출하는 방식을 설명합니다</p>
      </div>

      <section className="info-section">
        <div className="info-formula-bar">
          Score = 수요 가능성 35% + 경쟁강도 역산 25% + 업종궁합 20% + 접근성 10% + 비용부담 역산 10%
        </div>
        <div className="info-weight-grid">
          {WEIGHTS.map((w) => (
            <div key={w.label} className="info-weight-card">
              <div className="info-weight-pct" style={{ color: w.color }}>{w.pct}</div>
              <div className="info-weight-label">{w.label}</div>
              <div className="info-weight-desc">{w.desc}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <h2>사용 변수</h2>
        <p className="info-sub">"매출 예측" 대신 "창업 적합도·위험도·유지 가능성"으로 안전하게 설계했습니다</p>
        <div className="info-table-wrap">
          <table className="info-table">
            <thead>
              <tr><th>범주</th><th>변수</th><th>산출 방법</th><th>해석</th></tr>
            </thead>
            <tbody>
              {VARIABLES.map((v) => (
                <tr key={v.var}>
                  <td><strong>{v.cat}</strong></td>
                  <td className="mono">{v.var}</td>
                  <td>{v.method}</td>
                  <td>{v.interp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="info-section">
        <div className="info-verdict-grid">
          <div className="info-verdict can">
            <h3><CheckCircle2 size={18} /> 이 결과로 말할 수 있는 결론</h3>
            <ul>{CAN.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
          <div className="info-verdict cannot">
            <h3><XCircle size={18} /> 아직 말하면 안 되는 결론</h3>
            <ul>{CANNOT.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        </div>
      </section>
    </div>
  )
}
