import { ArrowRight, BarChart3, Database, MapPinned } from 'lucide-react'

export default function HomePage() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <div className="hero-inner">
          <p className="hero-pill">광주광역시 · 공공데이터 기반 분석</p>
          <h1>BizSpot AI</h1>
          <p className="hero-subtitle">창업 입지를 데이터로 결정하다</p>
          <p className="hero-copy">감이 아닌 공공데이터로 소상공인 창업 입지를 분석합니다</p>
          <div className="hero-actions">
            <a className="hero-link primary" href="/map">
              <span>지도에서 시작하기</span>
              <ArrowRight size={18} />
            </a>
            <a className="hero-link secondary" href="#how-it-works">
              분석 방법 보기
            </a>
          </div>
          <div className="hero-stats" aria-label="BizSpot AI 데이터 요약">
            <div>
              <strong>5</strong>
              <span>개 자치구</span>
            </div>
            <div>
              <strong>30만+</strong>
              <span>점포 데이터</span>
            </div>
            <div>
              <strong>6개</strong>
              <span>데이터 소스</span>
            </div>
          </div>
        </div>
      </section>

      <section className="how-section" id="how-it-works">
        <p className="section-kicker">HOW IT WORKS</p>
        <h2>3단계로 완성되는 입지 분석</h2>
        <p className="section-copy">복잡한 데이터를 쉽고 직관적으로 비교할 수 있게 정리했습니다</p>
        <div className="step-grid">
          <article>
            <span className="step-icon">
              <Database size={22} />
            </span>
            <h3>공공데이터 연결</h3>
            <p>상가정보, 교통, 비용 부담 proxy, 상권 격자 데이터를 같은 기준으로 정리합니다.</p>
          </article>
          <article>
            <span className="step-icon">
              <BarChart3 size={22} />
            </span>
            <h3>입지 점수 계산</h3>
            <p>수요, 접근성, 업종 궁합, 경쟁 부담, 비용 부담을 조합해 후보지를 비교합니다.</p>
          </article>
          <article>
            <span className="step-icon">
              <MapPinned size={22} />
            </span>
            <h3>지도에서 확인</h3>
            <p>광주 500m 상권 격자와 업종별 후보를 지도에서 바로 살펴봅니다.</p>
          </article>
        </div>
      </section>

      <section className="compare-section" id="compare">
        <div>
          <p className="section-kicker">COMPARE</p>
          <h2>후보지를 나란히 보고 판단합니다</h2>
          <p>
            입지 적합도, 영업 유지 proxy 점수, 접근성 proxy, 비용 부담 proxy를 같은 화면에서
            비교합니다.
          </p>
        </div>
        <a className="compare-link" href="/map">분석 화면으로 이동</a>
      </section>
    </div>
  )
}
