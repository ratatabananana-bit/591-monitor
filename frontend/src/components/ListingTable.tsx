import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'
import type { Listing, ListingEvent } from '../types'
import { StatusBadge } from './StatusBadge'
import { ScoreBar } from './ScoreBar'
import { CommuteInfo } from './CommuteInfo'
import { api } from '../api/client'

const col = createColumnHelper<Listing>()

const ACTIONS = ['save', 'watch', 'reject', 'contacted', 'visited'] as const

function fmtDate(d: string | null | undefined) {
  if (!d) return '—'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-CA', { month: '2-digit', day: '2-digit' })
}

function fmtDateTime(d: string | null | undefined) {
  if (!d) return '—'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-CA', { month: '2-digit', day: '2-digit' })
    + ' ' + dt.toLocaleTimeString('en-CA', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function ListingDetail({ listing, onClose, onRefresh }: {
  listing: Listing
  onClose: () => void
  onRefresh: () => void
}) {
  const [events, setEvents] = useState<ListingEvent[] | null>(null)
  const [loading, setLoading] = useState(false)

  if (events === null && !loading) {
    setLoading(true)
    api.listings.events(listing.id).then(ev => { setEvents(ev); setLoading(false) })
  }

  return (
    <tr className="bg-gray-850 border-b border-gray-700">
      <td colSpan={10} className="px-4 py-4">
        <div className="flex gap-6">
          {listing.thumbnail_url && (
            <a href={listing.url} target="_blank" rel="noopener noreferrer" className="shrink-0">
              <img
                src={listing.thumbnail_url}
                alt=""
                className="w-52 h-40 object-cover rounded"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            </a>
          )}

          <div className="flex-1 min-w-0">
            <a href={listing.url} target="_blank" rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 font-medium text-sm mb-2 block">
              {listing.title ?? listing.listing_id} ↗
            </a>

            <div className="grid grid-cols-4 gap-x-6 gap-y-1 text-xs text-gray-300 mb-3">
              <span><span className="text-gray-500">Price </span>{listing.price ? `NT$${listing.price.toLocaleString()}/mo` : '—'}</span>
              <span><span className="text-gray-500">Size </span>{listing.size_ping ? `${listing.size_ping} ping` : '—'}</span>
              <span><span className="text-gray-500">Floor </span>{listing.floor ?? '—'}</span>
              <span><span className="text-gray-500">Type </span>{listing.room_type ?? '—'}</span>
              <span><span className="text-gray-500">District </span>{listing.district ?? '—'}</span>
              <span><span className="text-gray-500">Score </span>{listing.score != null ? `${listing.score.toFixed(0)}/100` : '—'}</span>
              <span><span className="text-gray-500">Listed </span>{fmtDateTime(listing.listing_updated_at)}</span>
              <span><span className="text-gray-500">Checked </span>{fmtDateTime(listing.last_seen_at)}</span>
              <span><span className="text-gray-500">Added </span>{fmtDateTime(listing.first_seen_at)}</span>
            </div>

            {listing.commute_results.length > 0 && (
              <div className="text-xs text-gray-400 mb-3">
                <CommuteInfo results={listing.commute_results} />
              </div>
            )}

            <div className="flex gap-1 flex-wrap mb-3">
              {ACTIONS.map(action => (
                <button key={action}
                  onClick={async () => { await api.listings.action(listing.id, action); onRefresh() }}
                  className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded capitalize">
                  {action}
                </button>
              ))}
              <button onClick={onClose}
                className="px-2 py-1 text-xs bg-gray-600 hover:bg-gray-500 rounded ml-2">
                Close ✕
              </button>
            </div>

            <div className="border-t border-gray-700 pt-2">
              <p className="text-xs text-gray-500 mb-1">History</p>
              {loading && <p className="text-xs text-gray-500">Loading...</p>}
              {events?.length === 0 && <p className="text-xs text-gray-600">No events yet</p>}
              {events?.map(ev => (
                <div key={ev.id} className="text-xs text-gray-400 flex gap-3 py-0.5">
                  <span className="text-gray-600 w-28 shrink-0">{fmtDateTime(ev.created_at)}</span>
                  <span className="capitalize font-medium w-28 shrink-0">{ev.event_type.replace(/_/g, ' ')}</span>
                  {ev.old_value && ev.new_value && (
                    <span className="text-gray-500">{JSON.stringify(ev.old_value)} → {JSON.stringify(ev.new_value)}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
}

export function ListingTable({ listings, onRefresh }: { listings: Listing[]; onRefresh: () => void }) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const columns = [
    col.accessor('thumbnail_url', {
      header: '',
      enableSorting: false,
      cell: info => {
        const url = info.getValue()
        return url
          ? <img src={url} alt="" className="w-14 h-10 object-cover rounded"
              onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
          : <div className="w-14 h-10 bg-gray-700 rounded" />
      },
    }),
    col.accessor('status', {
      header: 'Status',
      cell: info => <StatusBadge status={info.getValue()} />,
    }),
    col.accessor('score', {
      header: 'Score',
      cell: info => <ScoreBar score={info.getValue()} />,
    }),
    col.accessor('title', {
      header: 'Title',
      enableSorting: false,
      cell: info => (
        <span className="block max-w-[220px] truncate text-gray-200" title={info.getValue() ?? ''}>
          {info.getValue() ?? <span className="text-gray-600">{info.row.original.listing_id}</span>}
        </span>
      ),
    }),
    col.accessor('price', {
      header: 'Price',
      cell: info => (info.getValue() != null ? `NT$${info.getValue()!.toLocaleString()}` : '—'),
    }),
    col.accessor('district', {
      header: 'District',
      cell: info => <span className="max-w-[110px] truncate block" title={info.getValue() ?? ''}>{info.getValue() ?? '—'}</span>,
    }),
    col.accessor('size_ping', {
      header: 'Size',
      cell: info => (info.getValue() != null ? `${info.getValue()} ping` : '—'),
    }),
    col.accessor('listing_updated_at', {
      header: 'Listed',
      cell: info => fmtDate(info.getValue()),
    }),
    col.accessor('last_seen_at', {
      header: 'Checked',
      cell: info => fmtDate(info.getValue()),
    }),
    col.accessor('commute_results', {
      header: 'Commute',
      enableSorting: false,
      cell: info => <CommuteInfo results={info.getValue()} />,
    }),
  ]

  const table = useReactTable({
    data: listings,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id} className="border-b border-gray-700">
              {hg.headers.map(header => (
                <th key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  className="text-left px-3 py-2 text-gray-400 font-medium cursor-pointer hover:text-white select-none whitespace-nowrap">
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {header.column.getIsSorted() === 'asc' ? ' ↑' : header.column.getIsSorted() === 'desc' ? ' ↓' : ''}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <>
              <tr key={row.id}
                onClick={() => setExpandedId(expandedId === row.original.id ? null : row.original.id)}
                className={`border-b border-gray-800 hover:bg-gray-800 cursor-pointer ${expandedId === row.original.id ? 'bg-gray-800' : ''}`}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {expandedId === row.original.id && (
                <ListingDetail key={`detail-${row.id}`} listing={row.original}
                  onClose={() => setExpandedId(null)} onRefresh={onRefresh} />
              )}
            </>
          ))}
        </tbody>
      </table>
      {listings.length === 0 && (
        <div className="text-center py-12 text-gray-500">No listings</div>
      )}
    </div>
  )
}
