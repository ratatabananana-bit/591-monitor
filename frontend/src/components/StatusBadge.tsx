import type { ListingStatus } from '../types'

const COLORS: Record<ListingStatus, string> = {
  NEW: 'bg-blue-600',
  ACTIVE: 'bg-green-600',
  SAVED: 'bg-purple-600',
  CHECKING: 'bg-teal-600',
  REJECTED: 'bg-gray-600',
  FILTERED: 'bg-gray-600',
  MISSING_ON_SEARCH: 'bg-orange-600',
  UNAVAILABLE: 'bg-red-700',
  ARCHIVED: 'bg-gray-700',
  REAPPEARED: 'bg-indigo-600',
  STALE: 'bg-gray-500',
  WATCHED: 'bg-yellow-600',
  CONTACTED: 'bg-teal-600',
  VISITED: 'bg-cyan-600',
}

export function StatusBadge({ status }: { status: ListingStatus }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium text-white ${COLORS[status] ?? 'bg-gray-600'}`}>
      {status}
    </span>
  )
}
