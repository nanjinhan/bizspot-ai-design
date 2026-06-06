const cors = require('cors')
const dotenv = require('dotenv')
const express = require('express')
const { resolve } = require('node:path')
const { buildFallbackAnswer, buildPrompt, sanitizeAnswer } = require('./aiPrompt.js')
dotenv.config({ path: resolve(__dirname, '.env') })
dotenv.config({ path: resolve(__dirname, '..', '.env') })

const app = express()
const port = Number(process.env.PORT || 8787)
const allowedOrigins = new Set([
  'http://localhost:5173',
  'http://127.0.0.1:5173',
  'http://localhost:5174',
  'http://127.0.0.1:5174',
])

function hasGeminiKey() {
  return Boolean(process.env.GEMINI_API_KEY) && process.env.BIZSPOT_DISABLE_GEMINI !== '1'
}

app.use(
  cors({
    origin(origin, callback) {
      if (!origin || allowedOrigins.has(origin)) {
        callback(null, true)
        return
      }
      callback(new Error(`CORS origin not allowed: ${origin}`))
    },
  }),
)
app.use(express.json({ limit: '1mb' }))

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    geminiConfigured: hasGeminiKey(),
    model: process.env.GEMMA_MODEL || 'gemini-2.5-flash',
  })
})

app.post('/api/ai/recommend', async (req, res) => {
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
    res.json({
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
    res.json({
      fallback: false,
      answer: sanitizeAnswer(answer),
    })
  } catch (error) {
    res.json({
      fallback: true,
      answer: buildFallbackAnswer({ candidates: topCandidates }),
      reason: error instanceof Error ? error.message : 'AI request failed',
    })
  }
})

async function callGemini({ question, candidates }) {
  const model = process.env.GEMMA_MODEL || 'gemini-2.5-flash'
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

app.listen(port, () => {
  console.log(`BizSpot AI server listening on http://localhost:${port}`)
})
