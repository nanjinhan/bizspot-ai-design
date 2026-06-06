import { MapPin, Package, BarChart2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

function useScrollReveal() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
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

export default function HomePage() {
  const [kickerRef, kickerVisible] = useScrollReveal()
  const [titleRef, titleVisible] = useScrollReveal()
  const [card1Ref, card1Visible] = useScrollReveal()
  const [card2Ref, card2Visible] = useScrollReveal()
  const [card3Ref, card3Visible] = useScrollReveal()

  return (
    <div className="home-page">
      <ScrollProgress />

      <section className="home-hero">
        <div className="hero-inner">
          <h1>BizSpot AI</h1>
          <p className="hero-subtitle">| 감이 아닌 데이터로 소상공인 창업 입지를 분석합니다 |</p>
          <div className="hero-actions" style={{ marginTop: '42px' }}>
            <a className="hero-link primary" href="/map">
              지도에서 시작하기
            </a>
            <a className="hero-link secondary" href="/map">
              AI 상담하기
            </a>
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
    </div>
  )
}
