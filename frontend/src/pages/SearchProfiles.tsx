import { useState, useEffect } from 'react'
import type { SearchProfile } from '../types'
import { api } from '../api/client'

// 591 section codes per city stored as strings (scraper passes them as str(d))
const DISTRICTS_BY_CITY: Record<string, Array<{ code: string; name: string }>> = {
  taipei: [
    { code: '1', name: '中正區' }, { code: '2', name: '大同區' }, { code: '3', name: '中山區' },
    { code: '4', name: '松山區' }, { code: '5', name: '大安區' }, { code: '6', name: '萬華區' },
    { code: '7', name: '信義區' }, { code: '8', name: '士林區' }, { code: '9', name: '北投區' },
    { code: '10', name: '內湖區' }, { code: '11', name: '南港區' }, { code: '12', name: '文山區' },
  ],
  new_taipei: [
    { code: '26', name: '板橋區' }, { code: '43', name: '三重區' }, { code: '38', name: '中和區' },
    { code: '37', name: '永和區' }, { code: '44', name: '新莊區' }, { code: '34', name: '新店區' },
    { code: '41', name: '樹林區' }, { code: '42', name: '鶯歌區' }, { code: '40', name: '三峽區' },
    { code: '50', name: '淡水區' }, { code: '27', name: '汐止區' }, { code: '30', name: '瑞芳區' },
    { code: '39', name: '土城區' }, { code: '47', name: '蘆洲區' }, { code: '48', name: '五股區' },
    { code: '45', name: '泰山區' }, { code: '46', name: '林口區' }, { code: '49', name: '八里區' },
    { code: '28', name: '深坑區' }, { code: '51', name: '三芝區' }, { code: '29', name: '石碇區' },
    { code: '35', name: '坪林區' }, { code: '20', name: '萬里區' }, { code: '21', name: '金山區' },
    { code: '31', name: '平溪區' }, { code: '32', name: '雙溪區' }, { code: '33', name: '貢寮區' },
    { code: '36', name: '烏來區' }, { code: '52', name: '石門區' },
  ],
}

const CITY_OPTIONS = [
  { value: 'taipei', label: '台北市 Taipei' },
  { value: 'new_taipei', label: '新北市 New Taipei' },
  { value: 'taichung', label: '台中市 Taichung' },
  { value: 'tainan', label: '台南市 Tainan' },
  { value: 'kaohsiung', label: '高雄市 Kaohsiung' },
]

const ROOM_TYPE_OPTIONS = ['整層住家', '獨立套房', '分租套房', '雅房']

const EMPTY: Partial<SearchProfile> = {
  name: '', enabled: true, city: 'taipei', districts: [],
  price_min: null, price_max: null, min_ping: null, room_types: [],
  required_keywords: [], rejected_keywords: [], scan_interval_minutes: 30,
}

function DistrictSelector({
  city,
  selected,
  onChange,
}: {
  city: string
  selected: string[]
  onChange: (codes: string[]) => void
}) {
  const districts = DISTRICTS_BY_CITY[city]
  if (!districts) {
    return (
      <p className="text-xs text-gray-500 italic">
        District selector not available for this city yet — leave empty to search all.
      </p>
    )
  }

  function toggle(code: string) {
    if (selected.includes(code)) onChange(selected.filter(c => c !== code))
    else onChange([...selected, code])
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {districts.map(d => (
        <button
          key={d.code}
          type="button"
          onClick={() => toggle(d.code)}
          className={`px-2 py-0.5 text-xs rounded border transition-colors ${
            selected.includes(d.code)
              ? 'bg-blue-600 border-blue-500 text-white'
              : 'bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-400'
          }`}
        >
          {d.name}
        </button>
      ))}
      {selected.length > 0 && (
        <button
          type="button"
          onClick={() => onChange([])}
          className="px-2 py-0.5 text-xs rounded border border-gray-600 text-gray-500 hover:text-gray-300"
        >
          clear
        </button>
      )}
    </div>
  )
}

export default function SearchProfiles() {
  const [profiles, setProfiles] = useState<SearchProfile[]>([])
  const [editing, setEditing] = useState<Partial<SearchProfile> | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Raw text for keyword inputs — only parsed on save, so commas can be typed freely
  const [reqKwText, setReqKwText] = useState('')
  const [rejKwText, setRejKwText] = useState('')

  const load = () => api.profiles.list().then(setProfiles).catch(e => setError(String(e)))
  useEffect(() => { load() }, [])

  const openEdit = (p: Partial<SearchProfile>, id: string | null) => {
    setEditing({ ...p })
    setEditId(id)
    setReqKwText((p.required_keywords ?? []).join(', '))
    setRejKwText((p.rejected_keywords ?? []).join(', '))
  }

  const save = async () => {
    if (!editing) return
    setError(null)
    const payload = {
      ...editing,
      required_keywords: reqKwText.split(',').map(s => s.trim()).filter(Boolean),
      rejected_keywords: rejKwText.split(',').map(s => s.trim()).filter(Boolean),
    }
    try {
      if (editId) await api.profiles.update(editId, payload)
      else await api.profiles.create(payload)
      setEditing(null)
      setEditId(null)
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  const del = async (id: string) => {
    if (!confirm('Delete this profile?')) return
    setError(null)
    try {
      await api.profiles.delete(id)
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  const duplicate = async (p: SearchProfile) => {
    setError(null)
    try {
      await api.profiles.create({
        ...p,
        name: `${p.name} (copy)`,
        enabled: false,
      })
      load()
    } catch (e) {
      setError(String(e))
    }
  }

  function districtLabel(city: string, codes: string[]): string {
    if (!codes.length) return 'All districts'
    const map = DISTRICTS_BY_CITY[city]
    if (!map) return `${codes.length} district(s)`
    return codes.map(c => map.find(d => d.code === c)?.name ?? c).join(', ')
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {error && (
        <div className="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded text-sm">
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-white">✕</button>
        </div>
      )}
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">Search Profiles</h1>
        <button
          onClick={() => openEdit({ ...EMPTY }, null)}
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
              <label className="block text-xs text-gray-400 mb-1">City</label>
              <select
                value={editing.city ?? 'taipei'}
                onChange={e => setEditing(p => ({ ...p!, city: e.target.value, districts: [] }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              >
                {CITY_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
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
            <div>
              <label className="block text-xs text-gray-400 mb-1">Min Size (ping) <span className="text-gray-600">optional</span></label>
              <input
                type="number"
                step="0.5"
                value={editing.min_ping ?? ''}
                onChange={e => setEditing(p => ({ ...p!, min_ping: e.target.value ? +e.target.value : null }))}
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
                placeholder="e.g. 8"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">Room Types <span className="text-gray-600">(leave empty = all)</span></label>
              <div className="flex flex-wrap gap-1.5">
                {ROOM_TYPE_OPTIONS.map(rt => {
                  const sel = (editing.room_types ?? []).includes(rt)
                  return (
                    <button
                      key={rt}
                      type="button"
                      onClick={() => {
                        const cur = editing.room_types ?? []
                        setEditing(p => ({
                          ...p!,
                          room_types: sel ? cur.filter(r => r !== rt) : [...cur, rt],
                        }))
                      }}
                      className={`px-2 py-0.5 text-xs rounded border transition-colors ${
                        sel
                          ? 'bg-blue-600 border-blue-500 text-white'
                          : 'bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-400'
                      }`}
                    >
                      {rt}
                    </button>
                  )
                })}
                {(editing.room_types ?? []).length > 0 && (
                  <button
                    type="button"
                    onClick={() => setEditing(p => ({ ...p!, room_types: [] }))}
                    className="px-2 py-0.5 text-xs rounded border border-gray-600 text-gray-500 hover:text-gray-300"
                  >
                    clear
                  </button>
                )}
              </div>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">
                Districts <span className="text-gray-600">(leave empty = all)</span>
              </label>
              <DistrictSelector
                city={editing.city ?? 'taipei'}
                selected={(editing.districts ?? []) as string[]}
                onChange={codes => setEditing(p => ({ ...p!, districts: codes }))}
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">
                Required Keywords <span className="text-gray-600">comma-separated — keyword itself can contain commas if needed</span>
              </label>
              <input
                value={reqKwText}
                onChange={e => setReqKwText(e.target.value)}
                placeholder="e.g. 東森, 大樓管理"
                className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-1.5 text-sm"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-400 mb-1">
                Rejected Keywords <span className="text-gray-600">comma-separated</span>
              </label>
              <input
                value={rejKwText}
                onChange={e => setRejKwText(e.target.value)}
                placeholder="e.g. 限女, 一次性費用"
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
              onClick={() => { setEditing(null); setEditId(null); setReqKwText(''); setRejKwText('') }}
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
              <div className="text-sm text-gray-400 mt-1 space-y-0.5">
                <div>
                  {p.price_min ? `NT$${p.price_min.toLocaleString()}` : ''}
                  {p.price_min && p.price_max ? ' – ' : ''}
                  {p.price_max ? `NT$${p.price_max.toLocaleString()}` : ''}
                  {p.min_ping ? ` · ≥${p.min_ping}ping` : ''}
                  {(p.room_types?.length ?? 0) > 0 ? ` · ${p.room_types.join('/')}` : ''}
                  {' · '}{p.scan_interval_minutes}min
                  {p.last_scanned_at ? ` · Last: ${new Date(p.last_scanned_at).toLocaleString()}` : ''}
                </div>
                {(p.districts?.length ?? 0) > 0 && (
                  <div className="text-xs text-gray-500">{districtLabel(p.city, p.districts as string[])}</div>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => openEdit(p, p.id)}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
              >
                Edit
              </button>
              <button
                onClick={() => duplicate(p)}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm"
                title="Duplicate profile (created as disabled)"
              >
                Copy
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
