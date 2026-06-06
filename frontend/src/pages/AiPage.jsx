import { Bot, Loader2, MapPin, Send, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import CandidateCard from '../components/CandidateCard.jsx'
import { attachGridContext, buildFallbackAnswer, selectTop3ForQuestion, sortByScore } from '../utils/recommendation.js'
import { sanitizeSafeText } from '../utils/safeText.js'
import { cleanProxyText } from '../utils/cleanText.js'

const configuredApiBase = import.meta.env.VITE_API_BASE_URL || ''
const localApiBasePattern = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/i
const API_BASE = import.meta.env.PROD
  ? localApiBasePattern.test(configuredApiBase) ? '' : configuredApiBase
  : configuredApiBase || 'http://localhost:8787'

async function loadJson(path) {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`Failed to load ${path}`)
  return res.json()
}

const EXAMPLES = [
  '광주 북구에서 카페 창업지 추천해줘',
  '서구에서 음식점 하려는데 어디가 좋아?',
  '유동인구 많은 편의점 자리 찾아줘',
]

export default function AiPage() {
  const [candidates, setCandidates] = useState([])
  const [gridScores, setGridScores] = useState([])
  const [question, setQuestion] = useState('')
  const [status, setStatus] = useState('idle')
  const [recommendations, setRecommendations] = useState([])
  const [answer, setAnswer] = useState('')

  useEffect(() => {
    Promise.all([
      loadJson('/data/candidates_balanced.json'),
      loadJson('/data/grid_scores.json').catch(() => []),
    ]).then(([candidateRows, gridRows]) => {
      setCandidates(sortByScore(candidateRows))
      setGridScores(gridRows)
    })
  }, [])

  async function handleSubmit() {
    if (!question.trim() || !candidates.length) return
    const { parsed, recommendations: recs } = selectTop3ForQuestion(candidates, question)
    const recsWithGrid = attachGridContext(recs, gridScores)
    setRecommendations(recs)
    setStatus('loading')

    let answerText = ''
    try {
      const response = await fetch(`${API_BASE}/api/ai/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, parsed, candidates: recsWithGrid }),
      })
      if (!response.ok) throw new Error(`${response.status}`)
      const payload = await response.json()
      answerText = cleanProxyText(sanitizeSafeText(payload.answer || buildFallbackAnswer(question, recs)))
    } catch {
      answerText = cleanProxyText(sanitizeSafeText(buildFallbackAnswer(question, recs)))
    }

    setAnswer(answerText)
    setStatus('done')
    sessionStorage.setItem('aiResults', JSON.stringify({ recommendations: recs, answer: answerText, question }))
  }

  function goToMap() {
    window.location.href = '/map?from=ai'
  }

  function reset() {
    setStatus('idle')
    setQuestion('')
    setAnswer('')
    setRecommendations([])
  }

  return (
    <div className="ai-page">
      <div className="ai-page-hero">
        <div className="ai-page-icon"><Bot size={36} /></div>
        <h1>AI 입지 상담</h1>
        <p>광주 창업 후보지를 AI가 분석해 드립니다</p>
      </div>

      <div className="ai-page-card">
        {status === 'idle' && (
          <>
            <p className="ai-page-label">어디서 어떤 창업을 생각하고 계신가요?</p>
            <textarea
              className="ai-page-textarea"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) handleSubmit() }}
              placeholder="예: 광주 북구에서 카페 창업지를 검토하고 싶은데 어디가 좋아?"
              rows={4}
            />
            <div className="ai-example-chips">
              {EXAMPLES.map((ex) => (
                <button key={ex} className="ai-example-chip" type="button" onClick={() => setQuestion(ex)}>
                  {ex}
                </button>
              ))}
            </div>
            <button
              className="ai-page-submit"
              type="button"
              onClick={handleSubmit}
              disabled={!question.trim() || !candidates.length}
            >
              <Send size={17} />
              후보지 찾기
            </button>
          </>
        )}

        {status === 'loading' && (
          <div className="ai-page-loading">
            <Loader2 className="spin" size={52} color="#8272f9" />
            <p className="ai-loading-title">AI가 후보지를 분석하고 있습니다</p>
            <p className="ai-loading-sub">공공데이터와 Gemini AI를 결합해 최적 입지를 찾는 중입니다</p>
          </div>
        )}

        {status === 'done' && (
          <div className="ai-page-result">
            <div className="ai-result-header">
              <Sparkles size={20} color="#8272f9" />
              <span>분석 완료 — 추천 후보지 {recommendations.length}곳</span>
            </div>
            <div className="ai-result-cards">
              {recommendations.map((candidate, index) => (
                <CandidateCard
                  key={candidate.candidate_id}
                  candidate={candidate}
                  rank={index + 1}
                  onSelect={() => {}}
                />
              ))}
            </div>
            <button className="ai-page-submit" type="button" onClick={goToMap}>
              <MapPin size={17} />
              지도에서 결과 보기
            </button>
            <button className="ai-page-reset" type="button" onClick={reset}>
              다시 질문하기
            </button>
          </div>
        )}
      </div>

      <a className="ai-page-back" href="/">← 홈으로</a>
    </div>
  )
}
