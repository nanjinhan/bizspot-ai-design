export const GWANGJU_CENTER = {
  lat: 35.159545,
  lng: 126.852601,
}

export const GWANGJU_BOUNDS = {
  minLat: 35.02,
  maxLat: 35.32,
  minLng: 126.65,
  maxLng: 127.02,
}

export function distanceKm(a, b) {
  const pointA = getPointLatLng(a)
  const pointB = getPointLatLng(b)
  if (!pointA || !pointB) return Number.POSITIVE_INFINITY
  const radius = 6371
  const dLat = toRad(pointB.lat - pointA.lat)
  const dLng = toRad(pointB.lng - pointA.lng)
  const lat1 = toRad(pointA.lat)
  const lat2 = toRad(pointB.lat)
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * radius * Math.asin(Math.sqrt(h))
}

export function distanceMeters(a, b) {
  return distanceKm(a, b) * 1000
}

export function toRad(value) {
  return (value * Math.PI) / 180
}

export function getPointLatLng(row) {
  if (!row) return null
  const lat = Number(row.center_lat ?? row.lat ?? row.latitude ?? row['위도'])
  const lng = Number(row.center_lng ?? row.lng ?? row.lon ?? row.longitude ?? row['경도'])
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return { lat, lng }
}

export function isGwangjuCoordinate(point) {
  const normalized = getPointLatLng(point)
  if (!normalized) return false
  return (
    normalized.lat >= GWANGJU_BOUNDS.minLat &&
    normalized.lat <= GWANGJU_BOUNDS.maxLat &&
    normalized.lng >= GWANGJU_BOUNDS.minLng &&
    normalized.lng <= GWANGJU_BOUNDS.maxLng
  )
}

export function projectToFallbackMap(candidate) {
  const point = getPointLatLng(candidate) || GWANGJU_CENTER
  const x =
    ((point.lng - GWANGJU_BOUNDS.minLng) /
      (GWANGJU_BOUNDS.maxLng - GWANGJU_BOUNDS.minLng)) *
    100
  const y =
    100 -
    ((point.lat - GWANGJU_BOUNDS.minLat) /
      (GWANGJU_BOUNDS.maxLat - GWANGJU_BOUNDS.minLat)) *
      100
  return {
    x: Math.max(2, Math.min(98, x)),
    y: Math.max(2, Math.min(98, y)),
  }
}

export function pointFromFallbackClick(event, element) {
  const rect = element.getBoundingClientRect()
  const x = (event.clientX - rect.left) / rect.width
  const y = (event.clientY - rect.top) / rect.height
  return {
    lng: GWANGJU_BOUNDS.minLng + x * (GWANGJU_BOUNDS.maxLng - GWANGJU_BOUNDS.minLng),
    lat: GWANGJU_BOUNDS.maxLat - y * (GWANGJU_BOUNDS.maxLat - GWANGJU_BOUNDS.minLat),
  }
}
