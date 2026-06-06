import { MapPin, Package, BarChart2, Star } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

function useScrollReveal() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { setVisible(entry.isIntersecting) },
      { threshold: 0.15 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, visible]
}

function ScrollProgress() {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    function onScroll() {
      const el = document.documentElement
      const scrolled = el.scrollTop || document.body.scrollTop
      const total = el.scrollHeight - el.clientHeight
      setProgress(total > 0 ? (scrolled / total) * 100 : 0)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return <div className="scroll-progress-bar" style={{ width: `${progress}%` }} />
}

const REVIEWS = [
  { name: '김○○', role: '카페 창업 준비 중', text: '광주 북구에서 카페 입지를 찾는 데 막막했는데, AI 상담 한 번으로 후보지 3곳을 바로 추려줬어요. 데이터 기반이라 신뢰가 갔습니다.' },
  { name: '이○○', role: '편의점 점주', text: '지도에서 직접 핀을 찍어보며 주변 경쟁 업종 밀도까지 확인할 수 있어서 결정할 때 확신이 생겼어요.' },
  { name: '박○○', role: '음식점 예비 창업자', text: '복잡한 상권 분석을 이렇게 쉽게 할 수 있다니 놀랐습니다. 접근성 지수와 유동인구 수치가 특히 도움됐어요.' },
]

export default function HomePage() {
  const [heroVisible, setHeroVisible] = useState(false)
  const [kickerRef, kickerVisible] = useScrollReveal()
  const [titleRef, titleVisible] = useScrollReveal()
  const [card1Ref, card1Visible] = useScrollReveal()
  const [card2Ref, card2Visible] = useScrollReveal()
  const [card3Ref, card3Visible] = useScrollReveal()
  const [reviewTitleRef, reviewTitleVisible] = useScrollReveal()
  const [review1Ref, review1Visible] = useScrollReveal()
  const [review2Ref, review2Visible] = useScrollReveal()
  const [review3Ref, review3Visible] = useScrollReveal()

  useEffect(() => {
    const t = setTimeout(() => setHeroVisible(true), 80)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="home-page">
      <ScrollProgress />

      <section className="home-hero">
        <div className={`hero-inner hero-entrance${heroVisible ? ' hero-entrance--in' : ''}`}>
          <h1>BizSpot AI</h1>
          <p className="hero-subtitle">| 감이 아닌 데이터로 소상공인 창업 입지를 분석합니다 |</p>
          <div className="hero-actions" style={{ marginTop: '42px' }}>
            <a className="hero-link primary" href="/map">지도에서 시작하기</a>
            <a className="hero-link secondary" href="/ai">AI 상담하기</a>
          </div>
        </div>
      </section>

      <section className="how-section" id="how-it-works">
        <p ref={kickerRef} className={`section-kicker reveal${kickerVisible ? ' revealed' : ''}`}>HOW IT WORKS</p>
        <h2 ref={titleRef} className={`reveal${titleVisible ? ' revealed' : ''}`}>3단계로 완성되는 입지 분석</h2>
        <div className="step-grid">
          <article ref={card1Ref} className={`reveal reveal-delay-1${card1Visible ? ' revealed' : ''}`}>
            <span className="step-number-badge">01</span>
            <span className="step-icon"><MapPin size={24} /></span>
            <h3>위치 선택</h3>
            <p>광주광역시 5개 자치구 중 창업을 고려하는 지역을 지도에서 직접 선택</p>
          </article>
          <article ref={card2Ref} className={`reveal reveal-delay-2${card2Visible ? ' revealed' : ''}`}>
            <span className="step-number-badge">02</span>
            <span className="step-icon"><Package size={24} /></span>
            <h3>업종 선택</h3>
            <p>카페, 음식점, 편의점 등 생활밀착형 업종 중 창업할 업종을 선택</p>
          </article>
          <article ref={card3Ref} className={`reveal reveal-delay-3${card3Visible ? ' revealed' : ''}`}>
            <span className="step-number-badge">03</span>
            <span className="step-icon"><BarChart2 size={24} /></span>
            <h3>점수 확인</h3>
            <p>5개 범주 가중합 알고리즘이 0~100점 입지 적합도 점수와 근거를 제공</p>
          </article>
        </div>
      </section>

      <section className="review-section">
        <p ref={reviewTitleRef} className={`section-kicker reveal${reviewTitleVisible ? ' revealed' : ''}`}>USER REVIEWS</p>
        <h2 className={`reveal${reviewTitleVisible ? ' revealed' : ''}`}>실제 사용자 후기</h2>
        <div className="review-grid">
          <div ref={review1Ref} className={`review-card reveal reveal-delay-1${review1Visible ? ' revealed' : ''}`}>
            <div className="review-stars">{[...Array(5)].map((_, i) => <Star key={i} size={14} fill="#8272f9" color="#8272f9" />)}</div>
            <p>"{REVIEWS[0].text}"</p>
            <div className="review-author"><strong>{REVIEWS[0].name}</strong><span>{REVIEWS[0].role}</span></div>
          </div>
          <div ref={review2Ref} className={`review-card reveal reveal-delay-2${review2Visible ? ' revealed' : ''}`}>
            <div className="review-stars">{[...Array(5)].map((_, i) => <Star key={i} size={14} fill="#8272f9" color="#8272f9" />)}</div>
            <p>"{REVIEWS[1].text}"</p>
            <div className="review-author"><strong>{REVIEWS[1].name}</strong><span>{REVIEWS[1].role}</span></div>
          </div>
          <div ref={review3Ref} className={`review-card reveal reveal-delay-3${review3Visible ? ' revealed' : ''}`}>
            <div className="review-stars">{[...Array(5)].map((_, i) => <Star key={i} size={14} fill="#8272f9" color="#8272f9" />)}</div>
            <p>"{REVIEWS[2].text}"</p>
            <div className="review-author"><strong>{REVIEWS[2].name}</strong><span>{REVIEWS[2].role}</span></div>
          </div>
        </div>
      </section>
    </div>
  )
}
