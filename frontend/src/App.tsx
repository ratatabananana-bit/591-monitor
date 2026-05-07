import { Routes, Route, NavLink } from 'react-router-dom'
import Listings from './pages/Listings'
import ListingDetail from './pages/ListingDetail'
import SearchProfiles from './pages/SearchProfiles'
import CommuteAnchors from './pages/CommuteAnchors'
import ScanHistory from './pages/ScanHistory'

function Nav() {
  const cls = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-2 rounded text-sm font-medium ${isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700'}`
  return (
    <nav className="bg-gray-800 px-4 py-3 flex gap-2 items-center">
      <span className="text-white font-bold mr-4">🏠 591 Monitor</span>
      <NavLink to="/" className={cls} end>Listings</NavLink>
      <NavLink to="/profiles" className={cls}>Search Profiles</NavLink>
      <NavLink to="/anchors" className={cls}>Commute Anchors</NavLink>
      <NavLink to="/scans" className={cls}>Scan History</NavLink>
    </nav>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <Nav />
      <main className="p-4">
        <Routes>
          <Route path="/" element={<Listings />} />
          <Route path="/listings/:id" element={<ListingDetail />} />
          <Route path="/profiles" element={<SearchProfiles />} />
          <Route path="/anchors" element={<CommuteAnchors />} />
          <Route path="/scans" element={<ScanHistory />} />
        </Routes>
      </main>
    </div>
  )
}
