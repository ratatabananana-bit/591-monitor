import { useState, useEffect } from 'react'
import type { Listing, ListingEvent } from '../types'
import { api } from '../api/client'

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

function fmtNT(n: number | null | undefined) {
  if (n == null) return '—'
  return 'NT$' + n.toLocaleString()
}

function fmtDate(d: string | null | undefined) {
  if (!d) return '—'
  const dt = new Date(d)
  return dt.toLocaleDateString('en-CA', { month: '2-digit', day: '2-digit' })
    + ' ' + dt.toLocaleTimeString('en-CA', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function ppPing(price: number | null | undefined, size: number | null | undefined) {
  if (!price || !size) return null
  return Math.round(price / size)
}

function scoreColor(s: number | null) {
  if (s == null) return 'var(--muted-2)'
  if (s >= 80) return 'var(--ok)'
  if (s >= 65) return 'var(--accent)'
  if (s >= 50) return 'var(--warn)'
  return 'var(--muted-2)'
}

function mapsUrl(listing: Listing): string {
  const q = listing.address || listing.district
  if (q) return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`
  if (listing.lat && listing.lng) return `https://www.google.com/maps?q=${listing.lat},${listing.lng}`
  return ''
}

const SCORE_COMPONENTS = [
  { label: 'Price',     weight: 30 },
  { label: 'Freshness', weight: 20 },
  { label: 'Commute',   weight: 35 },
  { label: 'Size',      weight: 15 },
]


export function DetailDrawer({
  listing,
  onClose,
  onRefresh,
}: {
  listing: Listing
  onClose: () => void
  onRefresh: () => void
}) {
  const [events, setEvents] = useState<ListingEvent[] | null>(null)
  const [evLoading, setEvLoading] = useState(false)
  const [imgIdx, setImgIdx] = useState(0)
  const [failedCount, setFailedCount] = useState(0)
  const [lightbox, setLightbox] = useState(false)
  const [actioning, setActioning] = useState(false)
  const [rescraping, setRescraping] = useState(false)
  const [localImageUrls, setLocalImageUrls] = useState<string[] | null>(null)

  // Reload events and reset image index whenever listing changes
  useEffect(() => {
    setEvents(null)
    setImgIdx(0)
    setFailedCount(0)
    setLocalImageUrls(null)
    setEvLoading(true)
    let cancelled = false
    api.listings.events(listing.id).then(ev => {
      if (!cancelled) { setEvents(ev); setEvLoading(false) }
    })
    // Mark as viewed — NEW → ACTIVE so badge clears after user opens it
    if (listing.status === 'NEW') {
      api.listings.viewed(listing.id).then(() => onRefresh())
    }
    return () => { cancelled = true }
  }, [listing.id])

  const rawUrls = localImageUrls ?? listing.image_urls
  const images = rawUrls?.length > 0
    ? rawUrls
    : listing.thumbnail_url ? [listing.thumbnail_url] : []

  // Close lightbox on Escape
  useEffect(() => {
    if (!lightbox) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightbox(false)
      if (e.key === 'ArrowLeft') setImgIdx(i => (i - 1 + images.length) % images.length)
      if (e.key === 'ArrowRight') setImgIdx(i => (i + 1) % images.length)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [lightbox, images.length])

  const prevImg = (e: React.MouseEvent) => {
    e.stopPropagation()
    setImgIdx(i => (i - 1 + images.length) % images.length)
  }
  const nextImg = (e: React.MouseEvent) => {
    e.stopPropagation()
    setImgIdx(i => (i + 1) % images.length)
  }

  const doAction = async (action: string) => {
    setActioning(true)
    try {
      await api.listings.action(listing.id, action)
      onRefresh()
    } finally {
      setActioning(false)
    }
  }

  const doDelete = async () => {
    if (!confirm('Delete this listing permanently?')) return
    await api.listings.delete(listing.id)
    onClose()
    onRefresh()
  }

  const doRescrapePhotos = async () => {
    setRescraping(true)
    setImgIdx(0)
    setFailedCount(0)
    try {
      const updated = await api.listings.rescrapePhotos(listing.id)
      setLocalImageUrls(updated.image_urls ?? [])
    } catch (e) {
      alert('Rescrape failed — listing may be unavailable on 591.')
    } finally {
      setRescraping(false)
    }
  }

  const dot = STATUS_DOT[listing.status] ?? 'var(--muted-2)'
  const pp = ppPing(listing.price, listing.size_ping)
  const scoreCol = scoreColor(listing.score)
  const mapHref = mapsUrl(listing)

  let floorDisplay = listing.floor ?? '—'
  if (listing.floor) {
    const m = listing.floor.match(/(\d+)F\/(\d+)F/)
    if (m) floorDisplay = `${m[1]} / ${m[2]}`
  }

  return (
    <aside className="drawer">
      {/* Header */}
      <div className="drawer-head">
        <div className="drawer-head-l">
          <span className="status-dot" style={{ background: dot }} />
          <span className="status-label">{listing.status}</span>
          <span className="muted small mono" style={{ marginLeft: 4 }}>· {listing.listing_id}</span>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close">✕</button>
      </div>

      <div className="drawer-body">
        {/* Photo */}
        <div className="drawer-photo">
          {images.length > 0 && failedCount < images.length ? (
            <>
              <img
                src={images[imgIdx]}
                alt=""
                style={{ cursor: 'zoom-in' }}
                onClick={() => setLightbox(true)}
                onError={() => setFailedCount(c => c + 1)}
              />
              {images.length > 1 && (
                <>
                  <span className="photo-label mono">{imgIdx + 1} / {images.length}</span>
                  <div className="photo-nav">
                    <button className="photo-nav-btn" onClick={prevImg}>‹</button>
                    <button className="photo-nav-btn" onClick={nextImg}>›</button>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="drawer-photo-placeholder">
              <span className="muted small">No photos</span>
            </div>
          )}
        </div>

        {/* Lightbox */}
        {lightbox && (
          <div
            className="lightbox-backdrop"
            onClick={() => setLightbox(false)}
          >
            <img
              src={images[imgIdx]}
              alt=""
              className="lightbox-img"
              onClick={e => e.stopPropagation()}
            />
            {images.length > 1 && (
              <>
                <button className="lightbox-nav lightbox-prev" onClick={e => { e.stopPropagation(); prevImg(e) }}>‹</button>
                <button className="lightbox-nav lightbox-next" onClick={e => { e.stopPropagation(); nextImg(e) }}>›</button>
                <span className="lightbox-label mono">{imgIdx + 1} / {images.length}</span>
              </>
            )}
            <button className="lightbox-close" onClick={() => setLightbox(false)}>✕</button>
          </div>
        )}

        {/* Title */}
        <div>
          <h2 className="drawer-title">
            {listing.title ?? listing.listing_id}
          </h2>
          {listing.district && (
            <div className="drawer-subtitle">
              {mapHref
                ? <a href={mapHref} target="_blank" rel="noopener noreferrer" className="map-link">
                    {listing.district} ↗
                  </a>
                : listing.district}
            </div>
          )}
          {(listing.matched_profile_names?.length > 0 || listing.rejected_by_profile_names?.length > 0) && (
            <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {listing.matched_profile_names?.map(n => (
                <span key={`m-${n}`} className="profile-pill">+{n}</span>
              ))}
              {listing.rejected_by_profile_names?.map(n => (
                <span key={`r-${n}`} className="profile-pill-filtered">−{n}</span>
              ))}
            </div>
          )}
          {listing.tags?.length > 0 && (
            <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {listing.tags.filter(t => t.startsWith('+')).map(t => (
                <span key={t} className="tag-pill tag-pos">{t}</span>
              ))}
              {listing.tags.filter(t => t.startsWith('-')).map(t => (
                <span key={t} className="tag-pill tag-neg">{t}</span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="drawer-actions">
          <a href={listing.url} target="_blank" rel="noopener noreferrer" className="wb-btn btn-primary">
            Open in 591 ↗
          </a>
          <button className="wb-btn" onClick={() => doAction('save')} disabled={actioning}>Save</button>
          <button className="wb-btn" onClick={() => doAction('reject')} disabled={actioning}>Reject</button>
          <button className="wb-btn" onClick={doRescrapePhotos} disabled={rescraping} title="Re-fetch photos from 591">
            {rescraping ? 'Scraping…' : 'Rescrape Photos'}
          </button>
          <button className="wb-btn danger" onClick={doDelete}>Delete</button>
        </div>

        {/* KV grid */}
        <div className="kv-grid">
          <div className="kv">
            <span className="kv-label">Price</span>
            <span className="kv-val mono">{fmtNT(listing.price)}<span className="muted">/mo</span></span>
          </div>
          <div className="kv">
            <span className="kv-label">Per ping</span>
            <span className="kv-val mono">{pp != null ? fmtNT(pp) : '—'}</span>
          </div>
          <div className="kv">
            <span className="kv-label">Size</span>
            <span className="kv-val mono">{listing.size_ping != null ? `${listing.size_ping} ping` : '—'}</span>
          </div>
          <div className="kv">
            <span className="kv-label">Type</span>
            <span className="kv-val">{listing.room_type ?? '—'}</span>
          </div>
          <div className="kv">
            <span className="kv-label">Floor</span>
            <span className="kv-val mono">{floorDisplay}</span>
          </div>
          <div className="kv">
            <span className="kv-label">Posted</span>
            <span className="kv-val mono" style={{ fontSize: 12 }}>
              {listing.posted_at
                ? fmtDate(listing.posted_at)
                : listing.listing_updated_at
                  ? fmtDate(listing.listing_updated_at) + ' ~'
                  : '—'}
            </span>
          </div>
          <div className="kv">
            <span className="kv-label">Checked</span>
            <span className="kv-val mono" style={{ fontSize: 12 }}>{fmtDate(listing.last_seen_at)}</span>
          </div>
          <div className="kv">
            <span className="kv-label">First seen</span>
            <span className="kv-val mono" style={{ fontSize: 12 }}>{fmtDate(listing.first_seen_at)}</span>
          </div>
          {listing.address && (
            <div className="kv span2">
              <span className="kv-label">Address</span>
              {mapHref
                ? <a href={mapHref} target="_blank" rel="noopener noreferrer" className="kv-val map-link">
                    {listing.address} ↗
                  </a>
                : <span className="kv-val">{listing.address}</span>}
            </div>
          )}
        </div>

        {/* Score breakdown */}
        <section className="dr-section">
          <div className="dr-section-head">Score</div>
          <div className="score-breakdown">
            <div className="score-big">
              <span className="score-big-num" style={{ color: scoreCol }}>
                {listing.score != null ? listing.score.toFixed(0) : '—'}
              </span>
              <span className="muted small" style={{ marginTop: 2 }}>/100</span>
            </div>
            <div className="score-bars">
              {SCORE_COMPONENTS.map(c => {
                const key = c.label.toLowerCase() as keyof NonNullable<typeof listing.score_breakdown>
                const val = listing.score_breakdown?.[key] ?? null
                const col = scoreColor(val)
                return (
                  <div key={c.label} className="score-row">
                    <span className="muted small">{c.label} <span style={{ color: 'var(--muted-2)' }}>{c.weight}%</span></span>
                    <div className="score-bar">
                      <div style={{ width: (val ?? 0) + '%', background: col }} />
                    </div>
                    <span className="mono small" style={{ textAlign: 'right', color: col }}>
                      {val != null ? val.toFixed(0) : '—'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        {/* Commute */}
        <section className="dr-section">
          <div className="dr-section-head">Commute</div>
          {listing.commute_results.length > 0 ? (
            <table className="mini-table">
              <thead>
                <tr>
                  <th>Anchor</th>
                  <th className="r">Transit</th>
                  <th className="r">Scooter</th>
                  <th className="r">Distance</th>
                </tr>
              </thead>
              <tbody>
                {listing.commute_results.map(c => (
                  <tr key={c.anchor_id}>
                    <td>{c.anchor_name}</td>
                    <td className="mono r">{c.transit_minutes != null ? `${c.transit_minutes}m` : '—'}</td>
                    <td className="mono r muted">{c.scooter_minutes != null ? `${c.scooter_minutes}m` : '—'}</td>
                    <td className="mono r muted">{c.scooter_distance_meters != null ? `${(c.scooter_distance_meters / 1000).toFixed(1)}km` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="dr-placeholder">
              No commute data — add anchors in Config → Commute Anchors, then rescan.
            </div>
          )}
        </section>

        {/* Facilities */}
        <section className="dr-section">
          <div className="dr-section-head">Facilities</div>
          {listing.facilities?.length > 0 ? (
            <div className="fac-row" style={{ flexWrap: 'wrap', gap: 4 }}>
              {listing.facilities.map(tag => (
                <span key={tag} className="fac-chip">{tag}</span>
              ))}
            </div>
          ) : (
            <div className="dr-placeholder">
              No facility data — will populate on next detail scrape.
            </div>
          )}
        </section>

        {/* History */}
        <section className="dr-section">
          <div className="dr-section-head">History</div>
          {evLoading && <span className="muted small">Loading…</span>}
          {events?.length === 0 && <span className="muted small">No events</span>}
          {events && events.length > 0 && (
            <div className="history">
              {events.map(ev => (
                <div key={ev.id} className="history-row">
                  <span className="mono small muted">{fmtDate(ev.created_at)}</span>
                  <span className="history-what">{ev.event_type.replace(/_/g, ' ')}</span>
                  <span className="muted small">
                    {ev.old_value && ev.new_value
                      ? `${JSON.stringify(ev.old_value)} → ${JSON.stringify(ev.new_value)}`
                      : ev.new_value ? JSON.stringify(ev.new_value) : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </aside>
  )
}
