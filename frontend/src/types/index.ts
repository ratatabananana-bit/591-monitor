export type ListingStatus =
  | 'NEW' | 'ACTIVE' | 'SAVED' | 'CHECKING' | 'REJECTED' | 'FILTERED'
  | 'MISSING_ON_SEARCH' | 'UNAVAILABLE' | 'ARCHIVED' | 'REAPPEARED' | 'STALE'
  | 'WATCHED' | 'CONTACTED' | 'VISITED'

export interface CommuteResult {
  anchor_id: string
  anchor_name: string
  walk_minutes: number | null
  transit_minutes: number | null
  distance_meters: number | null
  scooter_minutes: number | null
  scooter_distance_meters: number | null
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
  posted_at: string | null
  lat: number | null
  lng: number | null
  status: ListingStatus
  score: number | null
  score_breakdown: { price: number; freshness: number; commute: number; size: number } | null
  matched_profiles: string[]
  matched_profile_names: string[]
  filtered_by_profile_names: string[]
  rejected_by_profile_names: string[]
  image_urls: string[]
  facilities: string[]
  tags: string[]        // e.g. ["+pet-ok", "-near-mrt"]
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
  min_ping: number | null
  room_types: string[]
  required_keywords: string[]
  rejected_keywords: string[]
  scan_interval_minutes: number
  last_scanned_at: string | null
  created_at: string
  updated_at: string
}

export interface TagRule {
  id: string
  name: string
  keywords: string[]
  reject_keywords: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CommuteAnchor {
  id: string
  name: string
  address: string
  weight: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ScanRun {
  id: string
  profile_id: string | null
  profile_name: string | null
  started_at: string
  finished_at: string | null
  listings_found: number
  new_listings: number
  updated_listings: number
  gone_listings: number
  errors: Record<string, unknown> | null
  status: 'running' | 'cancelling' | 'cancelled' | 'success' | 'partial' | 'failed'
  job_type: 'scan' | 'commute_recalc' | 'backfill_dates' | 'backfill_page_text' | 'rescore' | 'retag_all' | 'telegram_alerts' | null
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
