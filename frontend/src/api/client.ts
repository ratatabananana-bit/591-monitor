import type {
  Listing, ListingsResponse, ListingEvent, ListingFilters,
  SearchProfile, CommuteAnchor, ScanRun, TagRule
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

    bulkAction: (ids: string[], action: string) =>
      request<{ updated: number }>('/listings/bulk-action', {
        method: 'POST',
        body: JSON.stringify({ ids, action }),
      }),

    delete: (id: string) => request<{ ok: boolean }>(`/listings/${id}`, { method: 'DELETE' }),

    bulkDelete: (ids: string[]) =>
      request<{ updated: number }>('/listings/bulk-action', {
        method: 'POST',
        body: JSON.stringify({ ids, action: 'delete' }),
      }),

    events: (id: string) => request<ListingEvent[]>(`/listings/${id}/events`),

    viewed: (id: string) => request<Listing>(`/listings/${id}/viewed`, { method: 'POST' }),

    rescrapePhotos: (id: string) =>
      request<Listing>(`/listings/${id}/rescrape-photos`, { method: 'POST' }),
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
    backfillDates: () => request<{ status: string }>('/scan-runs/backfill-dates', { method: 'POST' }),
    backfillPageText: () => request<{ status: string }>('/scan-runs/backfill-page-text', { method: 'POST' }),
    rescore: () => request<{ status: string }>('/scan-runs/rescore', { method: 'POST' }),
    cancel: (id: string) => request<{ status: string }>(`/scan-runs/${id}/cancel`, { method: 'POST' }),
    clearDone: () => request<{ deleted: number }>('/scan-runs/done', { method: 'DELETE' }),
    clearAlerted: () => request<{ deleted: number }>('/scan-runs/alerted', { method: 'DELETE' }),
  },

  logs: {
    fetch: (since: number) =>
      request<LogEntry[]>(`/logs?since=${since}`),
  },

  tagRules: {
    list: () => request<TagRule[]>('/tag-rules'),
    create: (data: Partial<TagRule>) =>
      request<TagRule>('/tag-rules', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Partial<TagRule>) =>
      request<TagRule>(`/tag-rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) => request<{ ok: boolean }>(`/tag-rules/${id}`, { method: 'DELETE' }),
    retagAll: () => request<{ status: string }>('/tag-rules/retag-all', { method: 'POST' }),
  },
}

export interface LogEntry {
  id: number
  t: number
  level: string
  logger: string
  msg: string
}
