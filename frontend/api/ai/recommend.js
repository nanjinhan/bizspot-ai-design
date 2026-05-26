import { buildFallbackAnswer, buildPrompt, sanitizeAnswer } from '../_aiPrompt.js'

function hasGeminiKey() {
  return Boolean(process.env.GEMINI_API_KEY)
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
    res.status(204).end()
    return
  }

  if (req.method !== 'POST') {
    res.status(405).json({ fallback: true, error: 'method not allowed' })
    return
  }

  const { question, candidates } = req.body || {}
  if (!Array.isArray(candidates)) {
    res.status(400).json({
      fallback: true,
      answer: buildFallbackAnswer({ candidates: [] }),
      error: 'candidates must be an array',
    })
    return
  }

  const topCandidates = candidates.slice(0, 3)
  if (!hasGeminiKey()) {
    res.status(200).json({
      fallback: true,
      answer: buildFallbackAnswer({ candidates: topCandidates }),
      reason: 'GEMINI_API_KEY is missing',
    })
    return
  }

  try {
    const answer = await callGemini({
      question: String(question || ''),
      candidates: topCandidates,
    })
    res.status(200).json({ fallback: false, answer: sanitizeAnswer(answer) })
  } catch (error) {
    res.status(200).json({
      fallback: true,
      answer: buildFallbackAnswer({ candidates: topCandidates }),
      reason: error instanceof Error ? error.message : 'AI request failed',
    })
  }
}

async function callGemini({ question, candidates }) {
  const model = process.env.GEMMA_MODEL || 'gemma-4-31b-it'
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    model,
  )}:generateContent?key=${encodeURIComponent(process.env.GEMINI_API_KEY)}`

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [
        {
          role: 'user',
          parts: [{ text: buildPrompt({ question, candidates }) }],
        },
      ],
      generationConfig: {
        temperature: 0.2,
        maxOutputTokens: 900,
      },
    }),
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => '')
    throw new Error(`Gemini API responded ${response.status}${errorText ? `: ${errorText.slice(0, 300)}` : ''}`)
  }

  const payload = await response.json()
  const text =
    payload?.candidates?.[0]?.content?.parts
      ?.filter((part) => part?.text && part.thought !== true)
      ?.map((part) => part.text)
      .filter(Boolean)
      .join('\n') || ''

  if (!text.trim()) {
    throw new Error('Gemini API returned empty text')
  }
  return text
}
