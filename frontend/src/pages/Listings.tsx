import { useState, useEffect, useCallback } from 'react'
import { ListingTable } from '../components/ListingTable'
import { api } from '../api/client'
import type { Listing, ListingFilters } from '../types'

const STATUSES = [
  '', 'NEW', 'ACTIVE', 'WATCHED', 'SAVED', 'REJECTED',
  'MISSING_ON_SEARCH', 'UNAVAILABLE', 'ARCHIVED', 'REAPPEARED',
]

export default function Listings() {
  const [listings, setListings] = useState<Listing[]>([])
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<ListingFilters>({
    page: 1, page_size: 50, sort_by: 'score', sort_dir: 'desc',
  })
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)

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

  const triggerScan = async () => {
    setScanning(true)
    try {
      const res = await api.scans.trigger()
      alert(`Triggered ${res.triggered} scan(s)`)
    } finally {
      setScanning(false)
    }
  }

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
          {scanning ? 'Scanning...' : '⟳ Scan Now'}
        </button>
      </div>

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
