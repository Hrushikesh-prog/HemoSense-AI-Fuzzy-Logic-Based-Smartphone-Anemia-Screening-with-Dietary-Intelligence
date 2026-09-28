// Thin client for the HemoSense FastAPI server (see api/main.py).
const BASE = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

export const MIN_IMAGES = 2
export const MAX_IMAGES = 10

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.status = status
    this.body = body
  }
}

function describe(body, status) {
  if (!body) return `Request failed (${status})`
  const d = body.detail
  if (typeof d === 'string') {
    if (d === 'model_unavailable' || d === 'llm_unavailable') return body.error || d
    return d
  }
  if (d && typeof d === 'object' && d.message) return d.message
  if (Array.isArray(d)) return d.map((e) => e.msg).join('; ')
  return body.error || `Request failed (${status})`
}

async function request(path, options) {
  let res
  try {
    res = await fetch(`${BASE}${path}`, options)
  } catch {
    throw new ApiError('Cannot reach the HemoSense API. Is the server running on port 8000?', 0)
  }
  const text = await res.text()
  let body = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = { detail: text }
  }
  if (!res.ok) throw new ApiError(describe(body, res.status), res.status, body)
  return body
}

export const getHealth = () => request('/health')

export const getSymptoms = () => request('/symptoms')

export function screenBatch(files, userContext) {
  const form = new FormData()
  files.forEach((f) => form.append('images', f))
  form.append('data', JSON.stringify({ user_context: userContext }))
  return request('/screen/batch', { method: 'POST', body: form })
}

export function getDietRecommendations(aggregate, userContext) {
  const form = new FormData()
  form.append(
    'data',
    JSON.stringify({
      screening: {
        predicted_hb_gdl: aggregate.predicted_hb_gdl,
        severity_class: aggregate.severity_class,
        anemic: aggregate.anemic,
      },
      user_context: userContext,
    }),
  )
  return request('/diet/recommendations', { method: 'POST', body: form })
}
