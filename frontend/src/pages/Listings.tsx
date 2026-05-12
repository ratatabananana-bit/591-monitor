import { useState, useEffect, useCallback, useRef } from 'react'
import { ListingTable } from '../components/ListingTable'
import type { SortKey, SortDir } from '../components/ListingTable'
import { api } from '../api/client'
import type { Listing, ListingFilters } from '../types'
import { useApp } from '../App'

function loadSort(): { key: SortKey; dir: SortDir } {
  return {
    key: (localStorage.getItem('listing_sort_key') as SortKey) ?? 'score',
    dir: (localStorage.getItem('listing_sort_dir') as SortDir) ?? 'desc',
  }
}

const VIEW_STATUSES: Record<string, string[]> = {
  v_new:      ['NEW'],
  v_active:   ['NEW', 'ACTIVE', 'REAPPEARED', 'MISSING_ON_SEARCH'],
  v_saved:    ['SAVED', 'CHECKING'],
  v_rejected: ['REJECTED'],
  v_delisted: ['MISSING_ON_SEARCH', 'UNAVAILABLE', 'ARCHIVED'],
}

const BULK_ACTIONS = ['save', 'checking', 'reject', 'delete'] as const

// ── Active filters state → chip display ──
interface ActiveFilters {
  price_min?: number
  price_max?: number
  score_min?: number
  transit_max?: number
  keyword?: string
  posted_within_days?: number
}

function chipsFromFilters(f: ActiveFilters) {
  const chips: { label: string; key: keyof ActiveFilters }[] = []
  if (f.price_min) chips.push({ label: `price ≥ NT$${f.price_min.toLocaleString()}`, key: 'price_min' })
  if (f.price_max) chips.push({ label: `price ≤ NT$${f.price_max.toLocaleString()}`, key: 'price_max' })
  if (f.score_min) chips.push({ label: `score ≥ ${f.score_min}`, key: 'score_min' })
  if (f.transit_max) chips.push({ label: `transit ≤ ${f.transit_max}m`, key: 'transit_max' })
  if (f.posted_within_days) chips.push({ label: `posted ≤ ${f.posted_within_days}d ago`, key: 'posted_within_days' })
  if (f.keyword) chips.push({ label: `"${f.keyword}"`, key: 'keyword' })
  return chips
}

// ── Filter add panel ──
type FilterFieldKey = keyof ActiveFilters | 'tag'

function AddFilterPanel({ onAdd, onAddTag, onClose }: {
  onAdd: (key: keyof ActiveFilters, val: number | string) => void
  onAddTag: (tag: string) => void
  onClose: () => void
}) {
  const [field, setField] = useState<FilterFieldKey>('price_max')
  const [val, setVal] = useState('')

  const FIELDS: { key: FilterFieldKey; label: string; type: string; placeholder: string }[] = [
    { key: 'price_max',         label: 'Max price (NT$)',     type: 'number', placeholder: '25000' },
    { key: 'price_min',         label: 'Min price (NT$)',     type: 'number', placeholder: '10000' },
    { key: 'score_min',         label: 'Min score',           type: 'number', placeholder: '70' },
    { key: 'transit_max',       label: 'Max transit (min)',   type: 'number', placeholder: '20' },
    { key: 'posted_within_days',label: 'Posted within (days)',type: 'number', placeholder: '7' },
    { key: 'keyword',           label: 'Keyword',             type: 'text',   placeholder: '捷運' },
    { key: 'tag',               label: 'Tag',                 type: 'text',   placeholder: '+pet-ok' },
  ]

  const submit = () => {
    if (!val) return
    if (field === 'tag') {
      onAddTag(val.startsWith('+') || val.startsWith('-') ? val : val)
    } else {
      onAdd(field, field === 'keyword' ? val : +val)
    }
    setVal('')
    onClose()
  }

  return (
    <div style={{
      position: 'absolute', top: '100%', left: 0, zIndex: 20, marginTop: 4,
      background: 'var(--bg-2)', border: '1px solid var(--border-2)', borderRadius: 6,
      padding: 12, width: 260, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <select
        value={field}
        onChange={e => setField(e.target.value as FilterFieldKey)}
        className="filter-input"
        style={{ width: '100%' }}
      >
        {FIELDS.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
      </select>
      <input
        type={FIELDS.find(f => f.key === field)?.type ?? 'text'}
        placeholder={FIELDS.find(f => f.key === field)?.placeholder}
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && val) submit() }}
        className="filter-input"
        style={{ width: '100%' }}
        autoFocus
      />
      <div style={{ display: 'flex', gap: 6 }}>
        <button className="wb-btn small btn-primary" style={{ flex: 1 }} onClick={submit}>Add</button>
        <button className="wb-btn small ghost" onClick={onClose}>Cancel</button>
      </div>
    </div>
  )
}

// ── Main ──
export default function Listings() {
  const { activeView, setOpenListing, openListing, refreshToken } = useApp()

  const [listings, setListings] = useState<Listing[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 100
  const [loading, setLoading] = useState(false)
  const initialLoadDone = useRef(false)
  const [focusId, setFocusId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulking, setBulking] = useState(false)
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({})
  const [activeTags, setActiveTags] = useState<string[]>([])
  const [showAddFilter, setShowAddFilter] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>(() => loadSort().key)
  const [sortDir, setSortDir] = useState<SortDir>(() => loadSort().dir)

  const statuses = VIEW_STATUSES[activeView] ?? VIEW_STATUSES['v_active']

  const handleSortChange = (key: SortKey, dir: SortDir) => {
    setSortKey(key)
    setSortDir(dir)
    if (key) localStorage.setItem('listing_sort_key', key)
    localStorage.setItem('listing_sort_dir', dir)
  }

  const load = useCallback(async (background = false) => {
    if (!background && !initialLoadDone.current) setLoading(true)
    try {
      const apiFilters: ListingFilters = {
        page,
        page_size: pageSize,
        sort_by: sortKey ?? 'score',
        sort_dir: sortDir,
        ...(activeFilters.price_min && { price_min: activeFilters.price_min }),
        ...(activeFilters.price_max && { price_max: activeFilters.price_max }),
        ...(activeFilters.score_min && { score_min: activeFilters.score_min }),
        ...(activeFilters.transit_max && { transit_max: activeFilters.transit_max }),
        ...(activeFilters.keyword && { keyword: activeFilters.keyword }),
      }

      // posted_within_days: compute first_seen_after date
      if (activeFilters.posted_within_days) {
        const cutoff = new Date(Date.now() - activeFilters.posted_within_days * 86400000)
        apiFilters.first_seen_after = cutoff.toISOString().split('T')[0]
      }

      const res = await api.listings.list({ ...apiFilters, status: statuses.join(',') })
      setListings(res.items)
      setTotal(res.total)
      initialLoadDone.current = true
    } finally {
      setLoading(false)
    }
  }, [statuses, page, activeFilters, sortKey, sortDir])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (initialLoadDone.current) load(true) }, [refreshToken]) // eslint-disable-line

  // Reset on view change
  useEffect(() => {
    setPage(1)
    setSelectedIds(new Set())
    setFocusId(null)
    initialLoadDone.current = false
  }, [activeView])

  // Scroll focused row into view inside .table-wrap container
  useEffect(() => {
    if (!focusId) return
    const el = document.querySelector(`[data-row-id="${focusId}"]`) as HTMLElement | null
    if (!el) return
    const wrap = el.closest('.table-wrap') as HTMLElement | null
    if (!wrap) return
    const thead = el.closest('table')?.querySelector('thead') as HTMLElement | null
    const topOffset = (thead?.offsetHeight ?? 0) + 4
    const elTop = el.offsetTop
    const elBottom = elTop + el.offsetHeight
    const wrapTop = wrap.scrollTop
    const wrapBottom = wrapTop + wrap.clientHeight
    if (elTop - topOffset < wrapTop) {
      wrap.scrollTo({ top: elTop - topOffset, behavior: 'smooth' })
    } else if (elBottom + 4 > wrapBottom) {
      wrap.scrollTo({ top: elBottom + 4 - wrap.clientHeight, behavior: 'smooth' })
    }
  }, [focusId])

  // Keyboard shortcuts — live in Listings so focusId survives ListingTable remounts
  const displayedRef = useRef<Listing[]>([])
  const focusIdRef = useRef<string | null>(null)
  focusIdRef.current = focusId
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      const ls = displayedRef.current
      if (!ls.length) return
      const idx = focusIdRef.current ? ls.findIndex(l => l.id === focusIdRef.current) : -1
      const moveTo = (listing: Listing) => {
        focusIdRef.current = listing.id  // update immediately — don't wait for render
        setFocusId(listing.id)
        setOpenListing(listing)
      }
      if (e.key === 'j' || e.key === 'J') {
        e.preventDefault()
        moveTo(ls[Math.min(idx + 1, ls.length - 1)])
      } else if (e.key === 'k' || e.key === 'K') {
        e.preventDefault()
        moveTo(ls[Math.max(idx - 1, 0)])
      } else if ((e.key === 's' || e.key === 'S') && idx >= 0) {
        e.preventDefault()
        const next = ls[Math.min(idx + 1, ls.length - 1)]
        api.listings.action(ls[idx].id, 'save').then(() => load(true))
        if (next.id !== ls[idx].id) moveTo(next)
      } else if ((e.key === 'r' || e.key === 'R') && idx >= 0) {
        e.preventDefault()
        const next = ls[Math.min(idx + 1, ls.length - 1)]
        api.listings.action(ls[idx].id, 'reject').then(() => load(true))
        if (next.id !== ls[idx].id) moveTo(next)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [setOpenListing, load])

  const bulkAction = async (action: string) => {
    if (selectedIds.size === 0) return
    if (action === 'delete' && !confirm(`Delete ${selectedIds.size} listing(s) permanently?`)) return
    setBulking(true)
    try {
      await api.listings.bulkAction(Array.from(selectedIds), action)
      setSelectedIds(new Set())
      load()
    } finally {
      setBulking(false)
    }
  }

  const addFilter = (key: keyof ActiveFilters, val: number | string) => {
    setActiveFilters(f => ({ ...f, [key]: val }))
    setPage(1)
  }

  const addTagFilter = (tag: string) => {
    setActiveTags(ts => ts.includes(tag) ? ts : [...ts, tag])
  }

  const removeTagFilter = (tag: string) => {
    setActiveTags(ts => ts.filter(t => t !== tag))
  }

  const removeFilter = (key: keyof ActiveFilters) => {
    setActiveFilters(f => { const n = { ...f }; delete n[key]; return n })
    setPage(1)
  }

  const chips = chipsFromFilters(activeFilters)
  const displayed: Listing[] = activeTags.length > 0
    ? listings.filter(l => {
        const tagSet = new Set(l.tags ?? [])
        return activeTags.every(t => tagSet.has(t))
      })
    : listings
  displayedRef.current = displayed

  const handleRowOpen = (listing: Listing) => {
    setOpenListing(listing)
  }

  // Update drawer listing when data reloads — use ref to avoid loop
  const openListingIdRef = useRef<string | null>(null)
  openListingIdRef.current = openListing?.id ?? null
  useEffect(() => {
    if (openListingIdRef.current) {
      const updated = listings.find(l => l.id === openListingIdRef.current)
      if (updated) setOpenListing(updated)
    }
  }, [listings, setOpenListing])

  return (
    <>
      {/* Filter bar */}
      <div className="filterbar" style={{ position: 'relative' }}>
        {chips.map(chip => (
          <div key={chip.key} className="filter-chip active">
            <span className="val">{chip.label}</span>
            <button className="x" onClick={() => removeFilter(chip.key)}>✕</button>
          </div>
        ))}
        {activeTags.map(tag => {
          let label = tag
          if (tag.startsWith('profile:')) label = `profile: ${tag.slice(8)}`
          else if (tag === 'badge:fresh') label = 'FRESH'
          else if (tag === 'badge:stale') label = 'STALE'
          else if (tag === 'badge:new') label = 'NEW'
          else if (tag === 'badge:missing') label = 'MISSING'
          return (
            <div key={`tag:${tag}`} className="filter-chip active">
              <span className="val">{label}</span>
              <button className="x" onClick={() => removeTagFilter(tag)}>✕</button>
            </div>
          )
        })}
        <button className="add-filter" onClick={() => setShowAddFilter(v => !v)}>
          + Filter
        </button>
        {(chips.length > 0 || activeTags.length > 0) && (
          <button className="wb-btn small ghost" onClick={() => { setActiveFilters({}); setActiveTags([]) }}>
            Clear all
          </button>
        )}
        {showAddFilter && (
          <AddFilterPanel onAdd={addFilter} onAddTag={addTagFilter} onClose={() => setShowAddFilter(false)} />
        )}
      </div>

      {/* Bulk bar */}
      {selectedIds.size > 0 && (
        <div className="bulk-bar">
          <span className="bulk-count">{selectedIds.size} selected</span>
          <span className="sep">·</span>
          {BULK_ACTIONS.map(action => (
            <button
              key={action}
              onClick={() => bulkAction(action)}
              disabled={bulking}
              className={'wb-btn small' + (action === 'delete' ? ' danger' : '')}
            >
              {action.charAt(0).toUpperCase() + action.slice(1)}
            </button>
          ))}
          <button
            onClick={() => setSelectedIds(new Set())}
            className="wb-btn small ghost ml-auto"
          >
            Clear (Esc)
          </button>
        </div>
      )}

      {loading ? (
        <div className="empty-pane">Loading…</div>
      ) : (
        <ListingTable
          listings={displayed}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onRowOpen={handleRowOpen}
          onTagClick={addTagFilter}
          focusId={focusId}
          onFocusChange={setFocusId}
          sortKey={sortKey}
          sortDir={sortDir}
          onSortChange={handleSortChange}
        />
      )}

      {/* Pagination */}
      <div className="pagination">
        <span>
          Showing <span className="mono" style={{ color: 'var(--text)' }}>{listings.length}</span>
          {total > listings.length && (
            <> of <span className="mono" style={{ color: 'var(--text)' }}>{total}</span></>
          )}
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          <kbd>J</kbd>/<kbd>K</kbd> <span>next/prev</span>
          <kbd>S</kbd> <span>save</span>
          <kbd>R</kbd> <span>reject</span>
        </div>
        {total > pageSize && (
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button
              className="wb-btn small"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
            >←</button>
            <span className="mono" style={{ fontSize: 12 }}>p{page}</span>
            <button
              className="wb-btn small"
              onClick={() => setPage(p => p + 1)}
              disabled={page * pageSize >= total}
            >→</button>
          </div>
        )}
      </div>
    </>
  )
}
