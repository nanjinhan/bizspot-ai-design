import AboutPage from './pages/AboutPage.jsx'
import AiPage from './pages/AiPage.jsx'
import AnalysisPage from './pages/AnalysisPage.jsx'
import ComparePage from './pages/ComparePage.jsx'
import HomePage from './pages/HomePage.jsx'
import InsightsPage from './pages/InsightsPage.jsx'
import MapPage from './pages/MapPage.jsx'

export default function App() {
  const path = window.location.pathname
  const isAi = path === '/ai'

  function renderPage() {
    if (path === '/map') return <MapPage />
    if (path === '/ai') return <AiPage />
    if (path === '/analysis') return <AnalysisPage />
    if (path === '/compare') return <ComparePage />
    if (path === '/insights') return <InsightsPage />
    if (path === '/about') return <AboutPage />
    return <HomePage />
  }

  const navLinks = [
    { href: '/map', label: '지도' },
    { href: '/analysis', label: '분석 방법' },
    { href: '/compare', label: '자치구 비교' },
    { href: '/insights', label: '인사이트' },
    { href: '/about', label: '소개' },
  ]

  return (
    <div className="app-shell">
      {!isAi && (
        <header className="top-nav" aria-label="주요 메뉴">
          <a className="brand" href="/" aria-label="BizSpot AI 홈">
            BizSpot AI
          </a>
          <nav>
            {navLinks.map((link) => (
              <a key={link.href} className={path === link.href ? 'active' : ''} href={link.href}>
                {link.label}
              </a>
            ))}
            <a className="nav-cta" href="/map">분석 시작</a>
          </nav>
        </header>
      )}
      <main className="app-main">{renderPage()}</main>
    </div>
  )
}
