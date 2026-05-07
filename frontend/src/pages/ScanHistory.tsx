import { useState, useEffect } from 'react'
import type { ScanRun } from '../types'
import { api } from '../api/client'

const STATUS_COLOR: Record<ScanRun['status'], string> = {
  running: 'text-yellow-400',
  success: 'text-green-400',
  failed: 'text-red-400',
}

export default function ScanHistory() {
  const [runs, setRuns] = useState<ScanRun[]>([])

  useEffect(() => { api.scans.list().then(setRuns) }, [])

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-xl font-bold mb-4">Scan History</h1>
      <div className="space-y-2">
        {runs.map(r => (
          <div key={r.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-center">
            <div>
              <div className="flex items-center gap-3">
                <span className={`font-medium capitalize ${STATUS_COLOR[r.status]}`}>{r.status}</span>
                <span className="text-sm text-gray-300">{r.new_listings} new / {r.listings_found} found</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {new Date(r.started_at).toLocaleString()}
                {r.finished_at && ` — ${Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000)}s`}
              </p>
            </div>
            {r.errors && (
              <span className="text-xs text-red-400 max-w-xs truncate">{JSON.stringify(r.errors)}</span>
            )}
          </div>
        ))}
        {runs.length === 0 && (
          <div className="text-center py-12 text-gray-500">No scan runs yet</div>
        )}
      </div>
    </div>
  )
}
