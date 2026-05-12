import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { useState, useCallback, useRef, useEffect, createContext, useContext } from 'react'
import type { Listing, ScanRun } from './types'
import { api } from './api/client'

// ── pages ──
import Listings from './pages/Listings'
import SearchProfiles from './pages/SearchProfiles'
import CommuteAnchors from './pages/CommuteAnchors'
import TagRules from './pages/TagRules'
import ScanHistory from './pages/ScanHistory'
import { DetailDrawer } from './components/DetailDrawer'

// ─────────────────────────────────── App context ──
interface AppCtx {
  activeView: string
  setActiveView: (v: string) => void
  openListing: Listing | null
  setOpenListing: (l: Listing | null) => void
  refreshToken: number
  triggerRefresh: () => void
}
export const AppContext = createContext<AppCtx>({
  activeView: 'v_active',
  setActiveView: () => {},
  openListing: null,
  setOpenListing: () => {},
  refreshToken: 0,
  triggerRefresh: () => {},
})
export const useApp = () => useContext(AppContext)

// ─────────────────────────────────── Icons ──
function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    inbox:    'M22 12h-6l-2 3h-4l-2-3H2M22 12V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v6M22 12v6a2 2 0 1 1-2 2H4a2 2 0 0 1-2-2v-6',
    search:   'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35',
    bookmark: 'M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z',
    archive:  'M21 8H3v13h18V8zM23 3H1v5h22V3zM10 12h4',
    tag:      'M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01',
    route:    'M9 19a4 4 0 0 1-4-4V9a4 4 0 0 1 4-4h6M15 5l4 4-4 4',
    settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
    refresh:  'M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15',
    history:  'M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  }
  return (
    <svg className="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={paths[name] ?? paths.search} />
    </svg>
  )
}

// ─────────────────────────────────── Views ──
const VIEWS = [
  { id: 'v_new',      label: 'New',        icon: 'inbox',    statuses: ['NEW'] },
  { id: 'v_active',   label: 'Active',     icon: 'search',   statuses: ['NEW', 'ACTIVE', 'REAPPEARED', 'MISSING_ON_SEARCH'] },
  { id: 'v_saved',    label: 'Saved',      icon: 'bookmark', statuses: ['SAVED', 'CHECKING'] },
  { id: 'v_rejected', label: 'Rejected',   icon: 'archive',  statuses: ['REJECTED'] },
  { id: 'v_delisted', label: 'Delisted',   icon: 'archive',  statuses: ['MISSING_ON_SEARCH', 'UNAVAILABLE', 'ARCHIVED'] },
]

// ─────────────────────────────────── Topbar ──
function TopBar({ scanning, onScan, recentRun }: {
  scanning: boolean
  onScan: () => void
  recentRun: ScanRun | null
}) {
  const pillClass = scanning ? 'scan-pill scanning' : recentRun?.status === 'failed' ? 'scan-pill failed' : 'scan-pill'
  const pillText = scanning
    ? 'Scanning…'
    : recentRun?.status === 'success'
      ? `Done · +${recentRun.new_listings} new`
      : recentRun?.status === 'failed'
        ? 'Scan failed'
        : 'Ready'

  return (
    <div className="topbar">
      <div className="brand">
        <div className="brand-mark">5</div>
        <span>591 Workbench</span>
      </div>
      <div className={pillClass}>
        <span className="dot" />
        <span>{pillText}</span>
      </div>
      <div style={{ flex: 1 }} />
      <button className="icon-btn" title="Settings" onClick={() => {}}>
        <Icon name="settings" />
      </button>
      <button className="wb-btn btn-primary" onClick={onScan} disabled={scanning}>
        <Icon name="refresh" />
        {scanning ? 'Scanning…' : 'Scan now'}
      </button>
    </div>
  )
}

// ─────────────────────────────────── Sidebar ──
function Sidebar({ activeView, onView }: { activeView: string; onView: (id: string) => void }) {
  const navigate = useNavigate()
  const location = useLocation()
  const onListings = location.pathname === '/'

  return (
    <aside className="sidebar">
      <div className="side-section-head"><span>Views</span></div>
      {VIEWS.map(v => (
        <div
          key={v.id}
          className={'side-item' + (onListings && activeView === v.id ? ' active' : '')}
          onClick={() => { onView(v.id); if (!onListings) navigate('/') }}
        >
          <Icon name={v.icon} />
          <span className="label">{v.label}</span>
        </div>
      ))}

      <div className="side-section-head" style={{ marginTop: 12 }}><span>Config</span></div>
      <div
        className={'side-item' + (location.pathname === '/profiles' ? ' active' : '')}
        onClick={() => navigate('/profiles')}
      >
        <Icon name="search" />
        <span className="label">Search Profiles</span>
      </div>
      <div
        className={'side-item' + (location.pathname === '/anchors' ? ' active' : '')}
        onClick={() => navigate('/anchors')}
      >
        <Icon name="route" />
        <span className="label">Commute Anchors</span>
      </div>
      <div
        className={'side-item' + (location.pathname === '/tags' ? ' active' : '')}
        onClick={() => navigate('/tags')}
      >
        <Icon name="tag" />
        <span className="label">Tag Rules</span>
      </div>

      <div style={{ flex: 1 }} />
      <div
        className={'side-item' + (location.pathname === '/scans' ? ' active' : '')}
        onClick={() => navigate('/scans')}
      >
        <Icon name="history" />
        <span className="label" style={{ fontSize: 12, color: 'var(--muted)' }}>Activity</span>
      </div>
    </aside>
  )
}

// ─────────────────────────────────── App ──
export default function App() {
  const [activeView, setActiveView] = useState('v_active')
  const [openListing, setOpenListing] = useState<Listing | null>(null)
  const [scanning, setScanning] = useState(false)
  const [recentRun, setRecentRun] = useState<ScanRun | null>(null)
  const [refreshToken, setRefreshToken] = useState(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const triggerRefresh = useCallback(() => setRefreshToken(t => t + 1), [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpenListing(null)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const loadRuns = useCallback(async () => {
    const runs = await api.scans.list()
    if (runs[0]) setRecentRun(runs[0])
    if (!runs.some(r => r.status === 'running')) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
      setScanning(false)
      triggerRefresh()
    }
  }, [triggerRefresh])

  const handleScan = useCallback(async () => {
    setScanning(true)
    try {
      const res = await api.scans.trigger()
      if (res.triggered === 0) {
        alert('No enabled search profiles. Create one in Search Profiles first.')
        setScanning(false)
        return
      }
      await loadRuns()
      pollRef.current = setInterval(loadRuns, 3000)
    } catch (e) {
      alert(`Scan failed: ${e}`)
      setScanning(false)
    }
  }, [loadRuns])

  const location = useLocation()
  const drawerOn = openListing !== null && location.pathname === '/'
  const shellCls = 'shell' + (drawerOn ? ' with-drawer' : '')

  return (
    <AppContext.Provider value={{ activeView, setActiveView, openListing, setOpenListing, refreshToken, triggerRefresh }}>
      <div className={shellCls}>
        <TopBar scanning={scanning} onScan={handleScan} recentRun={recentRun} />
        <Sidebar activeView={activeView} onView={id => { setActiveView(id); setOpenListing(null) }} />
        <main className="main">
          <Routes>
            <Route path="/" element={<Listings />} />
            <Route path="/profiles" element={<div className="config-main"><SearchProfiles /></div>} />
            <Route path="/anchors" element={<div className="config-main"><CommuteAnchors /></div>} />
            <Route path="/tags" element={<div className="config-main"><TagRules /></div>} />
            <Route path="/scans" element={<div className="config-main"><ScanHistory /></div>} />
          </Routes>
        </main>
        {drawerOn && (
          <DetailDrawer
            listing={openListing}
            onClose={() => setOpenListing(null)}
            onRefresh={triggerRefresh}
          />
        )}
      </div>
    </AppContext.Provider>
  )
}
