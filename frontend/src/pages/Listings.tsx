import { useState, useEffect, useCallback, useRef } from 'react'
import { ListingTable } from '../components/ListingTable'
import { api } from '../api/client'
import type { Listing, ListingFilters, ScanRun } from '../types'

const STATUSES = [
  '', 'NEW', 'ACTIVE', 'WATCHED', 'SAVED', 'REJECTED',
  'MISSING_ON_SEARCH', 'UNAVAILABLE', 'ARCHIVED', 'REAPPEARED',
]

function ScanStatus({ runs, onDone }: { runs: ScanRun[]; onDone: () => void }) {
  const latest = runs[0]
  if (!latest) return null

  const age = Date.now() - new Date(latest.started_at).getTime()
  const isRecent = age < 60_000 // within last minute

  if (!isRecent) return null

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
      const res = await api.listings.list(filters)
      setListings(res.items)
      setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { load() }, [load])

  const loadRuns = useCallback(async () => {
    const runs = await api.scans.list()
    setRecentRuns(runs.slice(0, 3))
    // Stop polling when no running scans
    if (!runs.some(r => r.status === 'running')) {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      // Reload listings since scan may have added new ones
      load()
    }
  }, [load])

  const triggerScan = async () => {
    setScanning(true)
    setShowStatus(true)
    try {
      const res = await api.scans.trigger()
      if (res.triggered === 0) {
        alert('No enabled search profiles found. Create one in Search Profiles first.')
        setShowStatus(false)
        return
      }
      // Poll for scan completion every 3 seconds
      await loadRuns()
      pollRef.current = setInterval(loadRuns, 3000)
    } catch (e) {
      alert(`Scan trigger failed: ${e}`)
      setShowStatus(false)
    } finally {
      setScanning(false)
    }
  }

  // Cleanup poll on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold">
          Listings{' '}
          <span className="text-gray-400 text-sm font-normal">({total} total)</span>
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

      <div className="flex flex-wrap gap-3 mb-4 p-3 bg-gray-800 rounded">
        <select
          value={filters.status ?? ''}
          onChange={e => setFilters(f => ({ ...f, status: e.target.value || undefined, page: 1 }))}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
        >
          {STATUSES.map(s => (
            <option key={s} value={s}>{s || 'All Statuses'}</option>
          ))}
        </select>

        <input
          type="number"
          placeholder="Min price"
          value={filters.price_min ?? ''}
          onChange={e => setFilters(f => ({ ...f, price_min: e.target.value ? +e.target.value : undefined, page: 1 }))}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-28"
        />
        <input
          type="number"
          placeholder="Max price"
          value={filters.price_max ?? ''}
          onChange={e => setFilters(f => ({ ...f, price_max: e.target.value ? +e.target.value : undefined, page: 1 }))}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-28"
        />
        <input
          type="number"
          placeholder="Min score"
          value={filters.score_min ?? ''}
          onChange={e => setFilters(f => ({ ...f, score_min: e.target.value ? +e.target.value : undefined, page: 1 }))}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-24"
        />
        <input
          type="number"
          placeholder="Max transit (min)"
          value={filters.transit_max ?? ''}
          onChange={e => setFilters(f => ({ ...f, transit_max: e.target.value ? +e.target.value : undefined, page: 1 }))}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-36"
        />
        <input
          type="text"
          placeholder="Search..."
          value={filters.keyword ?? ''}
          onChange={e => setFilters(f => ({ ...f, keyword: e.target.value || undefined, page: 1 }))}
          className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm w-36"
        />
        <button onClick={load} className="px-3 py-1 bg-gray-600 hover:bg-gray-500 rounded text-sm">
          Apply
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : (
        <ListingTable listings={listings} onRefresh={load} />
      )}

      {total > (filters.page_size ?? 50) && (
        <div className="flex gap-2 mt-4 justify-center">
          <button
            onClick={() => setFilters(f => ({ ...f, page: Math.max(1, (f.page ?? 1) - 1) }))}
            disabled={(filters.page ?? 1) <= 1}
            className="px-3 py-1 bg-gray-700 rounded disabled:opacity-50"
          >
            ←
          </button>
          <span className="px-3 py-1">Page {filters.page}</span>
          <button
            onClick={() => setFilters(f => ({ ...f, page: (f.page ?? 1) + 1 }))}
            disabled={(filters.page ?? 1) * (filters.page_size ?? 50) >= total}
            className="px-3 py-1 bg-gray-700 rounded disabled:opacity-50"
          >
            →
          </button>
        </div>
      )}
    </div>
  )
}
