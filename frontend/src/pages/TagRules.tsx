import { useState, useEffect } from 'react'
import type { TagRule } from '../types'
import { api } from '../api/client'
import { useApp } from '../App'

// ── Keyword chip input ──
function KeywordInput({
  label, values, onChange, placeholder,
}: {
  label: string
  values: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const parts = draft.split(',').map(s => s.trim()).filter(Boolean)
    if (!parts.length) return
    onChange([...values, ...parts.filter(p => !values.includes(p))])
    setDraft('')
  }

  return (
    <div>
      <div className="kv-label" style={{ marginBottom: 4 }}>{label}</div>
      {values.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
          {values.map(kw => (
            <span
              key={kw}
              className="fac-chip"
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
              onClick={() => onChange(values.filter(v => v !== kw))}
            >
              {kw} <span style={{ opacity: 0.5, fontSize: 10 }}>✕</span>
            </span>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 6 }}>
        <input
          className="filter-input"
          style={{ flex: 1 }}
          placeholder={placeholder ?? 'Keyword… (comma-separate for multiple)'}
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
        />
        <button className="wb-btn small" onClick={add}>Add</button>
      </div>
    </div>
  )
}

// ── Rule form ──
interface FormState {
  name: string
  keywords: string[]
  reject_keywords: string[]
  enabled: boolean
}

const EMPTY_FORM: FormState = { name: '', keywords: [], reject_keywords: [], enabled: true }

function RuleForm({
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

  return (
    <div style={{
      background: 'var(--bg-2)', border: '1px solid var(--border)',
      borderRadius: 6, padding: 14, display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <div style={{ fontWeight: 600, fontSize: 13 }}>{editId ? 'Edit Tag Rule' : 'New Tag Rule'}</div>

      <div>
        <div className="kv-label" style={{ marginBottom: 4 }}>Tag name</div>
        <input
          className="filter-input"
          style={{ width: '100%' }}
          placeholder="e.g. pet-ok, near-mrt, parking"
          value={form.name}
          onChange={e => set('name', e.target.value.toLowerCase().replace(/\s+/g, '-'))}
          autoFocus
        />
        <div className="muted small" style={{ marginTop: 4 }}>
          Listings matching keywords get <span style={{ color: 'var(--ok)' }}>+{form.name || 'tag'}</span>.
          Reject keyword matches get <span style={{ color: 'var(--danger)' }}>−{form.name || 'tag'}</span>.
        </div>
      </div>

      <KeywordInput
        label="Keywords → +tag applied"
        values={form.keywords}
        onChange={v => set('keywords', v)}
        placeholder="e.g. 可養寵, 歡迎寵物"
      />

      <KeywordInput
        label="Reject keywords → −tag (filter unless rescued)"
        values={form.reject_keywords}
        onChange={v => set('reject_keywords', v)}
        placeholder="e.g. 不可養寵, 禁止養寵"
      />

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
export default function TagRules() {
  useApp() // keep context wired for future use
  const [rules, setRules] = useState<TagRule[]>([])
  const [form, setForm] = useState<FormState | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retagging, setRetagging] = useState(false)
  const [retagDone, setRetagDone] = useState(false)

  const load = () => api.tagRules.list().then(setRules).catch(e => setError(String(e)))
  useEffect(() => { load() }, [])

  const openNew = () => { setForm({ ...EMPTY_FORM }); setEditId(null) }
  const openEdit = (r: TagRule) => {
    setForm({ name: r.name, keywords: r.keywords, reject_keywords: r.reject_keywords, enabled: r.enabled })
    setEditId(r.id)
  }

  const save = async () => {
    if (!form || !form.name.trim()) { setError('Tag name required'); return }
    if (form.keywords.length === 0 && form.reject_keywords.length === 0) {
      setError('Add at least one keyword or reject keyword')
      return
    }
    setError(null)
    try {
      const payload = { name: form.name.trim(), keywords: form.keywords, reject_keywords: form.reject_keywords, enabled: form.enabled }
      if (editId) await api.tagRules.update(editId, payload)
      else await api.tagRules.create(payload)
      setForm(null); setEditId(null)
      load()
    } catch (e) { setError(String(e)) }
  }

  const del = async (id: string) => {
    if (!confirm('Delete this tag rule?')) return
    try { await api.tagRules.delete(id); load() }
    catch (e) { setError(String(e)) }
  }

  const retagAll = async () => {
    setRetagging(true)
    setRetagDone(false)
    try {
      await api.tagRules.retagAll()
      setRetagDone(true)
      setTimeout(() => setRetagDone(false), 3000)
    } catch (e) { setError(String(e)) }
    finally { setRetagging(false) }
  }

  return (
    <div style={{ maxWidth: 600, display: 'flex', flexDirection: 'column', gap: 14 }}>
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

      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Tag Rules</span>
        <span className="muted small" style={{ flex: 1 }}>
          Keyword rules that apply ±tags to listings
        </span>
        <button className="wb-btn small" onClick={retagAll} disabled={retagging}>
          {retagging ? 'Retagging…' : retagDone ? '✓ Done' : '↻ Retag all'}
        </button>
        <button className="wb-btn small btn-primary" onClick={openNew}>+ New Rule</button>
      </div>

      {form && (
        <RuleForm
          form={form}
          setForm={setForm as React.Dispatch<React.SetStateAction<FormState>>}
          onSave={save}
          onCancel={() => { setForm(null); setEditId(null) }}
          editId={editId}
        />
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {rules.map(r => (
          <div key={r.id} style={{
            background: 'var(--bg-2)', border: '1px solid var(--border)',
            borderRadius: 6, padding: '10px 14px',
            display: 'flex', alignItems: 'flex-start', gap: 12,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 5,
              background: r.enabled ? 'var(--ok)' : 'var(--muted-2)',
            }} />

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{r.name}</span>
                {!r.enabled && (
                  <span className="badge" style={{ background: 'var(--bg-3)', color: 'var(--muted-2)' }}>OFF</span>
                )}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {r.keywords.map(kw => (
                  <span key={`k-${kw}`} className="profile-pill" style={{ fontSize: 11 }}>+{kw}</span>
                ))}
                {r.reject_keywords.map(kw => (
                  <span key={`r-${kw}`} className="profile-pill-filtered" style={{ fontSize: 11 }}>−{kw}</span>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
              <button className="wb-btn small" onClick={() => openEdit(r)}>Edit</button>
              <button className="wb-btn small danger" onClick={() => del(r.id)}>Delete</button>
            </div>
          </div>
        ))}

        {rules.length === 0 && !form && (
          <div className="empty-pane" style={{ height: 120 }}>
            No tag rules — create one to start tagging listings by keyword
          </div>
        )}
      </div>

      <div className="dr-placeholder">
        Tags appear as pills on listings. After adding rules, click ↻ Retag all to apply to existing listings.
      </div>
    </div>
  )
}
