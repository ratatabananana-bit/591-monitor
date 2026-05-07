import { useState, useEffect, useCallback, useRef } from 'react'
import { ListingTable } from '../components/ListingTable'
import { api } from '../api/client'
import type { Listing, ListingFilters, ScanRun } from '../types'

type Tab = 'active' | 'saved' | 'rejected'

const TAB_STATUSES: Record<Tab, string[]> = {
  active: ['NEW', 'ACTIVE', 'WATCHED', 'REAPPEARED', 'MISSING_ON_SEARCH'],
  saved: ['SAVED', 'CONTACTED', 'VISITED'],
  rejected: ['REJECTED', 'ARCHIVED', 'UNAVAILABLE'],
}

function ScanStatus({ runs, onDone }: { runs: ScanRun[]; onDone: () => void }) {
  const latest = runs[0]
  if (!latest) return null
  const age = Date.now() - new Date(latest.started_at).getTime()
  if (age >= 60_000) return null

  const color =
    latest.status === 'running' ? 'border-yellow-600 bg-yellow-900/30 text-yellow-300' :
    latest.status === 'success' ? 'border-green-600 bg-green-900/30 text-green-300' :
    'border-red-600 bg-red-900/30 text-red-300'

  return (
    <div className={`border rounded px-4 py-2 text-sm flex items-center gap-3 ${color}`}>
      {latest.status === 'running' && <span className="animate-spin">⟳</span>}
      {latest.status === 'success' && <span>✓</span>}
      {latest.status === 'failed' && <span>✕</span>}
      <span>
        Scan {latest.status}
        {latest.status === 'success' && ` — ${latest.new_listings} new / ${latest.listings_found} found`}
        {latest.status === 'failed' && latest.errors && ` — ${JSON.stringify(latest.errors)}`}
      </span>
      {latest.status !== 'running' && (
        <button onClick={onDone} className="ml-auto opacity-60 hover:opacity-100">✕</button>
      )}
    </div>
  )
}

export default function Listings() {
  const [tab, setTab] = useState<Tab>('active')
  const [listings, setListings] = useState<Listing[]>([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<ListingFilters>({
    page: 1, page_size: 50, sort_by: 'score', sort_dir: 'desc',
  })
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [recentRuns, setRecentRuns] = useState<ScanRun[]>([])
  const [showStatus, setShowStatus] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      // Build status filter from tab — use multiple calls and merge if needed
      // API supports single status filter, so we load all and filter client-side for tabs with multiple statuses
      const statuses = TAB_STATUSES[tab]
      if (statuses.length === 1) {
        const res = await api.listings.list({ ...filters, status: statuses[0] })
        setListings(res.items)
        setTotal(res.total)
      } else {
        // Fetch all matching statuses
        const res = await api.listings.list({ ...filters, page_size: 200, status: undefined })
        const filtered = res.items.filter(l => statuses.includes(l.status))
        setListings(filtered)
        setTotal(filtered.length)
      }
    } finally {
      setLoading(false)
    }
  }, [filters, tab])

  useEffect(() => { load() }, [load])

  // Reset to page 1 when tab changes
  useEffect(() => {
    setFilters(f => ({ ...f, page: 1 }))
  }, [tab])

  const loadRuns = useCallback(async () => {
    const runs = await api.scans.list()
    setRecentRuns(runs.slice(0, 3))
    if (!runs.some(r => r.status === 'running')) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      if (tab !== 'rejected') load()
    }
  }, [load, tab])

  const triggerScan = async () => {
    setScanning(true)
    setShowStatus(true)
    try {
      const res = await api.scans.trigger()
      if (res.triggered === 0) {
        alert('No enabled search profiles. Create one in Search Profiles first.')
        setShowStatus(false)
        return
      }
      await loadRuns()
      pollRef.current = setInterval(loadRuns, 3000)
    } catch (e) {
      alert(`Scan failed: ${e}`)
      setShowStatus(false)
    } finally {
      setScanning(false)
    }
  }

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const TAB_LABELS: Record<Tab, string> = {
    active: 'Active',
    saved: 'Saved / Watched',
    rejected: 'Rejected / Archived',
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">
          Listings <span className="text-gray-400 text-sm font-normal">({total})</span>
        </h1>
        <button
          onClick={triggerScan}
          disabled={scanning}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-sm font-medium"
        >
          {scanning ? '⟳ Scanning...' : '⟳ Scan Now'}
        </button>
      </div>

      {showStatus && (
        <div className="mb-4">
          <ScanStatus runs={recentRuns} onDone={() => setShowStatus(false)} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-gray-700">
        {(Object.keys(TAB_LABELS) as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t
                ? 'border-blue-500 text-white'
                : 'border-transparent text-gray-400 hover:text-white'
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* Filters — not shown for rejected tab */}
      {tab !== 'rejected' && (
        <div className="flex flex-wrap gap-3 mb-4 p-3 bg-gray-800 rounded">
          <input type="number" placeholder="Min price"
            value={filters.price_min ?? ''}
            onChange={e => setFilters(f => ({ ...f, price_min: e.target.value ? +e.target.value : undefined, page: 1 }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-28" />
          <input type="number" placeholder="Max price"
            value={filters.price_max ?? ''}
            onChange={e => setFilters(f => ({ ...f, price_max: e.target.value ? +e.target.value : undefined, page: 1 }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-28" />
          <input type="number" placeholder="Min score"
            value={filters.score_min ?? ''}
            onChange={e => setFilters(f => ({ ...f, score_min: e.target.value ? +e.target.value : undefined, page: 1 }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-24" />
          <input type="number" placeholder="Max transit (min)"
            value={filters.transit_max ?? ''}
            onChange={e => setFilters(f => ({ ...f, transit_max: e.target.value ? +e.target.value : undefined, page: 1 }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-36" />
          <input type="text" placeholder="Search..."
            value={filters.keyword ?? ''}
            onChange={e => setFilters(f => ({ ...f, keyword: e.target.value || undefined, page: 1 }))}
            className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-36" />
          <button onClick={load} className="px-3 py-1 bg-gray-600 hover:bg-gray-500 rounded text-sm">
            Apply
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : (
        <ListingTable listings={listings} onRefresh={load} />
      )}

      {total > (filters.page_size ?? 50) && tab !== 'rejected' && (
        <div className="flex gap-2 mt-4 justify-center">
          <button
            onClick={() => setFilters(f => ({ ...f, page: Math.max(1, (f.page ?? 1) - 1) }))}
            disabled={(filters.page ?? 1) <= 1}
            className="px-3 py-1 bg-gray-700 rounded disabled:opacity-50">←</button>
          <span className="px-3 py-1">Page {filters.page}</span>
          <button
            onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) + 1 }))}
            disabled={(filters.page ?? 1) * (filters.page_size ?? 50) >= total}
            className="px-3 py-1 bg-gray-700 rounded disabled:opacity-50">→</button>
        </div>
      )}
    </div>
  )
}
