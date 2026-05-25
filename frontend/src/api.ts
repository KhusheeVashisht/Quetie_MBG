async function requestJson(path: string, init: RequestInit = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...init,
    headers: {
      ...(init.headers || {}),
    },
  })

  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const payload = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    const detail = typeof payload === 'string' ? payload : payload?.detail || payload?.message || response.statusText
    throw new Error(detail || 'Request failed')
  }

  return payload
}

export async function login(username: string, password: string) {
  return requestJson('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
}

export async function createSession(token: string) {
  await requestJson('/api/auth/session', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
}

function _getCookie(name: string) {
  const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return m ? decodeURIComponent(m[2]) : null
}

export function _buildHeaders(method = 'GET') {
  const headers: Record<string,string> = {}
  if (method !== 'GET' && method !== 'HEAD') {
    const csrf = _getCookie('quetie_csrf')
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  return headers
}

export function setTokenFromStorage() {
  try {
    const t = localStorage.getItem('quetie_token')
    if (t) (window as any).api = (window as any).api || {}, (window as any).api.token = t
  } catch (e) {}
}

export function getToken() {
  try {
    return localStorage.getItem('quetie_token')
  } catch (e) {
    return null
  }
}

export async function logout() {
  await requestJson('/api/auth/session', { method: 'DELETE', headers: _buildHeaders('DELETE') })
  try { localStorage.removeItem('quetie_token') } catch(e){}
}

export async function getMe() {
  return requestJson('/api/auth/me', { headers: _buildHeaders('GET') })
}

export async function listAdmins() {
  return requestJson('/api/admins', { headers: _buildHeaders('GET') })
}

export async function getAuditLogs() {
  return requestJson('/api/audit?limit=100', { headers: _buildHeaders('GET') })
}

export async function getHealth() {
  return requestJson('/health', { headers: _buildHeaders('GET') })
}

export async function connectBot() {
  return requestJson('/api/bot/connect', {
    method: 'POST',
    headers: { ..._buildHeaders('POST') },
  })
}

export async function getQueue(skip = 0, limit = 100) {
  return requestJson(`/api/queue?skip=${skip}&limit=${limit}`, { headers: _buildHeaders('GET') })
}

export async function searchQueue(query: string) {
  return requestJson(`/api/queue/search?q=${encodeURIComponent(query)}`, { headers: _buildHeaders('GET') })
}

export async function getQueueStats() {
  return requestJson('/api/queue/stats', { headers: _buildHeaders('GET') })
}

export async function addQueueEntry(payload: { url: string; submitter_username: string; notes?: string }) {
  return requestJson('/api/queue/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._buildHeaders('POST') },
    body: JSON.stringify(payload),
  })
}

export async function markQueuePlaying(entryId: number) {
  return requestJson(`/api/queue/${entryId}/play`, { method: 'POST', headers: _buildHeaders('POST') })
}

export async function markQueueCompleted(entryId: number) {
  return requestJson(`/api/queue/${entryId}/complete`, { method: 'POST', headers: _buildHeaders('POST') })
}

export async function deleteQueueEntry(entryId: number, reason = '') {
  return requestJson(`/api/queue/${entryId}?reason=${encodeURIComponent(reason)}`, { method: 'DELETE', headers: _buildHeaders('DELETE') })
}

export async function reorderQueue(order: number[]) {
  return requestJson('/api/queue/reorder', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._buildHeaders('POST') },
    body: JSON.stringify(order),
  })
}

export async function getBlockedDomains() {
  return requestJson('/api/filters/blocked-domains', { headers: _buildHeaders('GET') })
}

export async function getBlockedKeywords() {
  return requestJson('/api/filters/blocked-keywords', { headers: _buildHeaders('GET') })
}

export async function addBlockedDomain(payload: { domain: string; reason?: string }) {
  return requestJson('/api/filters/blocked-domains', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._buildHeaders('POST') },
    body: JSON.stringify(payload),
  })
}

export async function removeBlockedDomain(domain: string) {
  return requestJson(`/api/filters/blocked-domains/${encodeURIComponent(domain)}`, { method: 'DELETE', headers: _buildHeaders('DELETE') })
}

export async function addBlockedKeyword(payload: { keyword: string; reason?: string; is_regex?: boolean }) {
  return requestJson('/api/filters/blocked-keywords', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._buildHeaders('POST') },
    body: JSON.stringify(payload),
  })
}

export async function removeBlockedKeyword(keyword: string) {
  return requestJson(`/api/filters/blocked-keywords/${encodeURIComponent(keyword)}`, { method: 'DELETE', headers: _buildHeaders('DELETE') })
}
