import { useState } from 'react'
import type { Listing, CommuteResult } from '../types'

export type SortKey = 'score' | 'price' | 'posted_at' | 'last_seen_at' | 'size_ping' | null
export type SortDir = 'asc' | 'desc'

// ── helpers ──
function fmtNT(n: number | null | undefined) {
  if (n == null) return '—'
  return n >= 10000
    ? 'NT$' + (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + 'k'
    : 'NT$' + n.toLocaleString()
}

function fmtDate(d: string | null | undefined) {
  if (!d) return null
  const dt = new Date(d)
  return dt.toLocaleDateString('en-CA', { month: '2-digit', day: '2-digit' })
}

export function daysSince(d: string | null | undefined) {
  if (!d) return null
  const diff = Date.now() - new Date(d).getTime()
  return Math.floor(diff / 86400000)
}

function relDays(d: string | null | undefined) {
  if (!d) return null
  const days = daysSince(d)
  if (days === null) return null
  if (days === 0) return 'today'
  if (days === 1) return '1d'
  return `${days}d`
}

function parseFloor(floor: string | null) {
  if (!floor) return { cur: null, tot: null }
  const m = floor.match(/(\d+)F\/(\d+)F/)
  if (m) return { cur: m[1], tot: m[2] }
  const m2 = floor.match(/(\d+)/)
  if (m2) return { cur: m2[1], tot: null }
  return { cur: null, tot: null }
}

function bestCommute(results: CommuteResult[]) {
  const withTime = results.filter(r => r.transit_minutes != null || r.scooter_minutes != null)
  if (!withTime.length) return null
  return withTime.reduce((a, b) => {
    const aMin = Math.min(a.transit_minutes ?? 999, a.scooter_minutes ?? 999)
    const bMin = Math.min(b.transit_minutes ?? 999, b.scooter_minutes ?? 999)
    return aMin <= bMin ? a : b
  })
}

function scoreColor(score: number | null) {
  if (score == null) return 'var(--muted-2)'
  if (score >= 80) return 'var(--ok)'
  if (score >= 65) return 'var(--accent)'
  if (score >= 50) return 'var(--warn)'
  return 'var(--muted-2)'
}

const STATUS_DOT: Record<string, string> = {
  NEW:              'var(--accent)',
  ACTIVE:           'var(--ok)',
  REAPPEARED:       'var(--ok)',
  SAVED:            'var(--purple)',
  CHECKING:         'var(--cyan)',
  REJECTED:         'var(--muted-2)',
  MISSING_ON_SEARCH:'var(--warn)',
  UNAVAILABLE:      'var(--danger)',
  ARCHIVED:         'var(--muted-2)',
  STALE:            'var(--muted-2)',
}


// ─────────────────────── Components ──

function ScoreCell({ score }: { score: number | null }) {
  const color = scoreColor(score)
  return (
    <div className="score-cell">
      <div className="score-bar">
        {score != null
          ? <div style={{ width: score + '%', background: color }} />
          : <div style={{ width: '100%', background: 'var(--muted-2)', opacity: 0.2 }} />
        }
      </div>
      <span className="score-num" style={{ color }}>
        {score != null ? score.toFixed(0) : '—'}
      </span>
    </div>
  )
}

function TitleCell({ listing, onTagClick }: { listing: Listing; onTagClick?: (tag: string) => void }) {
  const tags = new Set(listing.tags ?? [])
  const isNew = tags.has('badge:new')
  const isReappeared = tags.has('badge:reappeared')
  const isFresh = tags.has('badge:fresh')
  const isStale = tags.has('badge:stale')
  const isMissing = ['MISSING_ON_SEARCH', 'UNAVAILABLE'].includes(listing.status)

  return (
    <div className="title-cell">
      <div className="title-text" title={listing.title ?? ''}>
        {listing.title ?? <span className="muted">{listing.listing_id}</span>}
      </div>
      <div className="title-meta">
        {listing.matched_profile_names?.map(n => (
          <span key={`m-${n}`} className="profile-pill"
            style={onTagClick ? {cursor:'pointer'} : undefined}
            onClick={onTagClick ? e => { e.stopPropagation(); onTagClick(`profile:${n}`) } : undefined}>+{n}</span>
        ))}
        {listing.rejected_by_profile_names?.map(n => (
          <span key={`r-${n}`} className="profile-pill-filtered">−{n}</span>
        ))}
        {listing.tags?.filter(t => t.startsWith('+')).map(t => (
          <span key={t} className="tag-pill tag-pos" style={onTagClick ? {cursor:'pointer'} : undefined}
            onClick={onTagClick ? e => { e.stopPropagation(); onTagClick(t) } : undefined}>{t}</span>
        ))}
        {listing.tags?.filter(t => t.startsWith('-')).map(t => (
          <span key={t} className="tag-pill tag-neg" style={onTagClick ? {cursor:'pointer'} : undefined}
            onClick={onTagClick ? e => { e.stopPropagation(); onTagClick(t) } : undefined}>{t}</span>
        ))}
        {isReappeared && <span className="badge badge-new"
          style={onTagClick ? {cursor:'pointer'} : undefined}
          onClick={onTagClick ? e => { e.stopPropagation(); onTagClick('badge:reappeared') } : undefined}>BACK</span>}
        {isNew && <span className="badge badge-new"
          style={onTagClick ? {cursor:'pointer'} : undefined}
          onClick={onTagClick ? e => { e.stopPropagation(); onTagClick('badge:new') } : undefined}>NEW</span>}
        {isFresh && <span className="badge badge-fresh"
          style={onTagClick ? {cursor:'pointer'} : undefined}
          onClick={onTagClick ? e => { e.stopPropagation(); onTagClick('badge:fresh') } : undefined}>FRESH</span>}
        {isStale && !isMissing && <span className="badge badge-stale"
          style={onTagClick ? {cursor:'pointer'} : undefined}
          onClick={onTagClick ? e => { e.stopPropagation(); onTagClick('badge:stale') } : undefined}>STALE</span>}
        {isMissing && <span className="badge badge-missing"
          style={onTagClick ? {cursor:'pointer'} : undefined}
          onClick={onTagClick ? e => { e.stopPropagation(); onTagClick('badge:missing') } : undefined}>MISSING</span>}
      </div>
    </div>
  )
}

type CommuteMode = 'transit' | 'scooter' | 'distance'

function CommuteCell({ results, mode }: { results: Listing['commute_results'], mode: CommuteMode }) {
  const best = bestCommute(results)
  if (!best) return <span className="muted small mono">—</span>

  let value: string
  if (mode === 'transit') {
    value = best.transit_minutes != null ? `${best.transit_minutes}m` : '—'
  } else if (mode === 'scooter') {
    value = best.scooter_minutes != null ? `${best.scooter_minutes}m` : '—'
  } else {
    const m = best.scooter_distance_meters
    value = m != null ? (m >= 1000 ? `${(m / 1000).toFixed(1)}km` : `${m}m`) : '—'
  }

  const others = results.filter(r => r.transit_minutes != null || r.scooter_minutes != null).length - 1
  return (
    <div className="commute-cell">
      <span className="mono">{value}</span>
      <span className="muted small">{best.anchor_name}</span>
      {others > 0 && <span className="commute-more">+{others}</span>}
    </div>
  )
}

function PostedCell({ listing }: { listing: Listing }) {
  const dateStr = listing.posted_at ?? listing.listing_updated_at
  const rel = relDays(dateStr)
  const fmt = fmtDate(dateStr)
  const approx = !listing.posted_at && !!listing.listing_updated_at
  return (
    <div className="date-cell">
      <div className="date-main">{rel ?? '—'}{approx ? '~' : ''}</div>
      {fmt && <div className="date-sub">{fmt}{approx ? '~' : ''}</div>}
    </div>
  )
}

function CheckedCell({ listing }: { listing: Listing }) {
  const dt = new Date(listing.last_seen_at)
  return (
    <div className="date-cell">
      <div className="date-main">{dt.toLocaleDateString('en-CA', { month: '2-digit', day: '2-digit' })}</div>
      <div className="date-sub">{dt.toLocaleTimeString('en-CA', { hour: '2-digit', minute: '2-digit', hour12: false })}</div>
    </div>
  )
}

// ─────────────────────── Table ──

const COLS: { key: SortKey; label: string; alwaysOn?: boolean }[] = [
  { key: 'score',       label: 'Score' },
  { key: null,          label: 'Listing' },
  { key: 'price',       label: 'Price' },
  { key: null,          label: '$/ping' },
  { key: null,          label: 'Type' },
  { key: 'size_ping',   label: 'Size' },
  { key: null,          label: 'Floor' },
  { key: null,          label: 'Area' },
  { key: null,          label: 'Commute' },
  { key: 'posted_at',   label: 'Posted' },
  { key: 'last_seen_at',label: 'Checked' },
]

export function ListingTable({
  listings,
  selectedIds,
  onSelectionChange,
  onRowOpen,
  onTagClick,
  focusId,
  onFocusChange,
  sortKey,
  sortDir,
  onSortChange,
}: {
  listings: Listing[]
  selectedIds: Set<string>
  onSelectionChange: (ids: Set<string>) => void
  onRowOpen: (listing: Listing) => void
  onTagClick?: (tag: string) => void
  focusId?: string | null
  onFocusChange?: (id: string) => void
  sortKey: SortKey
  sortDir: SortDir
  onSortChange: (key: SortKey, dir: SortDir) => void
}) {
  const [density, setDensity] = useState<'compact' | 'cozy' | 'comfy'>('compact')
  const [commuteMode, setCommuteMode] = useState<CommuteMode>(
    () => (localStorage.getItem('commute_mode') as CommuteMode) ?? 'transit'
  )

  // Server sorts; render as-is
  const sorted = listings

  const allSelected = listings.length > 0 && listings.every(l => selectedIds.has(l.id))
  const someSelected = listings.some(l => selectedIds.has(l.id))

  function toggleSort(key: SortKey) {
    if (!key) return
    if (sortKey === key) onSortChange(key, sortDir === 'asc' ? 'desc' : 'asc')
    else onSortChange(key, 'desc')
  }

  function toggleAll() {
    const next = new Set(selectedIds)
    if (allSelected) listings.forEach(l => next.delete(l.id))
    else listings.forEach(l => next.add(l.id))
    onSelectionChange(next)
  }

  function toggleOne(e: React.MouseEvent, id: string) {
    e.stopPropagation()
    const next = new Set(selectedIds)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onSelectionChange(next)
  }

  function sortInd(key: SortKey) {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' ↑' : ' ↓'
  }

  return (
    <>
      {/* Toolbar */}
      <div className="toolbar">
        <span className="res-count">
          <strong>{listings.length}</strong> listing{listings.length !== 1 ? 's' : ''}
        </span>
        {sortKey && (
          <>
            <span style={{ width: 1, height: 16, background: 'var(--border)', display: 'inline-block' }} />
            <span className="muted" style={{ fontSize: 12 }}>
              Sort: <strong style={{ color: 'var(--text)' }}>{sortKey} {sortDir === 'desc' ? '↓' : '↑'}</strong>
            </span>
          </>
        )}
        <div style={{ flex: 1 }} />
        <div className="seg">
          {(['compact', 'cozy', 'comfy'] as const).map(d => (
            <button key={d} className={density === d ? 'on' : ''} onClick={() => setDensity(d)}>
              {d.charAt(0).toUpperCase() + d.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <table className="list">
          <thead>
            <tr>
              <th className="c-rail" />
              <th className="c-check" onClick={toggleAll} style={{ cursor: 'pointer' }}>
                <span className={'wb-check' + (allSelected ? ' on' : someSelected ? ' indet' : '')} />
              </th>
              {COLS.map(col => (
                <th
                  key={col.label}
                  onClick={() => toggleSort(col.key)}
                  style={{ cursor: col.key ? 'pointer' : 'default' }}
                >
                  {col.label === 'Commute'
                    ? <div className="commute-header">
                        <span>Commute</span>
                        <div className="seg" onClick={e => e.stopPropagation()}>
                          {(['transit', 'scooter', 'distance'] as CommuteMode[]).map(m => (
                            <button
                              key={m}
                              className={commuteMode === m ? 'on' : ''}
                              onClick={() => { setCommuteMode(m); localStorage.setItem('commute_mode', m) }}
                            >
                              {m === 'transit' ? 'T' : m === 'scooter' ? 'S' : 'D'}
                            </button>
                          ))}
                        </div>
                      </div>
                    : col.label}
                  {col.key && <span className="sort-ind">{sortInd(col.key)}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => {
              const dot = STATUS_DOT[row.status] ?? 'var(--muted-2)'
              const isSel = selectedIds.has(row.id)
              const isFocus = focusId === row.id
              const isDim = ['MISSING_ON_SEARCH', 'UNAVAILABLE', 'ARCHIVED', 'REJECTED'].includes(row.status)
              const fl = parseFloor(row.floor)
              const pp = row.price && row.size_ping ? Math.round(row.price / row.size_ping) : null

              return (
                <tr
                  key={row.id}
                  data-row-id={row.id}
                  className={'row' + (isSel ? ' sel' : '') + (isFocus ? ' focus' : '') + (isDim ? ' dim' : '')}
                  data-density={density}
                  onClick={() => { onFocusChange?.(row.id); onRowOpen(row) }}
                >
                  <td className="c-rail" style={{ background: dot }} />
                  <td className="c-check" onClick={e => toggleOne(e, row.id)}>
                    <span className={'wb-check' + (isSel ? ' on' : '')} />
                  </td>
                  <td><ScoreCell score={row.score} /></td>
                  <td className="c-title"><TitleCell listing={row} onTagClick={onTagClick} /></td>
                  <td><span className="price-main">{fmtNT(row.price)}</span></td>
                  <td className="mono muted" style={{ fontSize: 12 }}>
                    {pp != null ? pp.toLocaleString() : '—'}
                    {pp != null && <span className="muted small">/p</span>}
                  </td>
                  <td>
                    {row.room_type
                      ? <span className="type-chip">{row.room_type}</span>
                      : <span className="muted">—</span>}
                  </td>
                  <td className="mono">
                    {row.size_ping != null ? <>{row.size_ping}<span className="muted small">p</span></> : '—'}
                  </td>
                  <td className="c-floor mono">
                    {fl.cur != null
                      ? <>{fl.cur}{fl.tot && <span className="tot">/{fl.tot}</span>}</>
                      : <span className="muted">—</span>}
                  </td>
                  <td>
                    <div className="area-cell">
                      {row.district ? (() => {
                        const q = row.address || row.district
                        const href = q
                          ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
                          : `https://www.google.com/maps?q=${row.lat},${row.lng}`
                        return (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="area-main map-link"
                            onClick={e => e.stopPropagation()}
                          >
                            {row.district}
                          </a>
                        )
                      })() : <span className="muted">—</span>}
                    </div>
                  </td>
                  <td><CommuteCell results={row.commute_results} mode={commuteMode} /></td>
                  <td><PostedCell listing={row} /></td>
                  <td><CheckedCell listing={row} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {listings.length === 0 && (
          <div className="empty-pane">No listings</div>
        )}
      </div>
    </>
  )
}
