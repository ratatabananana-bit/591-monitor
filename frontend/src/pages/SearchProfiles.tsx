import { useState, useEffect } from 'react'
import type { SearchProfile } from '../types'
import { api } from '../api/client'

const EMPTY: Partial<SearchProfile> = {
  name: '', enabled: true, city: 'taipei', districts: [],
  price_min: null, price_max: null, room_types: [],
  required_keywords: [], rejected_keywords: [], scan_interval_minutes: 30,
}

export default function SearchProfiles() {
  const [profiles, setProfiles] = useState<SearchProfile[]>([])
  const [editing, setEditing] = useState<Partial<SearchProfile> | null>(null)
  const [editId, setEditId] = useState<string | null>(null)

  const load = () => api.profiles.list().then(setProfiles)
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!editing) return
    if (editId) await api.profiles.update(editId, editing)
    else await api.profiles.create(editing)
    setEditing(null)
    setEditId(null)
    load()
  }

  const del = async (id: string) => {
    if (!confirm('Delete this profile?')) return
    await api.profiles.delete(id)
    load()
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">Search Profiles</h1>
        <button
          onClick={() => { setEditing({ ...EMPTY }); setEditId(null) }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-sm"
        >
          + New Profile
        </button>
      </div>

      {editing && (
        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="font-medium">{editId ? 'Edit Profile' : 'New Profile'}</h2>
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
              <label className="block text-xs text-gray-400 mb-1">Scan Interval (min)</label>
              <input
                type="number"
                value={editing.scan_interval_minutes ?? 30}
                onChange={e => setEditing(p => ({ ...p!, scan_interval_minutes: +e.target.value }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Min Price (NT$)</label>
              <input
                type="number"
                value={editing.price_min ?? ''}
                onChange={e => setEditing(p => ({ ...p!, price_min: e.target.value ? +e.target.value : null }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Max Price (NT$)</label>
              <input
                type="number"
                value={editing.price_max ?? ''}
                onChange={e => setEditing(p => ({ ...p!, price_max: e.target.value ? +e.target.value : null }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Required Keywords (comma-separated)</label>
              <input
                value={(editing.required_keywords ?? []).join(', ')}
                onChange={e => setEditing(p => ({ ...p!, required_keywords: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Rejected Keywords (comma-separated)</label>
              <input
                value={(editing.rejected_keywords ?? []).join(', ')}
                onChange={e => setEditing(p => ({ ...p!, rejected_keywords: e.target.value.split(',').map(s => s.trim()).filter(Boolean) }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2 flex items-center gap-2">
              <input
                type="checkbox"
                checked={editing.enabled ?? true}
                onChange={e => setEditing(p => ({ ...p!, enabled: e.target.checked }))}
                id="enabled"
              />
              <label htmlFor="enabled" className="text-sm">Enabled</label>
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
        {profiles.map(p => (
          <div key={p.id} className="bg-gray-800 rounded-lg p-4 flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{p.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${p.enabled ? 'bg-green-700' : 'bg-gray-600'}`}>
                  {p.enabled ? 'Active' : 'Disabled'}
                </span>
              </div>
              <div className="text-sm text-gray-400 mt-1">
                {p.price_min ? `NT$${p.price_min.toLocaleString()}` : ''}
                {p.price_min && p.price_max ? ' – ' : ''}
                {p.price_max ? `NT$${p.price_max.toLocaleString()}` : ''}
                {' · '}{p.scan_interval_minutes}min interval
                {p.last_scanned_at ? ` · Last: ${new Date(p.last_scanned_at).toLocaleString()}` : ''}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => { setEditing({ ...p }); setEditId(p.id) }}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
              >
                Edit
              </button>
              <button onClick={() => del(p.id)} className="px-3 py-1 bg-red-700 hover:bg-red-600 rounded text-sm">
                Delete
              </button>
            </div>
          </div>
        ))}
        {profiles.length === 0 && (
          <div className="text-center py-12 text-gray-500">No profiles yet</div>
        )}
      </div>
    </div>
  )
}
