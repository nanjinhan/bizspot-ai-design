import { useEffect, useState } from 'react'

export function ScrollProgress() {
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

export function usePageReveal() {
  useEffect(() => {
    function observe() {
      const elements = document.querySelectorAll('.reveal')
      if (!elements.length) return
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('revealed')
            } else {
              entry.target.classList.remove('revealed')
            }
          })
        },
        { threshold: 0.1 }
      )
      elements.forEach((el) => observer.observe(el))
      return observer
    }

    const observer = observe()
    return () => observer?.disconnect()
  }, [])
}
