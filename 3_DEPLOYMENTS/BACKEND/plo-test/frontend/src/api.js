// api.js — centralised API helpers

const BASE = ''  // same origin in prod; Vite proxy in dev

// Attach auth token to every request
function authHeaders(extra = {}) {
  const token = localStorage.getItem('auth_token') || ''
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'X-Auth-Token': token } : {}),
    ...extra,
  }
}

export async function startEngine({ variant, hands, names }) {
  const res = await fetch(`${BASE}/api/run`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ variant, hands, names }),
  })
  return res.json()
}

export async function fetchResults(jobId) {
  const res = await fetch(`${BASE}/api/results/${jobId}`, {
    headers: authHeaders(),
  })
  return res.json()
}

export async function validateHands({ variant, hands, names }) {
  const res = await fetch(`${BASE}/api/validate`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ variant, hands, names }),
  })
  return res.json()
}

export async function fixCard({ variant, hands, names, slot, position, replacement }) {
  const res = await fetch(`${BASE}/api/fix`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ variant, hands, names, slot, position, replacement }),
  })
  return res.json()
}

export async function createSession() {
  const res = await fetch(`${BASE}/create`, {
    headers: authHeaders(),
  })
  return res.json()
}

export function downloadResults(jobId) {
  window.open(`${BASE}/api/download/${jobId}`, '_blank')
}

/**
 * Start a batch engine run (multiple samples separated by ---).
 * Returns { job_id, batch: true, total_samples } or { job_id } for single.
 */
export async function startBatchEngine({ variant, hands, names }) {
  const res = await fetch(`${BASE}/api/run-batch`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ variant, hands, names }),
  })
  return res.json()
}

/**
 * Subscribe to the SSE stream for a job.
 * onLine(line: string) called for each line
 * onDone(exitCode: number) called when __EXIT__ received
 * onError(msg) called on __ERROR__
 * Returns a cleanup function.
 */
export function subscribeStream(jobId, { onLine, onDone, onError }) {
  const token = localStorage.getItem('auth_token') || ''
  const url   = token
    ? `${BASE}/api/stream/${jobId}?token=${encodeURIComponent(token)}`
    : `${BASE}/api/stream/${jobId}`
  const es = new EventSource(url)
  es.onmessage = (e) => {
    let line
    try {
      const parsed = JSON.parse(e.data)
      line = typeof parsed === 'string' ? parsed : JSON.stringify(parsed)
    } catch { line = e.data }
    if (line.includes('__EXIT__')) {
      const code = parseInt(line.match(/__EXIT__(\d+)__/)?.[1] ?? '0')
      es.close()
      onDone?.(code)
    } else if (line.includes('__ERROR__') || line.startsWith('[ERROR:')) {
      es.close()
      onError?.(line)
    } else if (line.includes('__TIMEOUT__') || line === '[TIMEOUT]') {
      es.close()
      onError?.('Stream timed out')
    } else {
      onLine?.(line)
    }
  }
  // Handle named 'done' event from production backend
  es.addEventListener('done', () => {
    es.close()
    onDone?.(0)
  })
  es.onerror = () => {
    es.close()
    onError?.('SSE connection error')
  }
  return () => es.close()
}
