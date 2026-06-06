import { useCallback, useEffect, useMemo, useState } from 'react'
import { Filter, MapPinned } from 'lucide-react'
import AiConsultPanel from '../components/AiConsultPanel.jsx'
import AnalysisPanel from '../components/AnalysisPanel.jsx'
import CandidateCard from '../components/CandidateCard.jsx'
import KakaoMap from '../components/KakaoMap.jsx'
import SafeNotice from '../components/SafeNotice.jsx'
import { DISTRICTS, INDUSTRIES } from '../utils/industryLabel.js'
import { filterCandidates, selectAnalysisForClick, sortByScore } from '../utils/recommendation.js'

async function loadJson(path) {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`Failed to load ${path}`)
  return response.json()
}

export default function MapPage() {
  const [candidates, setCandidates] = useState([])
  const [gridScores, setGridScores] = useState([])
  const [industryRecommendations, setIndustryRecommendations] = useState([])
  const [district, setDistrict] = useState('전체')
  const [industry, setIndustry] = useState('cafe')
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [clickedPoint, setClickedPoint] = useState(null)
  const [clickInfo, setClickInfo] = useState(null)
  const [aiRecommendations, setAiRecommendations] = useState([])
  const [aiInitialData, setAiInitialData] = useState(null)
  const [loadError, setLoadError] = useState('')
  const fromAi = new URLSearchParams(window.location.search).get('from') === 'ai'
  const [activePanel, setActivePanel] = useState(fromAi ? 'ai' : 'search')

  useEffect(() => {
    if (fromAi) {
      try {
        const stored = sessionStorage.getItem('aiResults')
        if (stored) {
          const { recommendations, answer, question } = JSON.parse(stored)
          if (Array.isArray(recommendations)) setAiRecommendations(recommendations)
          if (answer || question) setAiInitialData({ question: question || '', answer: answer || '' })
          sessionStorage.removeItem('aiResults')
        }
      } catch {}
    }
  }, [])

  useEffect(() => {
    Promise.all([
      loadJson('/data/candidates_balanced.json'),
      loadJson('/data/grid_scores.json').catch(() => []),
      loadJson('/data/industry_recommendations_filtered.json'),
    ])
      .then(([candidateRows, gridRows, recommendationRows]) => {
        const sorted = sortByScore(candidateRows)
        setCandidates(sorted)
        setGridScores(gridRows)
        setIndustryRecommendations(recommendationRows)
        setSelectedCandidate(sorted.find((item) => item.recommended_industry === 'cafe') || sorted[0])
      })
      .catch((error) => setLoadError(error.message))
  }, [])

  const visibleCandidates = useMemo(
    () => sortByScore(filterCandidates(candidates, district, industry)).slice(0, 40),
    [candidates, district, industry],
  )

  const relatedIndustries = useMemo(() => {
    if (clickInfo?.analysisType === 'grid') return clickInfo.gridTop5 || []
    if (!selectedCandidate) return []
    const match = industryRecommendations.find(
      (item) => item.sigungu === selectedCandidate.sigungu && item.dong === selectedCandidate.dong,
    )
    return match?.industry_top5 || []
  }, [clickInfo, industryRecommendations, selectedCandidate])

  const handleMapClick = useCallback(
    (point) => {
      const result = selectAnalysisForClick({
        gridScores,
        candidates,
        point,
        selectedIndustry: industry,
      })
      setClickedPoint(point)
      setClickInfo(result)
      if (result?.candidate) setSelectedCandidate(result.candidate)
    },
    [candidates, gridScores, industry],
  )

  function selectCandidate(candidate) {
    setSelectedCandidate(candidate)
    setClickInfo(null)
  }

  function selectGridScore(gridScore) {
    const point = {
      lat: Number(gridScore.center_lat ?? gridScore.lat),
      lng: Number(gridScore.center_lng ?? gridScore.lng),
    }
    setClickedPoint(point)
    setSelectedCandidate(gridScore)
    setClickInfo({
      analysisType: 'grid',
      candidate: gridScore,
      baseGridId: gridScore.base_grid_id,
      gridTop5: sortByScore(gridScores.filter((row) => row.base_grid_id === gridScore.base_grid_id)).slice(0, 5),
      fallbackLabel: '격자 마커 선택',
      distanceKm: 0,
      distant: false,
      clickedPoint: point,
    })
  }

  if (loadError) {
    return <div className="error-page">데이터를 불러오지 못했습니다. {loadError}</div>
  }

  return (
    <div className="map-page">
      <header className="map-header">
        <div>
          <p className="panel-eyebrow">공공데이터 기반 후보지 점수</p>
          <h1>광주 입지 후보지 지도 분석</h1>
        </div>
        <SafeNotice compact />
      </header>

      <section className="map-grid">
        <aside className="control-panel">
          <div className="panel-tabs">
            <button
              className={`panel-tab ${activePanel === 'search' ? 'active' : ''}`}
              onClick={() => setActivePanel('search')}
              type="button"
            >
              <Filter size={14} /> 조건 검색
            </button>
            <button
              className={`panel-tab ${activePanel === 'ai' ? 'active' : ''}`}
              onClick={() => setActivePanel('ai')}
              type="button"
            >
              AI 상담
            </button>
          </div>

          {activePanel === 'search' && (
            <>
              <label>
                자치구
                <select value={district} onChange={(event) => setDistrict(event.target.value)}>
                  {DISTRICTS.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                업종
                <select value={industry} onChange={(event) => setIndustry(event.target.value)}>
                  {INDUSTRIES.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </label>
              <div className="section-title compact-title">
                <MapPinned size={16} />
                <h2>상위 후보</h2>
              </div>
              <div className="candidate-list">
                {visibleCandidates.slice(0, 6).map((candidate, index) => (
                  <CandidateCard
                    key={candidate.candidate_id}
                    candidate={candidate}
                    active={selectedCandidate?.candidate_id === candidate.candidate_id}
                    rank={index + 1}
                    onSelect={selectCandidate}
                  />
                ))}
              </div>
            </>
          )}

          {activePanel === 'ai' && (
            <AiConsultPanel
              candidates={candidates}
              gridScores={gridScores}
              onRecommendations={setAiRecommendations}
              onSelectCandidate={selectCandidate}
              initialQuestion={aiInitialData?.question}
              initialAnswer={aiInitialData?.answer}
              initialTop3={aiInitialData ? aiRecommendations : []}
            />
          )}
        </aside>

        <section className="map-stage">
          <KakaoMap
            candidates={candidates}
            gridScores={gridScores}
            selectedIndustry={industry}
            selectedCandidate={selectedCandidate}
            topCandidates={visibleCandidates.slice(0, 6)}
            clickedPoint={clickedPoint}
            aiRecommendations={aiRecommendations}
            onMapClick={handleMapClick}
            onCandidateSelect={selectCandidate}
            onGridSelect={selectGridScore}
          />
        </section>

        <AnalysisPanel
          candidate={selectedCandidate}
          clickInfo={clickInfo}
          relatedIndustries={relatedIndustries}
        />
      </section>
    </div>
  )
}
