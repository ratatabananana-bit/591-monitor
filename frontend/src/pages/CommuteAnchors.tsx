import { useState, useEffect, useRef } from 'react'
import type { CommuteAnchor } from '../types'
import { api } from '../api/client'
import { MRT_STATIONS, LINE_COLORS, LINE_NAMES } from '../data/mrtStations'

// ── helpers ──
type Mode = 'mrt' | 'custom'

interface FormState {
  name: string
  address: string
  weight: number
  enabled: boolean
  mode: Mode
  mrtQuery: string
}

const EMPTY_FORM: FormState = {
  name: '', address: '',
  weight: 1.0, enabled: true,
  mode: 'mrt', mrtQuery: '',
}

// ── MRT Station Picker ──
function MrtPicker({ query, onQuery, onSelect }: {
  query: string
  onQuery: (q: string) => void
  onSelect: (name: string, address: string) => void
}) {
  const filtered = query.length >= 1
    ? MRT_STATIONS.filter(s =>
        s.name.toLowerCase().includes(query.toLowerCase()) ||
        s.nameTW.includes(query)
      ).slice(0, 12)
    : []

  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <div style={{ position: 'relative' }}>
      <input
        ref={inputRef}
        className="filter-input"
        style={{ width: '100%' }}
        placeholder="Search MRT station… (e.g. 內湖, Neihu)"
        value={query}
        onChange={e => onQuery(e.target.value)}
        autoFocus
      />
      {filtered.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 30,
          background: 'var(--bg-2)', border: '1px solid var(--border-2)',
          borderRadius: 5, marginTop: 2, maxHeight: 260, overflowY: 'auto',
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          {filtered.map(s => (
            <div
              key={`${s.line}-${s.nameTW}`}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 10px', cursor: 'pointer', fontSize: 13,
              }}
              onMouseDown={e => {
                e.preventDefault()
                onSelect(s.nameTW, `台北捷運${s.nameTW}站`)
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--hover)')}
              onMouseLeave={e => (e.currentTarget.style.background = '')}
            >
              <span style={{
                width: 20, height: 20, borderRadius: '50%',
                background: LINE_COLORS[s.line] ?? '#888',
                display: 'grid', placeItems: 'center',
                fontSize: 9, fontWeight: 700, color: '#fff', flexShrink: 0,
              }}>{s.line}</span>
              <span>{s.nameTW}</span>
              <span style={{ color: 'var(--muted)', fontSize: 11 }}>{s.name}</span>
              <span style={{ color: 'var(--muted-2)', fontSize: 10, marginLeft: 'auto' }}>
                {LINE_NAMES[s.line]}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Anchor Form ──
function AnchorForm({
  form, setForm, onSave, onCancel, editId,
}: {
  form: FormState
  setForm: React.Dispatch<React.SetStateAction<FormState>>
  onSave: () => void
  onCancel: () => void
  editId: string | null
}) {
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleMrtSelect = (name: string, address: string) => {
    setForm(f => ({
      ...f,
      name: f.name || name,
      address,
      mrtQuery: name,
    }))
  }

  return (
    <div style={{
      background: 'var(--bg-2)', border: '1px solid var(--border)',
      borderRadius: 6, padding: 14, display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{ fontWeight: 600, fontSize: 13 }}>{editId ? 'Edit Anchor' : 'New Anchor'}</div>

      {/* Mode toggle */}
      <div className="seg" style={{ alignSelf: 'flex-start' }}>
        <button className={form.mode === 'mrt' ? 'on' : ''} onClick={() => set('mode', 'mrt')}>
          MRT Station
        </button>
        <button className={form.mode === 'custom' ? 'on' : ''} onClick={() => set('mode', 'custom')}>
          Custom Address
        </button>
      </div>

      {form.mode === 'mrt' && (
        <div>
          <div className="kv-label" style={{ marginBottom: 4 }}>Station</div>
          <MrtPicker
            query={form.mrtQuery}
            onQuery={q => set('mrtQuery', q)}
            onSelect={handleMrtSelect}
          />
        </div>
      )}

      {form.mode === 'custom' && (
        <div>
          <div className="kv-label" style={{ marginBottom: 4 }}>Address</div>
          <input
            className="filter-input"
            style={{ width: '100%' }}
            placeholder="台北市信義區..."
            value={form.address}
            onChange={e => set('address', e.target.value)}
            autoFocus
          />
        </div>
      )}

      {/* Name + Weight row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px', gap: 8 }}>
        <div>
          <div className="kv-label" style={{ marginBottom: 4 }}>Display name</div>
          <input
            className="filter-input"
            style={{ width: '100%' }}
            placeholder="Home, Office, School…"
            value={form.name}
            onChange={e => set('name', e.target.value)}
          />
        </div>
        <div>
          <div className="kv-label" style={{ marginBottom: 4 }}>Weight</div>
          <input
            type="number" step="0.1" min="0" max="1"
            className="filter-input"
            style={{ width: '100%' }}
            value={form.weight}
            onChange={e => set('weight', +e.target.value)}
          />
        </div>
      </div>

      {/* Enabled */}
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
        <span
          className={'wb-check' + (form.enabled ? ' on' : '')}
          onClick={() => set('enabled', !form.enabled)}
        />
        Enabled
      </label>

      <div style={{ display: 'flex', gap: 6 }}>
        <button className="wb-btn small btn-primary" onClick={onSave}>Save</button>
        <button className="wb-btn small ghost" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

// ── Main page ──
export default function CommuteAnchors() {
  const [anchors, setAnchors] = useState<CommuteAnchor[]>([])
  const [form, setForm] = useState<FormState | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recalcing, setRecalcing] = useState(false)

  const load = () => api.anchors.list().then(setAnchors).catch(e => setError(String(e)))
  useEffect(() => { load() }, [])

  const openNew = () => { setForm({ ...EMPTY_FORM }); setEditId(null) }
  const openEdit = (a: CommuteAnchor) => {
    setForm({
      name: a.name, address: a.address,
      weight: a.weight, enabled: a.enabled,
      mode: 'custom', mrtQuery: '',
    })
    setEditId(a.id)
  }

  const save = async () => {
    if (!form) return
    setError(null)
    try {
      const payload = {
        name: form.name,
        address: form.address,
        weight: form.weight,
        enabled: form.enabled,
      }
      if (editId) await api.anchors.update(editId, payload)
      else await api.anchors.create(payload)
      setForm(null); setEditId(null)
      load()
    } catch (e) { setError(String(e)) }
  }

  const del = async (id: string) => {
    if (!confirm('Delete this anchor?')) return
    setError(null)
    try { await api.anchors.delete(id); load() }
    catch (e) { setError(String(e)) }
  }

  const recalculate = async () => {
    setRecalcing(true)
    try { await api.scans.recalculate(); alert('Commute recalculation queued') }
    catch (e) { setError(String(e)) }
    finally { setRecalcing(false) }
  }

  return (
    <div style={{ maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Error */}
      {error && (
        <div style={{
          background: 'color-mix(in oklch, var(--danger) 14%, transparent)',
          border: '1px solid color-mix(in oklch, var(--danger) 35%, var(--border))',
          borderRadius: 5, padding: '8px 12px', fontSize: 12,
          color: 'oklch(0.92 0.10 25)', display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{ flex: 1 }}>{error}</span>
          <button className="icon-btn" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Commute Anchors</span>
        <span className="muted small" style={{ flex: 1 }}>
          Destinations used to calculate commute times
        </span>
        <button
          className="wb-btn small"
          onClick={recalculate}
          disabled={recalcing}
        >
          {recalcing ? 'Recalculating…' : '↻ Recalculate'}
        </button>
        <button className="wb-btn small btn-primary" onClick={openNew}>
          + New Anchor
        </button>
      </div>

      {/* Form */}
      {form && (
        <AnchorForm
          form={form}
          setForm={setForm as React.Dispatch<React.SetStateAction<FormState>>}
          onSave={save}
          onCancel={() => { setForm(null); setEditId(null) }}
          editId={editId}
        />
      )}

      {/* Anchor list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {anchors.map(a => (
          <div key={a.id} style={{
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 6, padding: '10px 14px',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
              background: a.enabled ? 'var(--ok)' : 'var(--muted-2)',
            }} />

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{a.name}</span>
                <span className="muted small mono">weight {a.weight.toFixed(1)}</span>
                {!a.enabled && (
                  <span className="badge" style={{ background: 'var(--bg-3)', color: 'var(--muted-2)' }}>
                    OFF
                  </span>
                )}
              </div>
              <div className="muted small truncate" style={{ marginTop: 2 }}>{a.address}</div>
            </div>

            <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
              <button className="wb-btn small" onClick={() => openEdit(a)}>Edit</button>
              <button className="wb-btn small danger" onClick={() => del(a.id)}>Delete</button>
            </div>
          </div>
        ))}

        {anchors.length === 0 && !form && (
          <div className="empty-pane" style={{ height: 120 }}>
            No anchors — add your workplace or school
          </div>
        )}
      </div>

      <div className="dr-placeholder">
        After adding anchors, click ↻ Recalculate or rescan to populate commute times.
      </div>
    </div>
  )
}
