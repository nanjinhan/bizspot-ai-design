import { AlertTriangle, CheckCircle2, Lightbulb, MapPin, TrendingUp, Users } from 'lucide-react'
import { ScrollProgress, usePageReveal } from '../components/ScrollReveal.jsx'

const KEY_INSIGHTS = [
  {
    icon: <TrendingUp size={28} />,
    title: '좋은 상권 ≠ 창업하기 좋은 상권',
    desc: '유동인구가 많고 번화한 곳이 오히려 경쟁이 치열하고 임대 부담이 높아 실제 창업에는 불리할 수 있습니다. 데이터는 이 차이를 구분해줍니다.',
  },
  {
    icon: <MapPin size={28} />,
    title: '같은 동네도 위치마다 점수가 다릅니다',
    desc: '같은 행정동 안에서도 버스 정류장 거리, 주변 경쟁 업체 수, 건물 환경에 따라 점수가 크게 달라집니다. 골목 단위 분석이 가능합니다.',
  },
  {
    icon: <Users size={28} />,
    title: '업종마다 유리한 입지가 다릅니다',
    desc: '카페는 유동인구와 접근성이, 편의점은 배후 주거 인구가, 음식점은 경쟁 밀도가 핵심입니다. 업종을 바꾸면 추천 후보지도 달라집니다.',
  },
]

const USE_CASES = [
  { q: '창업 지역을 아직 못 정했어요', a: '자치구 비교 탭에서 5개 구의 평균 적합도와 임대 부담을 한눈에 비교하세요.' },
  { q: '특정 동에서 시작하고 싶어요', a: '지도에서 원하는 지역을 클릭하면 그 위치의 점수와 추천/주의 사유를 바로 확인할 수 있습니다.' },
  { q: '어떤 업종이 맞는지 모르겠어요', a: 'AI 상담에 자유롭게 질문하면 질문 내용을 분석해 가장 적합한 후보지 3곳을 추려드립니다.' },
  { q: '분석 결과를 어떻게 해석하나요?', a: '입지 적합도 점수 + 추천 사유 + 주의 사유를 함께 보세요. 점수가 높아도 주의 사유가 있으면 현장 확인이 필요합니다.' },
]

const CAN = [
  '후보지를 데이터로 1차 필터링할 수 있다',
  '비슷한 조건의 여러 위치를 객관적으로 비교할 수 있다',
  '왜 그 후보지가 추천됐는지 근거를 확인할 수 있다',
  '업종별로 어떤 지역이 유리한지 파악할 수 있다',
]

const CANNOT = [
  '실제 창업 성공률을 보장하지 않는다',
  '현장 임대료·권리금·점포 상태는 직접 확인해야 한다',
  '광주광역시 외 지역은 아직 지원하지 않는다',
  '매출을 예측하거나 수익성을 계산해주지 않는다',
]

export default function InsightsPage() {
  usePageReveal()

  return (
    <div className="info-page">
      <ScrollProgress />

      <div className="info-hero reveal">
        <Lightbulb size={32} color="#8272f9" />
        <h1>인사이트</h1>
        <p>BizSpot AI를 더 잘 활용하기 위한 핵심 내용을 정리했습니다</p>
      </div>

      <section className="info-section">
        <h2 className="reveal">이것만 알면 됩니다</h2>
        <div className="insight-trio">
          {KEY_INSIGHTS.map((item, i) => (
            <div key={item.title} className={`insight-trio-card reveal reveal-delay-${i + 1}`}>
              <div className="insight-icon">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <h2 className="reveal">이런 상황에서 활용하세요</h2>
        <div className="insight-usecase-list">
          {USE_CASES.map((item, i) => (
            <div key={item.q} className={`insight-usecase-item reveal reveal-delay-${(i % 2) + 1}`}>
              <div className="insight-usecase-q">
                <span className="insight-usecase-badge">Q</span>
                {item.q}
              </div>
              <div className="insight-usecase-a">
                <span className="insight-usecase-badge insight-usecase-badge--a">A</span>
                {item.a}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <div className="info-verdict-grid">
          <div className="info-verdict can reveal reveal-delay-1">
            <h3><CheckCircle2 size={18} /> 이 서비스로 할 수 있는 것</h3>
            <ul>{CAN.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
          <div className="info-verdict cannot reveal reveal-delay-2">
            <h3><AlertTriangle size={18} /> 이 서비스의 한계</h3>
            <ul>{CANNOT.map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        </div>
      </section>
    </div>
  )
}
