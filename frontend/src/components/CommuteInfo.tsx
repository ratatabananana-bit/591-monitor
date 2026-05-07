import type { CommuteResult } from '../types'

export function CommuteInfo({ results }: { results: CommuteResult[] }) {
  if (!results.length) return <span className="text-gray-500 text-xs">No data</span>
  return (
    <div className="text-xs space-y-0.5">
      {results.map(r => (
        <div key={r.anchor_id} className="flex gap-2">
          <span className="text-gray-400 truncate max-w-20">{r.anchor_name}:</span>
          <span>{r.transit_minutes != null ? `🚇${r.transit_minutes}m` : '—'}</span>
          <span className="text-gray-500">{r.distance_meters != null ? `${(r.distance_meters / 1000).toFixed(1)}km` : ''}</span>
        </div>
      ))}
    </div>
  )
}
