import { AlertTriangle, Lightbulb } from 'lucide-react'
import { ScrollProgress, usePageReveal } from '../components/ScrollReveal.jsx'

const HYPOTHESES = [
  { id: 'H1', title: '창업 적합도 가설', body: '상가정보, 건축물대장, 공시지가, 실거래가, 대중교통 데이터를 결합하면 후보 위치·업종 조합의 창업 적합도 점수를 만들 수 있다.' },
  { id: 'H2', title: '경쟁 임계점 가설', body: '동일 업종 밀집도는 수요가 있다는 신호일 수 있지만, 일정 수준을 넘으면 신규 창업자에게 경쟁 위험으로 작용한다.' },
  { id: 'H3', title: '비용 부담 가설', body: '공시지가와 상업업무용 거래 수준이 높은 지역은 입지 가치가 높지만, 동시에 고정비 부담이 커져 위험 요인이 될 수 있다.' },
  { id: 'H4', title: '설명가능성 가설', body: '변수 기여도를 해석하면 "왜 이 후보지가 추천되는지"와 "무엇이 위험한지"를 웹 카드로 설명할 수 있다.' },
]

const VALIDATION = [
  { q: '예측이 가능한가?', method: 'Logistic / RF / XGBoost 비교', metric: 'AUROC, F1, Precision', criterion: 'Baseline 대비 개선 여부' },
  { q: '점수가 실제 패턴과 맞는가?', method: '상위 20% vs 하위 20% 유지율 비교', metric: '차이, t-test', criterion: '상위 그룹 우세 여부' },
  { q: '순위가 의미 있는가?', method: '점수와 유지율/생존율의 순위상관', metric: 'Spearman ρ', criterion: '양의 상관 관찰' },
  { q: '왜 그런 결과인가?', method: 'SHAP summary/waterfall', metric: '변수 기여도', criterion: '경쟁·비용·접근성 해석 가능' },
]

const INSIGHTS = [
  { title: '감이 아닌 데이터', body: '예비 창업자는 보통 유명 상권, 지인 추천, 직관에 기대어 입지를 고릅니다. BizSpot AI는 수요·경쟁·비용·접근성을 수치로 비교합니다.' },
  { title: '검증 → 해석 → 웹', body: '웹은 최종 포장지가 아닙니다. 모델이 어떤 변수를 근거로 판단했는지 보여주는 설명 인터페이스입니다.' },
  { title: '성공 보장 X', body: '이 시스템은 "창업 성공 예언"이 아니라, 후보지를 1차로 거르고 위험 요인을 확인하는 의사결정 보조 도구입니다.' },
]

export default function InsightsPage() {
  usePageReveal()

  return (
    <div className="info-page">
      <ScrollProgress />

      <div className="info-hero reveal">
        <Lightbulb size={32} color="#8272f9" />
        <h1>인사이트</h1>
        <p>이 프로젝트가 무엇을 검증하고 어떤 결론을 도출했는지 설명합니다</p>
      </div>

      <section className="info-section">
        <h2 className="reveal">연구 핵심 메시지</h2>
        <div className="insight-trio">
          {INSIGHTS.map((item, i) => (
            <div key={item.title} className={`insight-trio-card reveal reveal-delay-${i + 1}`}>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </div>
          ))}
        </div>
        <div className="info-formula-bar reveal" style={{ marginTop: 24 }}>
          최종 연구 질문: 광주광역시에서 특정 위치·업종 조합의 창업 적합도는 공공데이터 기반 변수로 설명될 수 있는가?
        </div>
      </section>

      <section className="info-section">
        <h2 className="reveal">핵심 가설</h2>
        <div className="hypothesis-grid">
          {HYPOTHESES.map((h, i) => (
            <div key={h.id} className={`hypothesis-card reveal reveal-delay-${(i % 2) + 1}`}>
              <span className="hypothesis-id">{h.id}</span>
              <h3>{h.title}</h3>
              <p>{h.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="info-section">
        <h2 className="reveal">모델 검증 설계</h2>
        <p className="info-sub reveal">평가 기준의 난이도와 인사이트를 동시에 잡는 핵심 파트입니다</p>
        <div className="info-table-wrap reveal">
          <table className="info-table">
            <thead>
              <tr><th>검증 질문</th><th>방법</th><th>지표</th><th>판단 기준</th></tr>
            </thead>
            <tbody>
              {VALIDATION.map((v) => (
                <tr key={v.q}>
                  <td><strong>{v.q}</strong></td>
                  <td>{v.method}</td>
                  <td className="mono">{v.metric}</td>
                  <td>{v.criterion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="info-section">
        <div className="info-verdict-grid">
          <div className="info-verdict can reveal reveal-delay-1">
            <h3>✓ 이 결과로 말할 수 있는 결론</h3>
            <ul>
              <li>공공데이터만으로도 후보지의 경쟁도·접근성·비용 부담을 정량화할 수 있다.</li>
              <li>좋은 상권과 창업하기 좋은 상권은 다를 수 있다.</li>
              <li>추천 사유와 위험 사유를 데이터로 설명할 수 있다.</li>
            </ul>
          </div>
          <div className="info-verdict cannot reveal reveal-delay-2">
            <h3><AlertTriangle size={16} /> 아직 말하면 안 되는 결론</h3>
            <ul>
              <li>이 시스템이 실제 창업 성공을 보장한다.</li>
              <li>실제 매출을 정확히 예측했다.</li>
              <li>상업업무용 매매 실거래가가 곧 임대료다.</li>
              <li>전국 모든 지역에 같은 모델을 바로 적용할 수 있다.</li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  )
}
