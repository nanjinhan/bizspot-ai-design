import { Bot, Loader2, Send } from 'lucide-react'
import { useState } from 'react'
import { attachGridContext, buildFallbackAnswer, selectTop3ForQuestion } from '../utils/recommendation.js'
import { sanitizeSafeText } from '../utils/safeText.js'
import { cleanProxyText } from '../utils/cleanText.js'
import CandidateCard from './CandidateCard.jsx'

const configuredApiBase = import.meta.env.VITE_API_BASE_URL || ''
const localApiBasePattern = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/i
const API_BASE = import.meta.env.PROD
  ? localApiBasePattern.test(configuredApiBase)
    ? ''
    : configuredApiBase
  : configuredApiBase || 'http://localhost:8787'

export default function AiConsultPanel({ candidates, gridScores = [], onRecommendations, onSelectCandidate, initialQuestion, initialAnswer, initialTop3 = [] }) {
  const [question, setQuestion] = useState(initialQuestion ?? '광주 북구에서 카페 창업지를 검토하고 싶은데 어디가 좋아?')
  const [answer, setAnswer] = useState(initialAnswer ?? '')
  const [localTop3, setLocalTop3] = useState(initialTop3)
  const [status, setStatus] = useState(initialAnswer ? 'success' : 'idle')

  async function askAi() {
    const { parsed, recommendations } = selectTop3ForQuestion(candidates, question)
    const recommendationsWithGrid = attachGridContext(recommendations, gridScores)
    setLocalTop3(recommendations)
    onRecommendations(recommendations)
    setStatus('loading')

    try {
      const response = await fetch(`${API_BASE}/api/ai/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, parsed, candidates: recommendationsWithGrid }),
      })
      if (!response.ok) throw new Error(`AI server responded ${response.status}`)
      const payload = await response.json()
      setAnswer(cleanProxyText(sanitizeSafeText(payload.answer || buildFallbackAnswer(question, recommendations))))
      setStatus(payload.fallback ? 'fallback' : 'success')
    } catch {
      setAnswer(cleanProxyText(sanitizeSafeText(buildFallbackAnswer(question, recommendations))))
      setStatus('fallback')
    }
  }

  return (
    <section className="ai-panel">
      <div className="section-title">
        <Bot size={18} />
        <h2>AI 입지 상담</h2>
      </div>
      <textarea
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        rows={4}
        placeholder="예: 광주 북구에서 카페 창업지를 검토하고 싶은데 어디가 좋아?"
      />
      <button className="primary-button" type="button" onClick={askAi} disabled={status === 'loading'}>
        {status === 'loading' ? <Loader2 className="spin" size={17} /> : <Send size={17} />}
        <span>후보지 찾기</span>
      </button>

      {localTop3.length > 0 && (
        <div className="ai-top3">
          {localTop3.map((candidate, index) => (
            <CandidateCard
              key={candidate.candidate_id}
              candidate={candidate}
              rank={index + 1}
              onSelect={onSelectCandidate}
            />
          ))}
        </div>
      )}
    </section>
  )
}
