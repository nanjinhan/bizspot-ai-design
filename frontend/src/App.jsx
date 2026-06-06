import AiPage from './pages/AiPage.jsx'
import HomePage from './pages/HomePage.jsx'
import MapPage from './pages/MapPage.jsx'

export default function App() {
  const path = window.location.pathname
  const isMap = path === '/map'
  const isAi = path === '/ai'

  function renderPage() {
    if (isMap) return <MapPage />
    if (isAi) return <AiPage />
    return <HomePage />
  }

  return (
    <div className="app-shell">
      {!isAi && (
        <header className="top-nav" aria-label="주요 메뉴">
          <a className="brand" href="/" aria-label="BizSpot AI 홈">
            BizSpot AI
          </a>
          <nav>
            <a className={isMap ? 'active' : ''} href="/map">지도</a>
            <a href="/map#analysis">분석</a>
            <a href="/#compare">비교</a>
            <a href="/#insight">인사이트</a>
            <a href="/#team">팀</a>
            <a className="nav-cta" href="/map">분석 시작</a>
          </nav>
        </header>
      )}
      <main className="app-main">{renderPage()}</main>
    </div>
  )
}
