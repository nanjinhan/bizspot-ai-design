export default function handler(_req, res) {
  res.status(200).json({
    ok: true,
    geminiConfigured: Boolean(process.env.GEMINI_API_KEY),
    model: process.env.GEMMA_MODEL || 'gemma-4-31b-it',
  })
}
