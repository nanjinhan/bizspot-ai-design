import { useEffect, useMemo, useRef, useState } from 'react'
import FallbackMap from './FallbackMap.jsx'
import { loadKakaoMap } from '../utils/kakaoLoader.js'
import { getPointLatLng, GWANGJU_CENTER } from '../utils/geo.js'
import { sortByScore } from '../utils/recommendation.js'

function markerKey(row) {
  return row.grid_id || row.candidate_id || `${row.lat}-${row.lng}-${row.industry || row.recommended_industry}`
}

function uniqueMarkers(rows) {
  const seen = new Set()
  return rows.filter((row) => {
    const key = markerKey(row)
    if (!key || seen.has(key) || !getPointLatLng(row)) return false
    seen.add(key)
    return true
  })
}

function buildMarkerRows({ candidates, gridScores, selectedIndustry }) {
  if (selectedIndustry === 'all') {
    return uniqueMarkers(sortByScore(candidates)).slice(0, 100)
  }

  const candidateRows = sortByScore(
    candidates.filter((row) => row.recommended_industry === selectedIndustry),
  )
  const gridRows = sortByScore(
    gridScores.filter((row) => row.industry === selectedIndustry || row.recommended_industry === selectedIndustry),
  )

  return uniqueMarkers([...candidateRows, ...gridRows]).slice(0, 40)
}

export default function KakaoMap({
  candidates,
  gridScores = [],
  selectedIndustry = 'cafe',
  selectedCandidate,
  topCandidates = [],
  clickedPoint,
  aiRecommendations,
  onMapClick,
  onCandidateSelect,
  onGridSelect,
}) {
  const mapRef = useRef(null)
  const mapInstance = useRef(null)
  const markerStore = useRef([])
  const clickMarkerRef = useRef(null)
  const [mode, setMode] = useState('loading')
  const [fallbackReason, setFallbackReason] = useState('')

  const markerRows = useMemo(
    () => buildMarkerRows({ candidates, gridScores, selectedIndustry }),
    [candidates, gridScores, selectedIndustry],
  )

  useEffect(() => {
    let cancelled = false
    loadKakaoMap()
      .then((kakao) => {
        if (cancelled || !mapRef.current) return
        const center = new kakao.maps.LatLng(GWANGJU_CENTER.lat, GWANGJU_CENTER.lng)
        mapInstance.current = new kakao.maps.Map(mapRef.current, {
          center,
          level: 7,
        })
        kakao.maps.event.addListener(mapInstance.current, 'click', (event) => {
          onMapClick({
            lat: event.latLng.getLat(),
            lng: event.latLng.getLng(),
          })
        })
        setMode('kakao')
      })
      .catch((error) => {
        setFallbackReason(
          error instanceof Error
            ? error.message
            : 'JavaScript 키가 없거나, 키 종류가 다르거나, 현재 URL이 Kakao Developers Web 도메인에 등록되지 않았을 수 있습니다.',
        )
        setMode('fallback')
      })
    return () => {
      cancelled = true
    }
  }, [onMapClick])

  useEffect(() => {
    if (mode !== 'kakao' || !window.kakao?.maps || !mapInstance.current) return
    const kakao = window.kakao
    markerStore.current.forEach((marker) => marker.setMap(null))
    markerStore.current = []

    const topIds = new Set(topCandidates.map((c) => markerKey(c)))
    const selectedId = selectedCandidate ? markerKey(selectedCandidate) : null

    markerRows.forEach((row) => {
      const point = getPointLatLng(row)
      if (!point) return
      const key = markerKey(row)
      if (topIds.has(key)) return

      const isSelected = key === selectedId
      const marker = new kakao.maps.Marker({
        map: mapInstance.current,
        position: new kakao.maps.LatLng(point.lat, point.lng),
        title: row.name || row.grid_id,
        zIndex: isSelected ? 5 : 1,
      })
      kakao.maps.event.addListener(marker, 'click', () => {
        if (row.source_type === 'grid') onGridSelect(row)
        else onCandidateSelect(row)
      })
      markerStore.current.push(marker)
    })

    topCandidates.forEach((candidate, index) => {
      const point = getPointLatLng(candidate)
      if (!point) return
      const key = markerKey(candidate)
      const isSelected = key === selectedId
      const element = document.createElement('button')
      element.className = isSelected ? 'kakao-rank-marker kakao-rank-marker--selected' : 'kakao-rank-marker'
      element.type = 'button'
      element.textContent = String(index + 1)
      element.title = candidate.name || `후보 ${index + 1}`
      element.addEventListener('click', () => onCandidateSelect(candidate))
      const overlay = new kakao.maps.CustomOverlay({
        map: mapInstance.current,
        position: new kakao.maps.LatLng(point.lat, point.lng),
        content: element,
        yAnchor: 1,
        zIndex: isSelected ? 10 : 3,
      })
      markerStore.current.push(overlay)
    })

    aiRecommendations.forEach((candidate, index) => {
      const point = getPointLatLng(candidate)
      if (!point) return
      const element = document.createElement('button')
      element.className = 'kakao-ai-marker'
      element.type = 'button'
      element.textContent = String(index + 1)
      element.title = candidate.name || `AI 추천 ${index + 1}`
      element.addEventListener('click', () => onCandidateSelect(candidate))

      const overlay = new kakao.maps.CustomOverlay({
        map: mapInstance.current,
        position: new kakao.maps.LatLng(point.lat, point.lng),
        content: element,
        yAnchor: 1,
      })
      markerStore.current.push(overlay)
    })

    return () => {
      markerStore.current.forEach((marker) => marker.setMap(null))
      markerStore.current = []
    }
  }, [mode, markerRows, topCandidates, selectedCandidate, aiRecommendations, onCandidateSelect, onGridSelect])

  useEffect(() => {
    if (mode !== 'kakao' || !window.kakao?.maps || !mapInstance.current) return
    const point = getPointLatLng(clickedPoint)
    if (!point) {
      if (clickMarkerRef.current) {
        clickMarkerRef.current.setMap(null)
        clickMarkerRef.current = null
      }
      return
    }
    const kakao = window.kakao
    const position = new kakao.maps.LatLng(point.lat, point.lng)
    if (!clickMarkerRef.current) {
      clickMarkerRef.current = new kakao.maps.Marker({
        map: mapInstance.current,
        position,
        title: '선택 좌표',
        zIndex: 10,
      })
      return
    }
    clickMarkerRef.current.setPosition(position)
  }, [mode, clickedPoint])

  useEffect(() => {
    if (mode !== 'kakao' || !window.kakao?.maps || !mapInstance.current) return
    const point = getPointLatLng(selectedCandidate)
    if (!point) return
    mapInstance.current.setCenter(new window.kakao.maps.LatLng(point.lat, point.lng))
    if (mapInstance.current.getLevel() > 5) mapInstance.current.setLevel(5)
  }, [mode, selectedCandidate])

  if (mode === 'fallback') {
    return (
      <FallbackMap
        markerRows={markerRows}
        selectedCandidate={selectedCandidate}
        clickedPoint={clickedPoint}
        aiRecommendations={aiRecommendations}
        reason={fallbackReason}
        onMapClick={onMapClick}
        onCandidateSelect={onCandidateSelect}
        onGridSelect={onGridSelect}
      />
    )
  }

  return (
    <div className="kakao-map-wrap">
      {mode === 'loading' && <div className="map-loading">지도를 준비하는 중입니다.</div>}
      <div className="kakao-map" data-testid="kakao-map" ref={mapRef} />
      <div className="map-legend">
        <span className="map-legend-item map-legend-rank">1</span> 검색 후보
        <span className="map-legend-item map-legend-selected">1</span> 선택됨
        <span className="map-legend-item map-legend-ai">1</span> AI 추천
      </div>
    </div>
  )
}
