import { BarChart2, Bus, Building2, ShoppingBag, Layers, TrendingDown, Train, Zap } from 'lucide-react'
import { ScrollProgress, usePageReveal } from '../components/ScrollReveal.jsx'

const WEIGHTS = [
  { pct: '30%', label: '수요 가능성', desc: '유동인구·배후·상권 활성도', color: '#8272f9' },
  { pct: '20%', label: '접근성', desc: '버스·지하철 거리', color: '#6254e8' },
  { pct: '20%', label: '업종 궁합', desc: '지역 업종 구조와 적합성', color: '#a294fa' },
  { pct: '15%', label: '경쟁 역산', desc: '동일 업종 과밀 보정', color: '#bdb5fc' },
  { pct: '15%', label: '비용 역산', desc: '공시지가·거래 수준', color: '#d4cffd' },
]

const DATA_CARDS = [
  {
    icon: <ShoppingBag size={28} />,
    title: '경쟁 분석',
    tag: '경쟁 위험 탐지',
    desc: '반경 300m 안에 같은 업종이 몇 개나 있는지 파악합니다. 경쟁이 너무 치열한 곳은 점수가 낮아집니다.',
  },
  {
    icon: <Layers size={28} />,
    title: '상권 활성도',
    tag: '상권 규모',
    desc: '주변 500m 내 전체 상가 수로 상권이 얼마나 살아있는지 측정합니다. 상권이 클수록 유동인구도 많습니다.',
  },
  {
    icon: <Zap size={28} />,
    title: '업종 다양성',
    tag: '업종 균형',
    desc: '특정 업종에 쏠린 상권인지, 다양한 업종이 공존하는지 분석합니다. 다양할수록 안정적인 상권입니다.',
  },
  {
    icon: <Bus size={28} />,
    title: '버스 접근성',
    tag: '교통',
    desc: '가장 가까운 버스 정류장까지의 거리를 측정합니다. 손님이 얼마나 쉽게 방문할 수 있는지를 나타냅니다.',
  },
  {
    icon: <Train size={28} />,
    title: '지하철 접근성',
    tag: '도시철도',
    desc: '광주도시철도 역까지의 거리를 측정합니다. 직장인·학생 유동인구 유입 가능성을 나타냅니다.',
  },
  {
    icon: <TrendingDown size={28} />,
    title: '예상 비용 부담',
    tag: '임대 추정',
    desc: '공시지가와 상업 거래 수준으로 예상 임대 부담을 추정합니다. 실제 임대료가 아닌 상대적 비용 수준입니다.',
  },
  {
    icon: <Building2 size={28} />,
    title: '건물 환경',
    tag: '시설 상태',
    desc: '건물 연령과 면적으로 시설의 상태와 규모를 파악합니다. 오래되거나 너무 작은 건물은 감점됩니다.',
  },
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
  usePageReveal()

  return (
    <div className="info-page">
      <ScrollProgress />

      <div className="info-hero reveal">
        <BarChart2 size={32} color="#8272f9" />
        <h1>분석 방법</h1>
        <p>BizSpot AI가 입지 점수를 어떻게 계산하는지 쉽게 설명합니다</p>
      </div>

      <section className="info-section">
        <div className="info-formula-bar reveal">
          점수 = 수요 가능성 30% + 접근성 20% + 업종궁합 20% + 경쟁강도 역산 15% + 비용부담 역산 15%
        </div>
        <div className="info-weight-grid">
          {WEIGHTS.map((w, i) => (
            <div key={w.label} className={`info-weight-card reveal reveal-delay-${i + 1}`}>
              <div className="info-weight-pct" style={{ color: w.color }}>{w.pct}</div>
              <div className="info-weight-label">{w.label}</div>
              <div className="info-weight-desc">{w.desc}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <h2 className="reveal">어떤 데이터를 보나요?</h2>
        <p className="info-sub reveal">공공데이터 7종을 조합해 후보지를 평가합니다</p>
        <div className="analysis-data-grid">
          {DATA_CARDS.map((card, i) => (
            <div key={card.title} className={`analysis-data-card reveal reveal-delay-${(i % 3) + 1}`}>
              <div className="analysis-data-icon">{card.icon}</div>
              <div className="analysis-data-tag">{card.tag}</div>
              <h3 className="analysis-data-title">{card.title}</h3>
              <p className="analysis-data-desc">{card.desc}</p>
            </div>
          ))}
        </div>
      </section>

    </div>
  )
}
