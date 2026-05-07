import { useState, useEffect } from 'react'
import type { ScanRun, Listing } from '../types'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'

const STATUS_COLOR: Record<ScanRun['status'], string> = {
  running: 'border-yellow-600 bg-yellow-900/20 text-yellow-300',
  success: 'border-green-700 bg-green-900/20 text-green-300',
  failed: 'border-red-700 bg-red-900/20 text-red-300',
}

function ScanDetail({ run }: { run: ScanRun }) {
  const [listings, setListings] = useState<Listing[] | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    const since = new Date(run.started_at)
    since.setSeconds(since.getSeconds() - 5)
    const until = run.finished_at ? new Date(run.finished_at) : new Date()
    until.setSeconds(until.getSeconds() + 5)

    api.listings.list({
      page_size: 100,
      sort_by: 'first_seen_at',
      sort_dir: 'desc',
      first_seen_after: since.toISOString(),
      first_seen_before: until.toISOString(),
    })
      .then(res => setListings(res.items))
      .finally(() => setLoading(false))
  }, [run.id])

  if (loading) return <div className="px-4 py-3 text-sm text-gray-500">Loading...</div>
  if (!listings) return null

  return (
    <div className="px-4 pb-4 border-t border-gray-700 mt-2 pt-3">
      <p className="text-xs text-gray-500 mb-2">
        {listings.length} new listing{listings.length !== 1 ? 's' : ''} added this scan
      </p>
      {listings.length === 0 && (
        <p className="text-xs text-gray-600">No new listings found in this scan window.</p>
      )}
      <div className="space-y-1">
        {listings.map(l => (
          <div key={l.id} className="flex items-center gap-3 text-xs bg-gray-900 rounded px-3 py-2">
            {l.thumbnail_url && (
              <img src={l.thumbnail_url} alt="" className="w-12 h-9 object-cover rounded shrink-0"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
            )}
            <div className="flex-1 min-w-0">
              <a href={l.url} target="_blank" rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 truncate block">
                {l.title ?? l.listing_id} ↗
              </a>
              <span className="text-gray-500">
                {l.price ? `NT$${l.price.toLocaleString()}/mo` : ''}{l.district ? ` · ${l.district}` : ''}
              </span>
            </div>
            <StatusBadge status={l.status} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ScanHistory() {
  const [runs, setRuns] = useState<ScanRun[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    api.scans.list().then(setRuns)
    const iv = setInterval(() => api.scans.list().then(setRuns), 5000)
    return () => clearInterval(iv)
  }, [])

  const duration = (r: ScanRun) => {
    if (!r.finished_at) return ''
    const ms = new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()
    return `${(ms / 1000).toFixed(0)}s`
  }

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Scan History</h1>
      <div className="space-y-2">
        {runs.map(r => (
          <div
            key={r.id}
            className={`border rounded-lg overflow-hidden ${STATUS_COLOR[r.status]}`}
          >
            {/* Header row — clickable */}
            <button
              className="w-full text-left px-4 py-3 flex items-center gap-4 hover:bg-white/5"
              onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
            >
              <span className="text-lg">
                {r.status === 'running' ? '⟳' : r.status === 'success' ? '✓' : '✕'}
              </span>
              <div className="flex-1">
                <div className="flex items-center gap-3 text-sm font-medium">
                  <span className="capitalize">{r.status}</span>
                  {r.status !== 'running' && (
                    <span className="font-normal text-current/70">
                      {r.new_listings} new / {r.listings_found} found
                      {duration(r) ? ` · ${duration(r)}` : ''}
                    </span>
                  )}
                  {r.status === 'running' && <span className="text-xs font-normal animate-pulse">scanning…</span>}
                </div>
                <p className="text-xs opacity-60 mt-0.5">
                  {new Date(r.started_at).toLocaleString()}
                </p>
              </div>
              {r.errors && (
                <span className="text-xs text-red-400 max-w-xs truncate">{JSON.stringify(r.errors)}</span>
              )}
              <span className="text-xs opacity-50">{expandedId === r.id ? '▲' : '▼'}</span>
            </button>

            {/* Expanded detail */}
            {expandedId === r.id && <ScanDetail run={r} />}
          </div>
        ))}
        {runs.length === 0 && (
          <div className="text-center py-12 text-gray-500">No scan runs yet</div>
        )}
      </div>
    </div>
  )
}
