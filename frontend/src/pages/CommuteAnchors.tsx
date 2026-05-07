import { useState, useEffect } from 'react'
import type { CommuteAnchor } from '../types'
import { api } from '../api/client'

const EMPTY: Partial<CommuteAnchor> = { name: '', address: '', weight: 1.0, enabled: true }

export default function CommuteAnchors() {
  const [anchors, setAnchors] = useState<CommuteAnchor[]>([])
  const [editing, setEditing] = useState<Partial<CommuteAnchor> | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = () => api.anchors.list().then(setAnchors).catch(e => setError(String(e)))
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!editing) return
    setError(null)
    try {
      if (editId) await api.anchors.update(editId, editing)
      else await api.anchors.create(editing)
      setEditing(null)
      setEditId(null)
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  const del = async (id: string) => {
    if (!confirm('Delete this anchor?')) return
    setError(null)
    try {
      await api.anchors.delete(id)
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  const recalculate = async () => {
    try {
      await api.scans.recalculate()
      alert('Commute recalculation queued')
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {error && (
        <div className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded text-sm">
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-white">✕</button>
        </div>
      )}
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">Commute Anchors</h1>
        <div className="flex gap-2">
          <button onClick={recalculate} className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded text-sm">
            ↻ Recalculate
          </button>
          <button
            onClick={() => { setEditing({ ...EMPTY }); setEditId(null) }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm"
          >
            + New Anchor
          </button>
        </div>
      </div>

      {editing && (
        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="font-medium">{editId ? 'Edit Anchor' : 'New Anchor'}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Name</label>
              <input
                value={editing.name ?? ''}
                onChange={e => setEditing(p => ({ ...p!, name: e.target.value }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Weight (0–1)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={editing.weight ?? 1}
                onChange={e => setEditing(p => ({ ...p!, weight: +e.target.value }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Address</label>
              <input
                value={editing.address ?? ''}
                onChange={e => setEditing(p => ({ ...p!, address: e.target.value }))}
                placeholder="台北市信義區..."
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={editing.enabled ?? true}
                onChange={e => setEditing(p => ({ ...p!, enabled: e.target.checked }))}
                id="anchor-enabled"
              />
              <label htmlFor="anchor-enabled" className="text-sm">Enabled</label>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded text-sm">Save</button>
            <button
              onClick={() => { setEditing(null); setEditId(null) }}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-500 rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {anchors.map(a => (
          <div key={a.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{a.name}</span>
                <span className="text-xs text-gray-400">weight: {a.weight}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${a.enabled ? 'bg-green-700' : 'bg-gray-600'}`}>
                  {a.enabled ? 'Active' : 'Off'}
                </span>
              </div>
              <p className="text-sm text-gray-400 mt-1">{a.address}</p>
              {a.lat && a.lng && (
                <p className="text-xs text-gray-500">{a.lat.toFixed(4)}, {a.lng.toFixed(4)}</p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setEditing({ ...a }); setEditId(a.id) }}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
              >
                Edit
              </button>
              <button onClick={() => del(a.id)} className="px-3 py-1 bg-red-700 hover:bg-red-600 rounded text-sm">
                Delete
              </button>
            </div>
          </div>
        ))}
        {anchors.length === 0 && (
          <div className="text-center py-12 text-gray-500">No anchors yet</div>
        )}
      </div>
    </div>
  )
}
