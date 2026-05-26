import { MapPin } from 'lucide-react'
import { industryLabel } from '../utils/industryLabel.js'

export default function CandidateCard({ candidate, active, rank, onSelect }) {
  if (!candidate) return null

  return (
    <button
      className={active ? 'candidate-card active' : 'candidate-card'}
      type="button"
      onClick={() => onSelect(candidate)}
    >
      <span className="candidate-rank">{rank}</span>
      <span className="candidate-main">
        <strong>{candidate.name}</strong>
        <small>
          <MapPin size={13} />
          {candidate.sigungu} {candidate.dong} · {industryLabel(candidate.recommended_industry)}
        </small>
      </span>
      <span className="candidate-score">{candidate.suitability_score}</span>
    </button>
  )
}
