import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Listing } from '../types'
import { StatusBadge } from './StatusBadge'
import { ScoreBar } from './ScoreBar'
import { CommuteInfo } from './CommuteInfo'
import { api } from '../api/client'

const col = createColumnHelper<Listing>()

const ACTIONS = ['save', 'watch', 'reject', 'contacted', 'visited'] as const

export function ListingTable({ listings, onRefresh }: { listings: Listing[]; onRefresh: () => void }) {
  const navigate = useNavigate()
  const [sorting, setSorting] = useState<SortingState>([])

  const columns = [
    col.accessor('status', {
      header: 'Status',
      cell: info => <StatusBadge status={info.getValue()} />,
    }),
    col.accessor('score', {
      header: 'Score',
      cell: info => <ScoreBar score={info.getValue()} />,
    }),
    col.accessor('price', {
      header: 'Price',
      cell: info => (info.getValue() != null ? `NT$${info.getValue()!.toLocaleString()}` : '—'),
    }),
    col.accessor('district', {
      header: 'District',
      cell: info => info.getValue() ?? '—',
    }),
    col.accessor('size_ping', {
      header: 'Size',
      cell: info => (info.getValue() != null ? `${info.getValue()}坪` : '—'),
    }),
    col.accessor('first_seen_at', {
      header: 'Seen',
      cell: info => new Date(info.getValue()).toLocaleDateString(),
    }),
    col.accessor('commute_results', {
      header: 'Commute',
      enableSorting: false,
      cell: info => <CommuteInfo results={info.getValue()} />,
    }),
    col.display({
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <div className="flex gap-1 flex-wrap">
          {ACTIONS.map(action => (
            <button
              key={action}
              onClick={async e => {
                e.stopPropagation()
                await api.listings.action(row.original.id, action)
                onRefresh()
              }}
              className="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 rounded capitalize"
            >
              {action}
            </button>
          ))}
          <a
            href={row.original.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="px-2 py-0.5 text-xs bg-blue-700 hover:bg-blue-600 rounded"
          >
            591 ↗
          </a>
        </div>
      ),
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
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  className="text-left px-3 py-2 text-gray-400 font-medium cursor-pointer hover:text-white select-none"
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {header.column.getIsSorted() === 'asc'
                    ? ' ↑'
                    : header.column.getIsSorted() === 'desc'
                      ? ' ↓'
                      : ''}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr
              key={row.id}
              onClick={() => navigate(`/listings/${row.original.id}`)}
              className="border-b border-gray-800 hover:bg-gray-800 cursor-pointer"
            >
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {listings.length === 0 && (
        <div className="text-center py-12 text-gray-500">No listings found</div>
      )}
    </div>
  )
}
