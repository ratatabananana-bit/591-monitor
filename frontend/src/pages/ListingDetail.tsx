import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import type { Listing, ListingEvent } from '../types'
import { StatusBadge } from '../components/StatusBadge'
import { ScoreBar } from '../components/ScoreBar'
import { CommuteInfo } from '../components/CommuteInfo'
import { api } from '../api/client'

export default function ListingDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [listing, setListing] = useState<Listing | null>(null)
  const [events, setEvents] = useState<ListingEvent[]>([])

  useEffect(() => {
    if (!id) return
    api.listings.get(id).then(setListing)
    api.listings.events(id).then(setEvents)
  }, [id])

  if (!listing) return <div className="text-gray-500 py-12 text-center">Loading...</div>

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm">
        ← Back
      </button>

      <div className="bg-gray-800 rounded-lg p-6 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold">{listing.title ?? 'Untitled'}</h1>
            <p className="text-gray-400 text-sm">{listing.address ?? listing.district}</p>
          </div>
          <StatusBadge status={listing.status} />
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-400">Price</span>
            <p className="font-medium">
              {listing.price != null ? `NT$${listing.price.toLocaleString()}/mo` : '—'}
            </p>
          </div>
          <div>
            <span className="text-gray-400">Size</span>
            <p className="font-medium">{listing.size_ping != null ? `${listing.size_ping}坪` : '—'}</p>
          </div>
          <div>
            <span className="text-gray-400">Type</span>
            <p className="font-medium">{listing.room_type ?? '—'}</p>
          </div>
          <div>
            <span className="text-gray-400">Floor</span>
            <p className="font-medium">{listing.floor ?? '—'}</p>
          </div>
          <div>
            <span className="text-gray-400">Score</span>
            <ScoreBar score={listing.score} />
          </div>
          <div>
            <span className="text-gray-400">First seen</span>
            <p>{new Date(listing.first_seen_at).toLocaleString()}</p>
          </div>
        </div>

        {listing.commute_results.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-gray-400 mb-2">Commute</h2>
            <CommuteInfo results={listing.commute_results} />
          </div>
        )}

        <div className="flex gap-2 flex-wrap">
          {['save', 'watch', 'reject', 'contacted', 'visited'].map(action => (
            <button
              key={action}
              onClick={async () => {
                const l = await api.listings.action(listing.id, action)
                setListing(l)
              }}
              className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm capitalize"
            >
              {action}
            </button>
          ))}
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1 bg-blue-700 hover:bg-blue-600 rounded text-sm"
          >
            View on 591 ↗
          </a>
        </div>
      </div>

      {events.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="font-medium mb-3">Event History</h2>
          <div className="space-y-2">
            {events.map(e => (
              <div key={e.id} className="flex gap-3 text-sm">
                <span className="text-gray-400 text-xs">
                  {new Date(e.created_at).toLocaleString()}
                </span>
                <span className="font-medium">{e.event_type}</span>
                {e.old_value && e.new_value && (
                  <span className="text-gray-400">
                    {JSON.stringify(e.old_value)} → {JSON.stringify(e.new_value)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
