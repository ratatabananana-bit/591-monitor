import { useState, useEffect, useRef } from 'react'
import type { ScanRun } from '../types'
import { api, type LogEntry } from '../api/client'

function duration(r: ScanRun): string {
  if (!r.finished_at) return ''
  const ms = new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function jobLabel(r: ScanRun): string {
  if (r.job_type === 'commute_recalc') return 'Commute Recalculate'
  if (r.job_type === 'backfill_dates') return 'Backfill Posted Dates'
  if (r.job_type === 'backfill_page_text') return 'Backfill Page Text'
  if (r.job_type === 'retag_all') return 'Retag All Listings'
  if (r.job_type === 'rescore') return 'Rescore All Listings'
  if (r.job_type === 'telegram_alerts') return 'Telegram Alerts'
  return r.profile_name ?? 'Scan'
}

function jobIcon(r: ScanRun): string {
  if (r.job_type === 'commute_recalc') return '⇄'
  if (r.job_type === 'backfill_dates') return '📅'
  if (r.job_type === 'backfill_page_text') return '📄'
  if (r.job_type === 'retag_all') return '🏷'
  if (r.job_type === 'rescore') return '★'
  if (r.job_type === 'telegram_alerts') return '🔔'
  return '⟳'
}

function StatusDot({ status }: { status: ScanRun['status'] }) {
  const color = status === 'running' || status === 'cancelling'
    ? 'var(--accent)'
    : status === 'success'
      ? 'var(--ok)'
      : status === 'partial'
        ? 'var(--warn)'
        : status === 'cancelled'
          ? 'var(--muted)'
          : 'var(--danger)'
  return (
    <span style={{
      width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
      background: color,
      boxShadow: status === 'running' ? `0 0 6px ${color}` : undefined,
    }} />
  )
}

// ── Log panel ──
function LogPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [paused, setPaused] = useState(false)
  const sinceRef = useRef(0)
  const pausedRef = useRef(false)
  pausedRef.current = paused

  useEffect(() => {
    const poll = async () => {
      try {
        const entries = await api.logs.fetch(sinceRef.current)
        if (entries.length > 0) {
          sinceRef.current = entries[entries.length - 1].id
          if (!pausedRef.current) {
            setLogs(prev => {
              const next = [...prev, ...entries].slice(-300)
              return next
            })
          }
        }
      } catch { /* ignore */ }
    }
    poll()
    const iv = setInterval(poll, 1500)
    return () => clearInterval(iv)
  }, [])

  const containerRef = useRef<HTMLDivElement>(null)
  const atBottomRef = useRef(true)

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60
  }

  useEffect(() => {
    if (!paused && atBottomRef.current) {
      const el = containerRef.current
      if (el) el.scrollTop = el.scrollHeight
    }
  }, [logs, paused])

  const levelColor = (level: string) => {
    if (level === 'ERROR' || level === 'CRITICAL') return 'var(--danger)'
    if (level === 'WARNING') return '#f59e0b'
    if (level === 'INFO') return 'var(--accent)'
    return 'var(--muted)'
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--bg)', border: '1px solid var(--border)',
      borderRadius: 6, overflow: 'hidden', height: '100%', minHeight: 0,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 10px', borderBottom: '1px solid var(--border)',
        background: 'var(--bg-2)', flexShrink: 0,
      }}>
        <span style={{ fontWeight: 600, fontSize: 12 }}>Server Log</span>
        <span style={{ flex: 1 }} />
        <button
          className="wb-btn small"
          style={{ fontSize: 10, padding: '1px 7px' }}
          onClick={() => setPaused(p => !p)}
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
        <button
          className="wb-btn small"
          style={{ fontSize: 10, padding: '1px 7px' }}
          onClick={() => { setLogs([]); setPaused(true) }}
        >
          Clear
        </button>
      </div>
      {/* Log entries */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        style={{
          flex: 1, overflowY: 'auto', padding: '6px 4px',
          fontFamily: 'monospace', fontSize: 11, lineHeight: 1.5,
        }}
      >
        {logs.length === 0 && (
          <div style={{ color: 'var(--muted-2)', padding: '8px 6px', fontSize: 11 }}>
            Waiting for log output…
          </div>
        )}
        {logs.map(e => {
          const ts = new Date(e.t * 1000).toLocaleTimeString('zh-TW', { hour12: false })
          return (
            <div key={e.id} style={{
              display: 'flex', gap: 6, padding: '1px 6px',
              borderRadius: 2,
              background: (e.level === 'ERROR' || e.level === 'CRITICAL')
                ? 'color-mix(in oklch, var(--danger) 8%, transparent)' : undefined,
            }}>
              <span style={{ color: 'var(--muted-2)', flexShrink: 0 }}>{ts}</span>
              <span style={{
                color: levelColor(e.level), flexShrink: 0,
                width: 28, fontSize: 9, fontWeight: 700,
                display: 'flex', alignItems: 'center',
              }}>{e.level.slice(0, 4)}</span>
              <span style={{ color: 'var(--muted)', flexShrink: 0, fontSize: 10 }}>
                [{e.logger}]
              </span>
              <span style={{
                color: e.level === 'ERROR' ? 'var(--danger)' : e.level === 'WARNING' ? '#f59e0b' : 'var(--fg)',
                wordBreak: 'break-all',
              }}>{e.msg}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Activity() {
  const [runs, setRuns] = useState<ScanRun[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = () => api.scans.list().then(data => {
    setRuns(data)
    const hasRunning = data.some(r => r.status === 'running')
    if (hasRunning && !pollRef.current) {
      pollRef.current = setInterval(() => api.scans.list().then(setRuns), 2500)
    } else if (!hasRunning && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  })

  useEffect(() => {
    load()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const hasRunning = runs.some(r => r.status === 'running')

  return (
    <div style={{ display: 'flex', gap: 14, height: 'calc(100vh - 120px)', minHeight: 400 }}>
    {/* Left: jobs */}
    <div style={{ width: 420, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header row 1: title + controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Activity</span>
        {hasRunning && (
          <span style={{
            fontSize: 11, color: 'var(--accent)', background: 'color-mix(in oklch, var(--accent) 12%, transparent)',
            border: '1px solid color-mix(in oklch, var(--accent) 30%, transparent)',
            borderRadius: 4, padding: '1px 7px',
          }}>
            ● Running
          </span>
        )}
        <span style={{ flex: 1 }} />
        <button className="wb-btn small" onClick={() => api.scans.clearDone().then(load)}>
          Clear Done
        </button>
        <button className="wb-btn small" onClick={load}>↻ Refresh</button>
      </div>

      {/* Header row 2: maintenance actions */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button
          className="wb-btn small"
          onClick={() => api.scans.rescore().then(load)}
          title="Recalculate scores for all listings using the current formula"
        >
          ★ Rescore
        </button>
        <button
          className="wb-btn small"
          onClick={() => api.scans.backfillDates().then(load)}
          title="Fetch posted date for listings that are missing it"
        >
          📅 Backfill Dates
        </button>
        <button
          className="wb-btn small"
          onClick={() => api.scans.backfillPageText().then(load)}
          title="Scrape full description for all listings — needed for tag keyword matching"
        >
          📄 Backfill Text
        </button>
        <button
          className="wb-btn small"
          style={{ color: 'var(--warn, #f59e0b)' }}
          onClick={() => {
            if (!confirm('Wipe all Telegram alerted records? All matching listings will re-alert on next scan.')) return
            api.scans.clearAlerted().then(r => { alert(`Cleared ${r.deleted} alerted record(s).`); load() })
          }}
          title="Reset Telegram alert history — use for testing"
        >
          🔔 Reset Alerts
        </button>
      </div>

      {/* Job list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {runs.map(r => {
          const expanded = expandedId === r.id
          return (
            <div key={r.id} style={{
              background: 'var(--bg-2)',
              border: `1px solid ${r.status === 'failed' ? 'color-mix(in oklch, var(--danger) 40%, var(--border))' : r.status === 'partial' ? 'color-mix(in oklch, var(--warn) 40%, var(--border))' : 'var(--border)'}`,
              borderRadius: 6, overflow: 'hidden',
            }}>
              {/* Row */}
              <div
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 12px', cursor: 'pointer',
                }}
                onClick={() => setExpandedId(expanded ? null : r.id)}
              >
                <StatusDot status={r.status} />

                {/* Icon */}
                <span style={{
                  fontSize: 14, color: 'var(--muted)', width: 16, textAlign: 'center',
                  animation: r.status === 'running' ? 'spin 1.2s linear infinite' : undefined,
                }}>
                  {jobIcon(r)}
                </span>

                {/* Label + stats */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{jobLabel(r)}</span>

                    {r.status === 'running' && (
                      <span style={{ fontSize: 11, color: 'var(--accent)' }}>running…</span>
                    )}

                    {r.status === 'success' && !r.job_type && (
                      <>
                        {r.new_listings > 0 && (
                          <span style={{ fontSize: 11, color: 'var(--ok)', background: 'color-mix(in oklch, var(--ok) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--ok) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                            +{r.new_listings} new
                          </span>
                        )}
                        {r.updated_listings > 0 && (
                          <span style={{ fontSize: 11, color: 'var(--accent)', background: 'color-mix(in oklch, var(--accent) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--accent) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                            {r.updated_listings} updated
                          </span>
                        )}
                        {r.gone_listings > 0 && (
                          <span style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--bg-3)', border: '1px solid var(--border)', borderRadius: 3, padding: '0 5px' }}>
                            {r.gone_listings} gone
                          </span>
                        )}
                        {r.new_listings === 0 && r.updated_listings === 0 && r.gone_listings === 0 && (
                          <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>{r.listings_found} found, no changes</span>
                        )}
                      </>
                    )}

                    {r.status === 'success' && r.job_type === 'commute_recalc' && (
                      <>
                        {r.new_listings > 0 && (
                          <span style={{ fontSize: 11, color: 'var(--ok)', background: 'color-mix(in oklch, var(--ok) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--ok) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                            {r.new_listings} calculated
                          </span>
                        )}
                        {r.updated_listings > 0 && (
                          <span style={{ fontSize: 11, color: 'var(--danger)', background: 'color-mix(in oklch, var(--danger) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--danger) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                            {r.updated_listings} failed
                          </span>
                        )}
                        {r.new_listings === 0 && r.updated_listings === 0 && (
                          <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>{r.listings_found} listings, no anchors</span>
                        )}
                      </>
                    )}

                    {r.status === 'success' && r.job_type === 'rescore' && (
                      <span style={{ fontSize: 11, color: 'var(--ok)', background: 'color-mix(in oklch, var(--ok) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--ok) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                        {r.new_listings} rescored
                      </span>
                    )}

                    {r.status === 'success' && r.job_type === 'retag_all' && (
                      <>
                        {r.new_listings > 0 && (
                          <span style={{ fontSize: 11, color: 'var(--ok)', background: 'color-mix(in oklch, var(--ok) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--ok) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                            {r.new_listings} updated
                          </span>
                        )}
                        {r.new_listings === 0 && (
                          <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>{r.listings_found} checked, no changes</span>
                        )}
                      </>
                    )}

                    {r.job_type === 'telegram_alerts' && r.status === 'success' && (
                      r.new_listings > 0
                        ? <span style={{ fontSize: 11, color: 'var(--ok)', background: 'color-mix(in oklch, var(--ok) 12%, transparent)', border: '1px solid color-mix(in oklch, var(--ok) 25%, transparent)', borderRadius: 3, padding: '0 5px' }}>
                            {r.new_listings} sent
                          </span>
                        : <span style={{ fontSize: 11, color: 'var(--muted-2)' }}>nothing to send</span>
                    )}

                    {r.status === 'partial' && (
                      <span style={{ fontSize: 11, color: 'var(--warn)' }}>
                        {r.new_listings} filled · {r.updated_listings} missing date
                      </span>
                    )}

                    {r.status === 'failed' && r.errors && (
                      <span style={{ fontSize: 11, color: 'var(--danger)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {String(Object.values(r.errors)[0] ?? 'error')}
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 2 }}>
                    {relTime(r.started_at)}
                    {duration(r) ? ` · ${duration(r)}` : ''}
                    {r.status === 'success' && !r.job_type ? ` · ${r.listings_found} found` : ''}
                  </div>
                </div>

                {/* Cancel button for running jobs */}
                {(r.status === 'running' || r.status === 'cancelling') && (
                  <button
                    className="wb-btn small danger"
                    style={{ fontSize: 10, padding: '1px 7px', flexShrink: 0 }}
                    disabled={r.status === 'cancelling'}
                    onClick={e => { e.stopPropagation(); api.scans.cancel(r.id).then(load) }}
                  >
                    {r.status === 'cancelling' ? 'Stopping…' : '■ Stop'}
                  </button>
                )}

                {/* Status badge */}
                <span style={{
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                  color: r.status === 'running' || r.status === 'cancelling' ? 'var(--accent)'
                    : r.status === 'success' ? 'var(--ok)'
                    : r.status === 'partial' ? 'var(--warn)'
                    : r.status === 'cancelled' ? 'var(--muted)'
                    : 'var(--danger)',
                  textTransform: 'uppercase', flexShrink: 0,
                }}>
                  {r.status}
                </span>

                <span style={{ fontSize: 10, color: 'var(--muted-2)', flexShrink: 0 }}>{expanded ? '▲' : '▼'}</span>
              </div>

              {/* Expanded detail */}
              {expanded && (
                <div style={{
                  borderTop: '1px solid var(--border)', padding: '10px 12px',
                  background: 'var(--bg)', display: 'flex', flexDirection: 'column', gap: 6,
                }}>
                  {r.status === 'failed' && r.errors && (
                    <pre style={{
                      fontSize: 11, color: 'var(--danger)', fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap', wordBreak: 'break-all', margin: 0,
                    }}>
                      {JSON.stringify(r.errors, null, 2)}
                    </pre>
                  )}

                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px 16px',
                    fontSize: 11, color: 'var(--muted)',
                  }}>
                    <span>Started: <span style={{ color: 'var(--fg)' }}>{new Date(r.started_at).toLocaleString()}</span></span>
                    {r.finished_at && <span>Finished: <span style={{ color: 'var(--fg)' }}>{new Date(r.finished_at).toLocaleString()}</span></span>}
                    {duration(r) && <span>Duration: <span style={{ color: 'var(--fg)' }}>{duration(r)}</span></span>}
                    {!r.job_type && <>
                      <span>Found: <span style={{ color: 'var(--fg)' }}>{r.listings_found}</span></span>
                      <span>New: <span style={{ color: 'var(--ok)' }}>{r.new_listings}</span></span>
                      <span>Updated: <span style={{ color: 'var(--accent)' }}>{r.updated_listings}</span></span>
                      <span>Gone: <span style={{ color: 'var(--muted)' }}>{r.gone_listings}</span></span>
                    </>}
                    {(r.job_type === 'rescore' || r.job_type === 'retag_all' || r.job_type === 'backfill_dates' || r.job_type === 'backfill_page_text') && <>
                      <span>Total: <span style={{ color: 'var(--fg)' }}>{r.listings_found}</span></span>
                      <span>Processed: <span style={{ color: 'var(--ok)' }}>{r.new_listings}</span></span>
                      {r.updated_listings > 0 && <span>Failed: <span style={{ color: 'var(--danger)' }}>{r.updated_listings}</span></span>}
                    </>}
                    {r.job_type === 'commute_recalc' && <>
                      <span>Total: <span style={{ color: 'var(--fg)' }}>{r.listings_found}</span></span>
                      <span>Calculated: <span style={{ color: 'var(--ok)' }}>{r.new_listings}</span></span>
                      <span>Failed: <span style={{ color: r.updated_listings > 0 ? 'var(--danger)' : 'var(--muted)' }}>{r.updated_listings}</span></span>
                    </>}
                    <span>Type: <span style={{ color: 'var(--fg)' }}>{r.job_type ?? 'scan'}</span></span>
                  </div>
                </div>
              )}
            </div>
          )
        })}

        {runs.length === 0 && (
          <div className="empty-pane" style={{ height: 120 }}>
            No activity yet — run a scan or recalculate commutes
          </div>
        )}
      </div>
    </div>{/* end left col */}

    {/* Right: live log */}
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <LogPanel />
    </div>
  </div>
  )
}
