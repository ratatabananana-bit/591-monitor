import type {
  Listing, ListingsResponse, ListingEvent, ListingFilters,
  SearchProfile, CommuteAnchor, ScanRun
} from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

function buildQuery(params: Record<string, unknown>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  }
  return q.toString() ? `?${q.toString()}` : ''
}

export const api = {
  listings: {
    list: (filters: ListingFilters = {}) =>
      request<ListingsResponse>(`/listings${buildQuery(filters as Record<string, unknown>)}`),

    get: (id: string) => request<Listing>(`/listings/${id}`),

    action: (id: string, action: string) =>
      request<Listing>(`/listings/${id}/action`, {
        method: 'PATCH',
        body: JSON.stringify({ action }),
      }),

    events: (id: string) => request<ListingEvent[]>(`/listings/${id}/events`),
  },

  profiles: {
    list: () => request<SearchProfile[]>('/search-profiles'),
    get: (id: string) => request<SearchProfile>(`/search-profiles/${id}`),
    create: (data: Partial<SearchProfile>) =>
      request<SearchProfile>('/search-profiles', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Partial<SearchProfile>) =>
      request<SearchProfile>(`/search-profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) => request<{ ok: boolean }>(`/search-profiles/${id}`, { method: 'DELETE' }),
  },

  anchors: {
    list: () => request<CommuteAnchor[]>('/commute-anchors'),
    create: (data: Partial<CommuteAnchor>) =>
      request<CommuteAnchor>('/commute-anchors', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Partial<CommuteAnchor>) =>
      request<CommuteAnchor>(`/commute-anchors/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) => request<{ ok: boolean }>(`/commute-anchors/${id}`, { method: 'DELETE' }),
  },

  scans: {
    list: () => request<ScanRun[]>('/scan-runs'),
    trigger: (profileId?: string) =>
      request<{ triggered: number }>(`/scan-runs/trigger${profileId ? `?profile_id=${profileId}` : ''}`, { method: 'POST' }),
    recalculate: () => request<{ status: string }>('/scan-runs/recalculate-commutes', { method: 'POST' }),
  },
}
