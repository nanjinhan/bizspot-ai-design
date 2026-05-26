import { ShieldCheck } from 'lucide-react'
import { SAFE_NOTICE_LONG, SAFE_NOTICE_SHORT } from '../utils/safeText.js'

export default function SafeNotice({ compact = false }) {
  return (
    <div className={compact ? 'safe-notice compact' : 'safe-notice'}>
      <ShieldCheck size={18} />
      <p>{compact ? SAFE_NOTICE_SHORT : SAFE_NOTICE_LONG}</p>
    </div>
  )
}
