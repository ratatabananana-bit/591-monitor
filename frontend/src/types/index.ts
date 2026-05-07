export type ListingStatus =
  | 'NEW' | 'ACTIVE' | 'WATCHED' | 'SAVED' | 'REJECTED'
  | 'CONTACTED' | 'VISITED' | 'MISSING_ON_SEARCH'
  | 'UNAVAILABLE' | 'ARCHIVED' | 'REAPPEARED' | 'STALE'

export interface CommuteResult {
  anchor_id: string
  anchor_name: string
  walk_minutes: number | null
  transit_minutes: number | null
  distance_meters: number | null
}

export interface Listing {
  id: string
  listing_id: string
  url: string
  title: string | null
  price: number | null
  district: string | null
  address: string | null
  size_ping: number | null
  room_type: string | null
  floor: string | null
  thumbnail_url: string | null
  listing_updated_at: string | null
  lat: number | null
  lng: number | null
  status: ListingStatus
  score: number | null
  first_seen_at: string
  last_seen_at: string
  commute_results: CommuteResult[]
}

export interface ListingsResponse {
  total: number
  page: number
  page_size: number
  items: Listing[]
}

export interface ListingEvent {
  id: string
  event_type: string
  old_value: Record<string, unknown> | null
  new_value: Record<string, unknown> | null
  created_at: string
}

export interface SearchProfile {
  id: string
  name: string
  enabled: boolean
  city: string
  districts: string[]
  price_min: number | null
  price_max: number | null
  room_types: string[]
  required_keywords: string[]
  rejected_keywords: string[]
  scan_interval_minutes: number
  last_scanned_at: string | null
  created_at: string
  updated_at: string
}

export interface CommuteAnchor {
  id: string
  name: string
  address: string
  lat: number | null
  lng: number | null
  weight: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ScanRun {
  id: string
  profile_id: string | null
  started_at: string
  finished_at: string | null
  listings_found: number
  new_listings: number
  errors: Record<string, unknown> | null
  status: 'running' | 'success' | 'failed'
}

export interface ListingFilters {
  status?: string
  district?: string
  price_min?: number
  price_max?: number
  score_min?: number
  transit_max?: number
  keyword?: string
  first_seen_after?: string
  first_seen_before?: string
  sort_by?: string
  sort_dir?: string
  page?: number
  page_size?: number
}
